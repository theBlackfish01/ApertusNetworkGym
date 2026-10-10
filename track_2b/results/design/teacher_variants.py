"""Scratch: blocking of BM-LS-KSP restricted to what the prompt can list (not part of the repo).

ong     ONG's select_jocn_ls_bm_ksp_action (lowest slot over all modulations).
strict  lowest start valid at each path's most efficient feasible modulation.
same    lowest start valid at any modulation needing the same slots as that best one.
"""
import json
import sys
from multiprocessing import Pool

import numpy as np
from optical_networking_gym.heuristics import select_heuristic_action
from optical_networking_gym.runtime.action_codec import encode_action, reject_action

from sim import TEACHER, _offsets_by_efficiency, _valid_starts, build_env


def restricted(analysis, same_slots: bool) -> int:
    valid = _valid_starts(analysis)
    order = _offsets_by_efficiency(analysis)
    required = analysis.required_slots_by_path_mod
    best_key, best_action = None, reject_action(analysis.config)
    for p in range(len(analysis.paths)):
        best = next((o for o in order if valid[p, o].any()), None)
        if best is None:
            continue
        offsets = [o for o in order if required[p, o] == required[p, best]] if same_slots else [best]
        starts = np.flatnonzero(valid[p, offsets].any(axis=0))
        slot = int(starts[0])
        offset = next(o for o in offsets if valid[p, o, slot])
        key = (slot, p)
        if best_key is None or key < best_key:
            best_key = key
            best_action = encode_action(analysis.config, path_index=p, modulation_offset=offset, initial_slot=slot)
    return best_action


def run(job):
    variant, load, seed = job
    env = build_env(load, seed, 3000)
    _, info = env.reset(seed=seed)
    for _ in range(1000):
        _, _, _, _, info = env.step(select_heuristic_action(TEACHER, env, info))
    _, info = env.reset(options={"only_episode_counters": True})
    differs = 0
    for _ in range(2000):
        ong = select_heuristic_action(TEACHER, env, info)
        if variant == "ong":
            action = ong
        else:
            action = restricted(env.simulator.current_analysis, variant == "same")
        differs += action != ong
        _, _, _, _, info = env.step(action)
    snap = env.simulator.statistics.snapshot()
    return {"variant": variant, "load": load, "seed": seed, "sbp": snap.episode_service_blocking_rate,
            "bbp": snap.episode_bit_rate_blocking_rate, "differs_from_ong": differs / 2000}


if __name__ == "__main__":
    jobs = [(v, load, s) for load in (240.0, 390.0) for v in ("ong", "strict", "same") for s in (1, 2, 3)]
    with Pool(2) as pool:
        rows = []
        for row in pool.imap_unordered(run, jobs):
            rows.append(row)
            print(json.dumps(row), flush=True)
    print("\nvariant load  SBP% mean (per seed)   BBP% mean   differs from ONG %")
    for load in (240.0, 390.0):
        for v in ("ong", "strict", "same"):
            rs = sorted((r for r in rows if r["variant"] == v and r["load"] == load), key=lambda r: r["seed"])
            sbp = [100 * r["sbp"] for r in rs]
            print(f"{v:7s} {load:5.0f}  {np.mean(sbp):5.2f} ({', '.join(f'{x:.2f}' for x in sbp)})   "
                  f"{100*np.mean([r['bbp'] for r in rs]):5.2f}   {100*np.mean([r['differs_from_ong'] for r in rs]):5.1f}")
    json.dump(rows, open(sys.argv[1], "w"), indent=1)
