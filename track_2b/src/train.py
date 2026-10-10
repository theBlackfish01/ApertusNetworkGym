# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "torch>=2.4",
#   "transformers~=5.19",
#   "peft~=0.21",
#   "bitsandbytes~=0.50; platform_system == 'Linux'",
#   "datasets~=5.1",
#   "accelerate~=1.15",
#   "huggingface_hub~=2.2",
# ]
# ///
"""QLoRA fine-tuning of Apertus v1.5 8B on the provisioning dataset (SPEC section 6).

Self-contained on purpose (it imports nothing from this repository), so it runs unchanged as an
HF Job or on any GPU machine:

    hf jobs uv run --flavor a100-large --secrets HF_TOKEN src/train.py -- \\
        --dataset-repo <user>/apertus-lightpath --hub-adapter <user>/apertus-lightpath-lora \\
        --hub-merged <user>/apertus-lightpath-merged
    uv run src/train.py --data-dir data/full --out runs/apertus-ft        # on a GPU box

    uv run src/train.py --data-dir data/full --dry-run     # tokenizer only, no GPU: prints one
                                                           # rendered example and token statistics

Recipe: 4-bit NF4 base, LoRA r=32 alpha=32 dropout 0.05 on all six projection matrices of a block,
lr 2e-4 cosine with 5 % warm-up, 2 epochs, batch 8 x accumulation 4, bf16, gradient
checkpointing, paged_adamw_8bit, max length 768.

Loss is on the completion only. Each example is rendered with the tokenizer's chat template;
the tokens of the prompt (up to and including the assistant start) get label -100, the answer
and the end token ``<|assistant_end|>`` are the targets. Label ids 131072-131271 are also set
to -100: those head rows are untrained in the text-only conversion.

Outputs in ``--out``: ``adapter/``, ``training_log.json`` and ``heldout_predictions.jsonl``
(greedy, unconstrained answers of the merged model on the three held-out splits; score them with
``uv run python src/evaluate.py offline --policy apertus_ft --predictions ...``), plus ``merged/``
(bf16) with ``--save-merged``. With ``--hub-adapter`` the adapter is pushed to the Hub at the end
of every epoch and again with the log as soon as training ends, so a job that dies later loses
nothing. Held-out data is used for the loss curve and these predictions only, never for training.
"""

from __future__ import annotations

import argparse
import gc
import json
import statistics
from pathlib import Path

MODEL = "andreasmartin/apertus-v1.5-8b-text"
SPLITS = ("train", "heldout_indist", "heldout_paraphrase", "heldout_pairs")
# Every projection matrix of an Apertus block. There is no gate projection: its MLP is up -> xIELU -> down.
LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "up_proj", "down_proj"]
UNTRAINED_LABEL_IDS = (131072, 131271)  # inclusive


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--data-dir", type=Path, help="directory with train.jsonl and heldout_*.jsonl")
    parser.add_argument("--dataset-repo", help="Hugging Face dataset repo holding the same files")
    parser.add_argument("--out", type=Path, default=Path("runs/apertus-ft"))
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--accumulation", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=768)
    parser.add_argument("--lora-r", type=int, default=32)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--template-kwargs", default="{}", help="JSON passed to the chat template")
    parser.add_argument("--hub-adapter", help="repo to push the adapter to (created private)")
    parser.add_argument("--hub-merged", help="repo to push the merged bf16 model to (created private)")
    # smoke tests and inspection
    parser.add_argument("--dry-run", action="store_true", help="tokenize and report; no model, no training")
    parser.add_argument(
        "--no-4bit", action="store_true", help="base in bf16 (float32 on CPU) instead of 4-bit"
    )
    parser.add_argument("--limit-train", type=int, default=0)
    parser.add_argument("--limit-heldout", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument(
        "--skip-merge", action="store_true", help="predict with the adapter instead of merging"
    )
    parser.add_argument(
        "--save-merged", action="store_true", help="also write the merged bf16 model to --out"
    )
    parser.add_argument("--eval-records", type=int, default=200, help="held-out records for the loss curve")
    parser.add_argument(
        "--save-steps", type=int, default=100, help="checkpoint every N optimizer steps (0: never)"
    )
    parser.add_argument(
        "--resume", action="store_true", help="continue from the checkpoint or adapter on the Hub"
    )
    parser.add_argument("--resume-dir", default=None, help="continue from this local checkpoint directory")
    parser.add_argument(
        "--die-at-step", type=int, default=0, help="test only: fail after this optimizer step"
    )
    parser.add_argument("--predict-batch", type=int, default=32)
    return parser.parse_args()


def load_split(args: argparse.Namespace, split: str) -> list[dict]:
    if args.data_dir:
        path = args.data_dir / f"{split}.jsonl"
    else:
        from huggingface_hub import hf_hub_download

        path = Path(hf_hub_download(args.dataset_repo, f"{split}.jsonl", repo_type="dataset"))
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def render(tokenizer, record: dict, template_kwargs: dict) -> tuple[str, str]:
    """``(prompt text ending at the assistant start, target text ending with the end token)``."""
    prompt = tokenizer.apply_chat_template(
        record["prompt"], tokenize=False, add_generation_prompt=True, **template_kwargs
    )
    full = tokenizer.apply_chat_template(
        record["prompt"] + record["completion"], tokenize=False, **template_kwargs
    )
    if not full.startswith(prompt):
        raise ValueError(
            "the chat template does not render prompt+answer as an extension of the prompt; "
            f"inspect it before training.\n--- prompt ---\n{prompt}\n--- full ---\n{full}"
        )
    target = full[len(prompt) :]
    eos = tokenizer.eos_token
    if eos not in target:
        target = target.rstrip() + eos
    return prompt, target[: target.rindex(eos) + len(eos)]


def encode(tokenizer, record: dict, template_kwargs: dict, max_length: int) -> dict | None:
    prompt, target = render(tokenizer, record, template_kwargs)
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    target_ids = tokenizer(target, add_special_tokens=False)["input_ids"]
    if len(prompt_ids) + len(target_ids) > max_length:
        return None
    low, high = UNTRAINED_LABEL_IDS
    labels = [-100] * len(prompt_ids) + [-100 if low <= t <= high else t for t in target_ids]
    input_ids = prompt_ids + target_ids
    return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels,
            "prompt_tokens": len(prompt_ids)}  # fmt: skip


