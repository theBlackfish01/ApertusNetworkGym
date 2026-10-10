"""The project env must match ONG's make_env decisions and keep its analysis cache bounded."""

from optical_networking_gym import make_env
from optical_networking_gym.heuristics import select_heuristic_action

from sim import SCENARIO, TEACHER, build_env


def test_build_env_matches_make_env_and_clears_cache():
    reference = make_env(scenario=SCENARIO, load=270.0, seed=4, episode_length=40)
    ours = build_env(270.0, 4, episode_length=40)
    _, info_ref = reference.reset(seed=4)
    _, info_ours = ours.reset(seed=4)
    for _ in range(40):
        action = select_heuristic_action(TEACHER, reference, info_ref)
        assert select_heuristic_action(TEACHER, ours, info_ours) == action
        _, _, _, _, info_ref = reference.step(action)
        _, _, _, _, info_ours = ours.step(action)
        assert len(ours.simulator.analysis_engine._analysis_cache) == 0
    assert len(reference.simulator.analysis_engine._analysis_cache) > 1  # the upstream growth we work around
    assert (
        ours.simulator.statistics.snapshot().episode_service_blocking_rate
        == reference.simulator.statistics.snapshot().episode_service_blocking_rate
    )


def test_view_blocks_are_valid_actions_and_teacher_tracks_ong():
    from intents import NO_INTENT, teacher_choice
    from sim import action_from_choice, choice_from_action, view_from_analysis

    env = build_env(390.0, 5, episode_length=260)
    _, info = env.reset(seed=5)
    agree = total = 0
    for step in range(260):
        analysis = env.simulator.current_analysis
        action = select_heuristic_action(TEACHER, env, info)
        if step >= 200:
            view = view_from_analysis(analysis)
            mask = env.action_masks()
            for path in view.paths:
                assert path.feasible == bool(path.blocks)
                for start, length in path.blocks:
                    for slot in (start, start + length - path.slots_needed):  # both ends of the block
                        encoded = action_from_choice(analysis, (path.index, slot))
                        assert encoded is not None and mask[encoded]
                        assert choice_from_action(analysis, encoded) == (path.index, slot)
            assert (
                action_from_choice(analysis, (0, 400)) is None
                and action_from_choice(analysis, (7, 0)) is None
            )
            assert choice_from_action(analysis, action_from_choice(analysis, None)) is None
            ours = teacher_choice(view, NO_INTENT)
            assert action_from_choice(analysis, ours) is not None
            agree += ours == choice_from_action(analysis, action)
            total += 1
        _, _, _, _, info = env.step(action)
    assert agree >= total - 1  # ONG's BM-LS-KSP differs only when a wider format fits at a lower slot
