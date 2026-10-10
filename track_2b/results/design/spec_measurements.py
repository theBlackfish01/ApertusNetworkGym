"""Scratch: measure spec ambiguities on live states (not part of the repo)."""
import random
import sys
from collections import Counter

from optical_networking_gym.heuristics import select_heuristic_action
from optical_networking_gym.heuristics.runtime_heuristics import select_load_balancing_action

import intents as I
from sim import TEACHER, action_from_choice, build_env, choice_from_action, view_from_analysis

loads = [float(x) for x in sys.argv[1:]] or [150.0, 270.0, 390.0]
rng = random.Random(0)
KINDS = [(), ("I1",), ("I2",), ("I3",), ("I4",), ("I1", "I2"), ("I1", "I3"), ("I1", "I4"), ("I2", "I3")]

for load in loads:
    env = build_env(load, 11, 1000)
    _, info = env.reset(seed=11)
    c = Counter()
    blocks_gt3 = Counter()
    maxhops = 0
    for step in range(1000):
        analysis = env.simulator.current_analysis
        action = select_heuristic_action(TEACHER, env, info)
        if step >= 300:
            view = view_from_analysis(analysis)
            c["n"] += 1
            ong = choice_from_action(analysis, action)
            ours = I.teacher_choice(view, I.NO_INTENT)
            c["I0_matches_ONG"] += ours == ong
            assert action_from_choice(analysis, ours) == action or ours != ong
            feasible = [p for p in view.paths if p.feasible]
            c["any_feasible"] += bool(feasible)
            if ours is not None:
                c["I0_accept"] += 1
                p = view.paths[ours[0]]
                c["I0_offlist_slot"] += ours[1] != p.first_slot
                # best-modulation-only variant of BM-LS-KSP
                alt = min(feasible, key=lambda q: (q.first_slot, q.index))
                c["I0_bestmod_variant_same_path"] += alt.index == ours[0]
            for p in view.paths:
                maxhops = max(maxhops, p.hops)
                if p.feasible:
                    c["feasible_paths"] += 1
                    c["paths_gt3_blocks"] += len(p.blocks) > 3
                    c["paths_lowest_lt_first"] += p.lowest_slot < p.first_slot
            # ONG load balancing path vs "most free slots"
            lb = choice_from_action(analysis, select_load_balancing_action(env.heuristic_context()))
            mine = I.teacher_choice(view, I.Intent(("I3",), "x"))
            if lb is not None:
                c["LB_accept"] += 1
                c["LB_same_path_as_most_free"] += lb[0] in I.admissible_paths(view, I.Intent(("I3",), "x"))
                c["LB_slot_is_first_fit"] += lb[1] == view.paths[lb[0]].first_slot
            base = I.teacher_choice(view, I.NO_INTENT)
            for ids in KINDS[1:]:
                intent = I.sample_intent(view, ids, rng)
                key = intent.key
                allowed = I.admissible_paths(view, intent)
                choice = I.teacher_choice(view, intent)
                if feasible:
                    c[f"{key}|n"] += 1
                    c[f"{key}|empty"] += not allowed
                    c[f"{key}|path_differs_from_I0"] += (choice is None) != (base is None) or (
                        choice is not None and base is not None and choice[0] != base[0]
                    )
                    c[f"{key}|I0_choice_admissible"] += I.is_admissible(view, intent, base)
                    c[f"{key}|n_allowed_{min(len(allowed), 3)}"] += 1
                    if len(ids) == 2 and "I1" in ids:
                        # sequential semantics: filter by I1 first, then rank the rest
                        rest = [p for p in feasible if not p.has_link(*intent.link)]
                        c[f"{key}|seq_empty"] += not rest
        _, _, term, trunc, info = env.step(action)
    n = c["n"]
    print(f"\n=== load {load:g}: {n} requests, max hops {maxhops}")
    for k in ["any_feasible", "I0_matches_ONG", "I0_accept"]:
        print(f"  {k}: {c[k]} ({100*c[k]/n:.1f}%)")
    a = max(c["I0_accept"], 1)
    print(f"  I0 teacher slot off the listed blocks (lower modulation at lower slot): {c['I0_offlist_slot']} ({100*c['I0_offlist_slot']/a:.2f}% of accepts)")
    fp = max(c["feasible_paths"], 1)
    print(f"  feasible paths with lowest_slot < first best-mod slot: {100*c['paths_lowest_lt_first']/fp:.2f}%   with >3 blocks: {100*c['paths_gt3_blocks']/fp:.1f}%")
    lb = max(c["LB_accept"], 1)
    print(f"  ONG load_balancing: path is a most-free-slots path {100*c['LB_same_path_as_most_free']/lb:.1f}%, slot is first fit {100*c['LB_slot_is_first_fit']/lb:.1f}%")
    for ids in KINDS[1:]:
        key = "+".join(ids)
        m = max(c[f"{key}|n"], 1)
        extra = f" seq_empty {100*c[f'{key}|seq_empty']/m:.1f}%" if f"{key}|seq_empty" in c else ""
        print(
            f"  {key:6s} empty {100*c[f'{key}|empty']/m:5.1f}%  path differs from I0 {100*c[f'{key}|path_differs_from_I0']/m:5.1f}%  "
            f"I0 choice admissible {100*c[f'{key}|I0_choice_admissible']/m:5.1f}%  |allowed| 0/1/2/3+: "
            f"{c[f'{key}|n_allowed_0']}/{c[f'{key}|n_allowed_1']}/{c[f'{key}|n_allowed_2']}/{c[f'{key}|n_allowed_3']}{extra}"
        )