def report_tokens(
    tokenizer, data: dict[str, list[dict]], args: argparse.Namespace, template_kwargs: dict
) -> None:
    """Print one rendered example and the token statistics of every split."""
    record = data["train"][0]
    prompt, target = render(tokenizer, record, template_kwargs)
    encoded = encode(tokenizer, record, template_kwargs, 10**9)
    print("=== rendered prompt (label -100) ===")
    print(prompt)
    print("=== target (trained on) ===")
    print(repr(target), "->", encoded["input_ids"][encoded["prompt_tokens"] :])
    low, high = UNTRAINED_LABEL_IDS
    print(f"eos token {tokenizer.eos_token!r} id {tokenizer.eos_token_id}; vocabulary {len(tokenizer)}")
    if low <= tokenizer.eos_token_id <= high:
        raise SystemExit("the end token lies in the masked label range: it would never be trained")
    for split, records in data.items():
        prompt_tokens, total, masked = [], [], 0
        for item in records:
            enc = encode(tokenizer, item, template_kwargs, 10**9)
            prompt_tokens.append(enc["prompt_tokens"])
            total.append(len(enc["input_ids"]))
            masked += sum(1 for t in enc["input_ids"][enc["prompt_tokens"] :] if low <= t <= high)
        user = [
            len(tokenizer(r["prompt"][-1]["content"], add_special_tokens=False)["input_ids"]) for r in records
        ]
        print(
            f"{split:20s} n={len(records):6d}  user-message tokens mean {statistics.fmean(user):.0f} max {max(user)} "
            f"(over 450: {sum(u > 450 for u in user)})  full sequence max {max(total)} "
            f"(over {args.max_length}: {sum(t > args.max_length for t in total)})  target ids in masked range: {masked}"
        )


