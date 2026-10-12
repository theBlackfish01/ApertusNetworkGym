---
license: cdla-permissive-2.0
language:
  - en
  - de
  - fr
  - it
  - ur
task_categories:
  - text2text-generation
pretty_name: Operator instructions for lightpath provisioning
---

# Dataset Card: operator instructions for lightpath provisioning

Instructions an operator of an optical transport network might type about how a lightpath is
routed ("the Zurich–Milan span is under maintenance", "at most four hops, then the shortest in
km", "for 400G services, avoid Basel until further notice"), each with the line of a small policy
language it means, and the answers of several Apertus readers to each. Built for Hack Apertus
(online hackathon, October 2026, Track 2B) by the project *Operator instructions for lightpath
provisioning with Apertus 8B*.

## Dataset Details

- **Curated by:** the project's author (Wadood Ranjha), with sentences written by separate AI
  instances from briefs; see *Source Data*.
- **Language(s) (NLP):** English, German, French, Italian; 5 lines of Urdu in Latin script.
- **License:** CDLA-Permissive-2.0 (the whole dataset and every instance).
- **Git repository:** the project repository (`track_2b/`), which holds the generators
  (`src/corpora3_tests.py`, `src/corpora4_tests.py`, `src/swiss.py`, `src/benchmark_export.py`).

## Uses

### Direct Use

Evaluating a model that turns an operator's instruction into a structured routing policy: for
each instruction the expected line is given, so a translation can be scored exactly (same
meaning, applied with another meaning, not applied). The responses file gives the answers of the
project's readers, so new models can be compared with them on the same sentences.

### Out-of-Scope Use

The sentences are synthetic (written by AI instances from briefs, except the author's 22). They
are not a record of what operators say. The policy language carries seven slots; instructions
outside it are included only as material the model should refuse or hand on.

### Specifications

- `evaluation.jsonl`: one row per instruction: `id`, `set`, `lang`, `kind`, `text`, `topology`
  (`nobel-eu` or `swiss`), `means` (the line of the fourth format it means, or `unsupported`,
  `no_instruction`, `unresolved`), `spec` (the same as JSON), `written_by`.
- `responses.jsonl`: one row per instruction and reader: `id`, `reader`, `line`, `outcome`.
- `metadata.json`: the sets, the readers, the outcome definitions, the line format, counts.

## Dataset Structure

Sets (`set` field): the policy language in four languages (`v3_en`, `v3_de`, `v3_fr`, `v3_it`:
every clause kind alone, clause pairs seen and never seen in training, triples, two preferences);
instruction types shown to no component (`v3_new`, `v3_new_hard`, `v3_new_impossible`);
instructions carried in part (`v3_partial`); other routing instructions (`v3_other`); text that is
no instruction (`v3_not`); places outside the network (`v3_faulty`); the author's own lines
(`owner`); standing policies with a scope or a lifetime (`v4_en` … `v4_it`); the same sentences on
a Swiss network with the cities in each language's own name (`v3_swiss_en` … `v3_swiss_it`).

The line format: `avoid=<links,nodes>; via=<node>; hops=<n|any>; km=<n|any>; path=<0-4|any>;
prefer=<hops,km,load,slots in order>; scope=<any|rate:G|from:node|to:node>; until=<open|Nh>;
rest=<none|more>`, or `unsupported`, or `no_instruction`.

## Dataset Creation

### Curation Rationale

To measure whether a small open model reads operator instructions right, including combinations
of clauses it never saw together, languages, names of places, and instructions outside its
language, with test sentences written by someone other than the people who wrote the training
templates.

### Source Data

#### Data Collection

The sentences of the `v3_*` sets were written by four separate AI instances (one per language)
from a brief that named the clause kinds, the cities and none of the project's wording. The
scope and lifetime phrases of the `v4_*` sets were written by another instance from a brief, and
attached to `v3` sentences by a script. The `v3_swiss_*` sets fill the `v3` sentences with Swiss
cities in each language's own name. The `owner` set was typed by the author. Placeholders
(cities, links, limits, bit rates, hours) were filled by scripts with values from the topology.

#### Source Data Producers and Data Subjects

Producers: AI instances (Claude, Anthropic) writing from briefs; the author. No data subjects:
the sentences describe no person.

#### Ownership and Consent Management

All sentences were created for this dataset by its author or by AI instances under the author's
direction; nothing was collected from third parties.

#### Data Processing and Quality Control

Every expected line is produced by the same script that fills the sentence, so it cannot drift
from the sentence; lines are validated against the topology (a place that is not a node makes
the instruction `unresolved`); duplicates within a set are dropped. The sets with decisions
behind them (`v3_new_hard`, `v3_new_impossible`) were placed on simulated requests by a
condition on the instruction and the request only.

#### Data Instance Licenses

CDLA-Permissive-2.0 for every instance.

### Annotations

#### Annotation Process

The annotation is the expected line, generated with the sentence (see above). The responses are
model outputs, decoded under a grammar that admits only lines of the format; their `outcome` is
computed by comparing the meaning of the line with the expected one.

#### Annotator Details

Scripts in the project repository; no human annotation beyond the author's 22 lines.

## Risks, Bias, and Limitations

The sentences are AI-written and may be more regular than what operators type. Four languages
only; Swiss German and Romansh are not covered. The policy language carries seven slots; the
dataset says nothing about instructions it cannot carry beyond asking that they be handed on or
refused.

### Personally Identifiable Information

None: the only names are those of cities.

### Sensitive Information

None.

### Recommendations

Use the `v3_new*` and `v3_partial` sets to measure what a model does with what it was never
shown, not only the sets inside the language; report instruction-blind baselines next to any
decision-level number.

## Citations [optional]

The project's technical report (Hack Apertus online hackathon, October 2026).
