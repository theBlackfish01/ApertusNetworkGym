"""MLP control (SPEC section 7): a small numeric model trained on the same examples as Apertus.

It answers "did the language model's pretraining buy anything?". Inputs are the numbers the
prompt shows for each candidate path, plus a flag per intent id. The MLP cannot read the link
named by an avoid-link intent, so each path also gets a flag saying whether it contains that
link. The output is one of six classes: path 0-4 or reject. The start slot is the first listed
block of the chosen path, which is what every teacher answers.

Two hidden layers, ReLU, softmax; trained with Adam in plain numpy and stored as ``.npz``, so
inference needs nothing but numpy.

    uv run python src/mlp.py            # train on data/full/train.jsonl -> results/mlp/
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from intents import SINGLES, Intent
from view import Choice, RequestView

ROOT = Path(__file__).resolve().parents[1]
MAX_PATHS = 5
REJECT = MAX_PATHS  # class index
PATH_FEATURES = (
    "feasible", "hops", "km", "slots_needed", "free_slots", "first_slot", "blocks", "largest_block", "has_avoided_link",
)  # fmt: skip
N_FEATURES = MAX_PATHS * len(PATH_FEATURES) + 2 + len(SINGLES)


def features(view: RequestView, intent: Intent) -> np.ndarray:
    """Fixed-length input vector; every entry is scaled to roughly [0, 1]."""
    slots = float(view.num_slots)
    rows = []
    for index in range(MAX_PATHS):
        if index >= len(view.paths):
            rows.append([0.0] * len(PATH_FEATURES))
            continue
        path = view.paths[index]
        avoided = intent.link is not None and path.has_link(*intent.link)
        rows.append(
            [
                float(path.feasible),
                path.hops / 10.0,
                path.km / 4000.0,
                (path.slots_needed or 0) / 40.0,
                path.free_slots / slots,
                (path.first_slot if path.feasible else slots) / slots,
                min(len(path.blocks), 20) / 20.0,
                path.largest_block / slots,
                float(avoided),
            ]
        )
    extra = [view.bit_rate / 400.0, view.free_ratio] + [float(i in intent.ids) for i in SINGLES]
    return np.asarray([value for row in rows for value in row] + extra, dtype=np.float32)


def label(choice: Choice) -> int:
    return REJECT if choice is None else int(choice[0])


class MLP:
    """Inference with stored weights: ``predict`` returns a choice for a request."""

    def __init__(self, weights: list[np.ndarray], biases: list[np.ndarray]) -> None:
        self.weights, self.biases = weights, biases

    @classmethod
    def load(cls, path: Path) -> MLP:
        data = np.load(path)
        layers = len([k for k in data.files if k.startswith("w")])
        return cls([data[f"w{i}"] for i in range(layers)], [data[f"b{i}"] for i in range(layers)])

    def save(self, path: Path) -> None:
        arrays = {f"w{i}": w for i, w in enumerate(self.weights)} | {
            f"b{i}": b for i, b in enumerate(self.biases)
        }
        np.savez(path, **arrays)

    def logits(self, x: np.ndarray) -> np.ndarray:
        for w, b in zip(self.weights[:-1], self.biases[:-1], strict=True):
            x = np.maximum(x @ w + b, 0.0)
        return x @ self.weights[-1] + self.biases[-1]

    def predict(self, view: RequestView, intent: Intent) -> Choice:
        cls = int(np.argmax(self.logits(features(view, intent)[None, :])[0]))
        if cls == REJECT:
            return None
        if cls >= len(view.paths) or not view.paths[cls].feasible:
            return (cls, 0)  # not a valid action: the evaluator counts it as invalid
        return (cls, view.paths[cls].first_slot)


def train(
    x: np.ndarray,
    y: np.ndarray,
    *,
    hidden: int = 128,
    epochs: int = 300,
    batch: int = 128,
    lr: float = 1e-3,
    patience: int = 30,
    seed: int = 0,
) -> tuple[MLP, dict]:
    """Adam on softmax cross-entropy; keeps the weights with the best accuracy on a 10 % holdout."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(x))
    n_val = len(x) // 10
    val, tr = order[:n_val], order[n_val:]
    sizes = [x.shape[1], hidden, hidden, MAX_PATHS + 1]
    params = []
    for fan_in, fan_out in itertools.pairwise(sizes):
        params += [rng.normal(0.0, np.sqrt(2.0 / fan_in), (fan_in, fan_out)).astype(np.float32),
                   np.zeros(fan_out, dtype=np.float32)]  # fmt: skip
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    step, best_acc, best_params, best_epoch = 0, -1.0, None, 0

    def model() -> MLP:
        return MLP(params[0::2], params[1::2])

    for epoch in range(1, epochs + 1):
        for start in range(0, len(tr), batch):
            idx = tr[start : start + batch]
            activations = [x[idx]]
            for w, b in zip(params[0:-2:2], params[1:-2:2], strict=True):
                activations.append(np.maximum(activations[-1] @ w + b, 0.0))
            logits = activations[-1] @ params[-2] + params[-1]
            logits -= logits.max(axis=1, keepdims=True)
            probs = np.exp(logits)
            probs /= probs.sum(axis=1, keepdims=True)
            delta = probs
            delta[np.arange(len(idx)), y[idx]] -= 1.0
            delta /= len(idx)
            grads = [None] * len(params)
            for layer in range(len(sizes) - 2, -1, -1):
                grads[2 * layer] = activations[layer].T @ delta
                grads[2 * layer + 1] = delta.sum(axis=0)
                if layer:
                    delta = (delta @ params[2 * layer].T) * (activations[layer] > 0)
            step += 1
            for i, grad in enumerate(grads):
                m[i] = 0.9 * m[i] + 0.1 * grad
                v[i] = 0.999 * v[i] + 0.001 * grad * grad
                params[i] = params[i] - lr * (m[i] / (1 - 0.9**step)) / (
                    np.sqrt(v[i] / (1 - 0.999**step)) + 1e-8
                )
        tr = tr[rng.permutation(len(tr))]
        acc = float(np.mean(np.argmax(model().logits(x[val]), axis=1) == y[val]))
        if acc > best_acc:
            best_acc, best_params, best_epoch = acc, [p.copy() for p in params], epoch
        elif epoch - best_epoch >= patience:
            break
    params = best_params
    info = {"hidden": hidden, "epochs_run": epoch, "best_epoch": best_epoch, "val_accuracy": best_acc,
            "train_examples": len(tr), "val_examples": n_val, "lr": lr, "batch": batch, "seed": seed}  # fmt: skip
    return model(), info


def load_examples(path: Path) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            meta = json.loads(line)["meta"]
            xs.append(features(RequestView.from_json(meta["view"]), Intent.from_json(meta["intent"])))
            ys.append(label(tuple(meta["teacher_choice"]) if meta["teacher_choice"] else None))
    return np.stack(xs), np.asarray(ys, dtype=np.int64)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--train", type=Path, default=ROOT / "data" / "full" / "train.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "mlp")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    x, y = load_examples(args.train)
    model, info = train(x, y, seed=args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    model.save(args.out / "mlp.npz")
    info |= {"train_file": args.train.name, "features": N_FEATURES, "path_features": list(PATH_FEATURES)}
    (args.out / "training.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
