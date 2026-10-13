# Operator instructions for lightpath provisioning with Apertus 8B

Hack Apertus 2026, Track 2B (own project). An operator of an optical transport network states a
routing policy in plain language, in German, French, Italian or English; Apertus 8B reads it
once into one line of a small policy language; a rule engine enforces that line on every
lightpath request the policy covers, for as long as it holds. Evaluated in closed loop in the
Optical Networking Gym simulator; runs on a laptop GPU, on premise and air-gapped.

The project lives in [`track_2b/`](track_2b/README.md), which follows the
[Hack Apertus project template](https://github.com/HackApertus/project-template). From this
directory or from `track_2b/`:

```bash
make run        # builds the Docker image and runs the demo end to end (no GPU, no secrets)
make console    # the operator console on http://localhost:8090
```

The technical report is [`track_2b/technical_report.md`](track_2b/technical_report.md); the
implementation spec the work started from is [`SPEC.md`](SPEC.md).