def main() -> None:
    args = parse_args()
    if not args.data_dir and not args.dataset_repo:
        raise SystemExit("give --data-dir or --dataset-repo")
    template_kwargs = json.loads(args.template_kwargs)

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    data = {split: load_split(args, split) for split in SPLITS}
    if args.limit_train:
        data["train"] = data["train"][: args.limit_train]
    if args.limit_heldout:
        for split in SPLITS[1:]:
            data[split] = data[split][: args.limit_heldout]
    report_tokens(tokenizer, data, args, template_kwargs)
    if args.dry_run:
        return

    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        BitsAndBytesConfig,
        Trainer,
        TrainerCallback,
        TrainingArguments,
    )

    def tokenized(records: list[dict]) -> Dataset:
        rows = [encode(tokenizer, r, template_kwargs, args.max_length) for r in records]
        kept = [{k: row[k] for k in ("input_ids", "labels")} for row in rows if row]
        print(
            f"tokenized {len(kept)} of {len(records)} records (dropped {len(records) - len(kept)} over max length)"
        )
        return Dataset.from_list(kept)

    def collate(batch: list[dict]) -> dict:
        """Right-pad to the longest example; padding is masked out of attention and loss."""
        width = max(len(item["input_ids"]) for item in batch)
        input_ids, attention, labels = [], [], []
        for item in batch:
            pad = width - len(item["input_ids"])
            input_ids.append(item["input_ids"] + [tokenizer.pad_token_id] * pad)
            attention.append([1] * len(item["input_ids"]) + [0] * pad)
            labels.append(item["labels"] + [-100] * pad)
        return {
            "input_ids": torch.tensor(input_ids),
            "attention_mask": torch.tensor(attention),
            "labels": torch.tensor(labels),
        }

    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    args.out.mkdir(parents=True, exist_ok=True)
    adapter_dir = args.out / "adapter"
    api = None
    if args.hub_adapter or args.hub_merged:
        from huggingface_hub import HfApi, snapshot_download

        api = HfApi()
        for repo in filter(None, (args.hub_adapter, args.hub_merged)):
            api.create_repo(repo, private=True, exist_ok=True)  # fail now, not after hours of training

    # --resume: continue from what an earlier job left on the Hub. If training had finished, only
    # the predictions are redone; otherwise it restarts from the last pushed checkpoint (adapter,
    # optimizer, scheduler, data position), so at most --save-steps optimizer steps are repeated.
    finished, resume_from = False, args.resume_dir
    if args.resume and api is not None and args.hub_adapter:
        remote = set(api.list_repo_files(args.hub_adapter))
        if {"adapter_model.safetensors", "training_log.json"} <= remote:
            finished = True
            snapshot_download(
                args.hub_adapter, local_dir=str(adapter_dir), allow_patterns=["adapter_*", "*.jinja"]
            )
            snapshot_download(args.hub_adapter, local_dir=str(args.out), allow_patterns=["training_log.json"])
            tokenizer.save_pretrained(adapter_dir)
            print("training already finished on the Hub: skipping to the predictions", flush=True)
        elif "checkpoint/trainer_state.json" in remote:
            snapshot_download(
                args.hub_adapter, local_dir=str(args.out / "resume"), allow_patterns=["checkpoint/*"]
            )
            resume_from = str(args.out / "resume" / "checkpoint")
    if resume_from and not finished:
        step = json.loads(Path(resume_from, "trainer_state.json").read_text())["global_step"]
        print(f"resuming training from the checkpoint at optimizer step {step}", flush=True)

    def fit():
        """Train (or continue training) the adapter; returns the trained PEFT model."""
        quantization = None
        if not args.no_4bit:
            quantization = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
            )  # fmt: skip
        model = AutoModelForCausalLM.from_pretrained(
            args.model, quantization_config=quantization, dtype=dtype, device_map="auto"
        )
        model.config.use_cache = False  # incompatible with gradient checkpointing
        if quantization is not None:
            model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
        else:
            model.enable_input_require_grads()  # lets gradients reach the adapters through checkpointed blocks
        lora = LoraConfig(
            r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
            target_modules=LORA_TARGETS, task_type="CAUSAL_LM",
        )  # fmt: skip
        model = get_peft_model(model, lora)
        model.print_trainable_parameters()
        config = TrainingArguments(
            output_dir=str(args.out / "checkpoints"),
            num_train_epochs=args.epochs,
            max_steps=args.max_steps,
            per_device_train_batch_size=args.batch,
            per_device_eval_batch_size=args.batch,
            gradient_accumulation_steps=args.accumulation,
            learning_rate=args.lr,
            lr_scheduler_type="cosine",
            warmup_steps=0.05,  # a value below 1 is a ratio of the total steps
            bf16=torch.cuda.is_available(),
            optim="adamw_torch" if args.no_4bit else "paged_adamw_8bit",
            gradient_checkpointing=True,
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=100 if args.max_steps < 0 else max(1, args.max_steps),
            save_strategy="steps" if args.save_steps > 0 else "no",
            save_steps=max(1, args.save_steps),
            save_total_limit=1,
            report_to="none",
            seed=args.seed,
            remove_unused_columns=False,  # the datasets hold exactly input_ids and labels
        )

        class PushProgress(TrainerCallback):
            """Copy progress to the Hub while training: the latest checkpoint every time one is
            saved, and the adapter at the end of every epoch."""

            def on_save(self, train_args, state, control, **kwargs):
                if api is None or not args.hub_adapter:
                    return
                folder = Path(train_args.output_dir) / f"checkpoint-{state.global_step}"
                api.upload_folder(
                    repo_id=args.hub_adapter,
                    folder_path=str(folder),
                    path_in_repo="checkpoint",
                    delete_patterns="*",
                )
                print(f"pushed checkpoint at optimizer step {state.global_step}", flush=True)

            def on_epoch_end(self, train_args, state, control, **kwargs):
                if api is None or not args.hub_adapter:
                    return
                folder = args.out / f"adapter-epoch{round(state.epoch)}"
                kwargs["model"].save_pretrained(folder)
                api.upload_folder(repo_id=args.hub_adapter, folder_path=str(folder), path_in_repo=folder.name)
                print(f"pushed {folder.name} to {args.hub_adapter}", flush=True)

            def on_step_end(self, train_args, state, control, **kwargs):
                if args.die_at_step and state.global_step == args.die_at_step:
                    raise SystemExit(
                        f"simulated failure at optimizer step {state.global_step} (--die-at-step)"
                    )

        trainer = Trainer(
            model=model,
            args=config,
            train_dataset=tokenized(data["train"]),
            eval_dataset=tokenized(data["heldout_indist"][: args.eval_records]),  # loss curve only
            data_collator=collate,
            callbacks=[PushProgress()],
        )
        outcome = trainer.train(resume_from_checkpoint=resume_from)
        print(f"training: {outcome.metrics}", flush=True)
        trainer.model.save_pretrained(adapter_dir)
        tokenizer.save_pretrained(adapter_dir)
        log = {"args": {k: str(v) for k, v in vars(args).items()}, "resumed_from": resume_from,
               "metrics": outcome.metrics, "log": trainer.state.log_history}  # fmt: skip
        (args.out / "training_log.json").write_text(json.dumps(log, indent=2))
        if api is not None and args.hub_adapter:
            api.upload_folder(repo_id=args.hub_adapter, folder_path=str(adapter_dir))
            api.upload_file(
                repo_id=args.hub_adapter,
                path_or_fileobj=str(args.out / "training_log.json"),
                path_in_repo="training_log.json",
            )
            print(f"pushed adapter and training log to {args.hub_adapter} (private)", flush=True)
        return trainer.model

    trained = None if finished else fit()
    if args.skip_merge and trained is not None:
        predictor = trained
    else:
        del trained
        gc.collect()
        torch.cuda.empty_cache()
        base = AutoModelForCausalLM.from_pretrained(args.model, dtype=dtype, device_map="auto")
        predictor = PeftModel.from_pretrained(base, adapter_dir).merge_and_unload()
        if args.save_merged or args.hub_merged:
            predictor.save_pretrained(args.out / "merged")
            tokenizer.save_pretrained(args.out / "merged")
    predictor.eval()

    tokenizer.padding_side = "left"
    with (args.out / "heldout_predictions.jsonl").open("w", encoding="utf-8") as handle:
        for split in SPLITS[1:]:
            records = data[split]
            for start in range(0, len(records), args.predict_batch):
                chunk = records[start : start + args.predict_batch]
                prompts = [render(tokenizer, r, template_kwargs)[0] for r in chunk]
                inputs = tokenizer(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(
                    predictor.device
                )
                with torch.no_grad():
                    output = predictor.generate(
                        **inputs, max_new_tokens=16, do_sample=False, pad_token_id=tokenizer.pad_token_id
                    )
                answers = tokenizer.batch_decode(
                    output[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True
                )
                for record, answer in zip(chunk, answers, strict=True):
                    handle.write(
                        json.dumps({"id": record["id"], "split": split, "answer": answer.strip()}) + "\n"
                    )
            print(f"predicted {split}: {len(records)} records", flush=True)

    if api is not None:
        predictions = str(args.out / "heldout_predictions.jsonl")
        if args.hub_adapter:
            api.upload_file(
                repo_id=args.hub_adapter,
                path_or_fileobj=predictions,
                path_in_repo="heldout_predictions.jsonl",
            )
            print(f"pushed held-out predictions to {args.hub_adapter}", flush=True)
        if args.hub_merged:
            api.upload_folder(repo_id=args.hub_merged, folder_path=str(args.out / "merged"))
            print(f"pushed merged model to {args.hub_merged} (private)", flush=True)


if __name__ == "__main__":
    main()
