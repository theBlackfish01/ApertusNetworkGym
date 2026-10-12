# /// script
# requires-python = ">=3.11"
# dependencies = ["huggingface_hub~=2.2"]
# ///
"""Fetch single files that a job left in the work repo, into the same path below ``track_2b/``.

    WORK_REPO=<user>/apertus-lightpath-work-v2 uv run jobs/fetch.py results/cache/translate2_ft.jsonl ...

Each file is downloaded afresh (``force_download``). The ``hf download`` command with several
``--include`` patterns left one answer cache out and kept a stale copy of another (11 Oct 2026); a
replay then fails with "No module named 'torch'", because a missing answer makes the code load the model.
"""

import os
import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
repo = os.environ["WORK_REPO"]
for name in sys.argv[1:]:
    source = hf_hub_download(repo, name, repo_type="dataset", force_download=True)
    target = ROOT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, target)
    print(f"{name}: {target.stat().st_size:,} bytes")
