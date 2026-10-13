# Data

- `benchmark/`: the published dataset: 4,712 test instructions in 20 sets with the line each
  means, every reader's answers with their outcome, metadata and a card in the HackApertus
  format. Built by `src/benchmark_export.py`; on the Hub as `blackfish021/apertus-lightpath-benchmark`.
- `instructions/`: the test sets and their sources (sentences written by separate AI instances
  from briefs; `owner_source.txt` holds the author's own lines); `topologies/`: the Swiss network
  and the city names in four languages; `fewshot/`: the examples of the untrained translators;
  `translate4/`: the fourth format's training data; `sample/` and `stats.json`: a sample of the
  decider's dataset and its statistics.
- Not committed, rebuilt by the pipeline (README, "Pipeline"): `full/` (the decider's 12,000
  training decisions and held-out splits, `src/generate.py`), `probes/`, `translate/`,
  `translate2/`, `translate3/` (the earlier formats' training data), `pass1/`. None is needed to
  run `make run` or the console; they are needed only to retrain.
