"""Optical Networking Gym environment for this project (the ``jocn_benchmark`` scenario).

Every script builds its environment through :func:`build_env`, so all of them share the same
scenario and the memory fix below. Per SPEC section 2 only ``load`` and ``seed`` vary.
"""

from __future__ import annotations

import numpy as np
from optical_networking_gym import build_scenario
from optical_networking_gym.defaults import resolve_topology, set_topology_dir
from optical_networking_gym.envs.optical_env import OpticalEnv
from optical_networking_gym.network.topology import TopologyModel
from optical_networking_gym.runtime.action_codec import decode_action, encode_action, reject_action
from optical_networking_gym.runtime.request_analysis import RequestAnalysis

from view import Choice, PathView, RequestView

SCENARIO = "jocn_benchmark"
TEACHER = "jocn_ls_bm_ksp"  # select_jocn_ls_bm_ksp_action, the paper's BM-LS-KSP
BASELINE = "first_fit"  # masked first fit: path, then most efficient modulation, then first slot


class ProvisioningEnv(OpticalEnv):
    """``OpticalEnv`` whose request-analysis cache does not grow during an episode.

    ONG (commit f7c4491) caches each ``RequestAnalysis`` under a key that includes the
    allocation-state version and clears the cache only on a full reset, so memory grows by about
    0.28 MB per request (≈ 0.9 GB for a 3,000-request episode). Entries from earlier versions
    can never be hit again. Within a step ONG builds the same analysis several times (simulator,
    action mask, observation) and those hits still happen, because we clear only after the step
    returns. The pending request's analysis stays reachable as ``simulator.current_analysis``.
    """

    def step(self, action: int):
        result = super().step(action)
        self.simulator.analysis_engine.clear_cache()
        return result


def build_env(
    load: float,
    seed: int,
    episode_length: int,
    env_class: type[OpticalEnv] = ProvisioningEnv,
    topology: str | None = None,
    **env_kwargs,
) -> OpticalEnv:
    """The ``jocn_benchmark`` preset at ``load`` (Erlang) and ``seed``, built like ONG's ``make_env``.

    ``env_class`` lets the data generator pass its own subclass (which should derive from
    :class:`ProvisioningEnv` to keep the memory fix); ``env_kwargs`` go to its constructor.
    ``topology`` replaces the preset's nobel-eu by another topology shipped with ONG; everything
    else of the preset is kept (used only for the unseen-topology probe of ``transfer.py``).
    """
    other = {"topology_id": topology} if topology else {}
    config = build_scenario(
        SCENARIO, load=float(load), seed=int(seed), episode_length=int(episode_length), **other
    )
    if config.topology_dir is not None:
        set_topology_dir(config.topology_dir)
    topology = TopologyModel.from_file(
        resolve_topology(config.topology_id),
        topology_id=config.topology_id,
        k_paths=config.k_paths,
        max_span_length_km=config.max_span_length_km,
        default_attenuation_db_per_km=config.default_attenuation_db_per_km,
        default_noise_figure_db=config.default_noise_figure_db,
    )
    return env_class(config, topology, episode_length=config.episode_length, **env_kwargs)


def _valid_starts(analysis: RequestAnalysis) -> np.ndarray:
    """Boolean ``[path, modulation offset, slot]``: resource- and QoT-valid start slots."""
    return np.asarray(analysis.qot_valid_starts, dtype=bool) & np.asarray(
        analysis.resource_valid_starts, dtype=bool
    )


def _offsets_by_efficiency(analysis: RequestAnalysis) -> list[int]:
    """Modulation offsets, most efficient first (the order ONG's heuristics use)."""
    modulations = analysis.config.modulations
    indices = analysis.modulation_indices
    return sorted(range(len(indices)), key=lambda o: (-int(modulations[indices[o]].spectral_efficiency), o))


def view_from_analysis(analysis: RequestAnalysis) -> RequestView:
    """The policy-facing summary of the pending request (see ``view.py``)."""
    valid = _valid_starts(analysis)
    order = _offsets_by_efficiency(analysis)
    modulations = analysis.config.modulations
    paths = []
    for p, record in enumerate(analysis.paths):
        best = next((o for o in order if valid[p, o].any()), None)
        fields = {"modulation": None, "slots_needed": None, "blocks": ()}
        if best is not None:
            required = analysis.required_slots_by_path_mod[p]
            needed = int(required[best])
            # Starts valid with any format that needs the same number of slots as the best one.
            same_width = [o for o in order if int(required[o]) == needed]
            starts = np.flatnonzero(valid[p, same_width].any(axis=0))
            runs = np.split(starts, np.flatnonzero(np.diff(starts) > 1) + 1)
            fields = {
                "modulation": modulations[analysis.modulation_indices[best]].name,
                "slots_needed": needed,
                "blocks": tuple((int(run[0]), int(run[-1] - run[0]) + needed) for run in runs),
            }
        paths.append(
            PathView(
                index=p,
                nodes=tuple(record.node_names),
                km=round(record.length_km),
                free_slots=int(np.count_nonzero(analysis.common_free_masks[p])),
                **fields,
            )
        )
    first = analysis.paths[0]
    return RequestView(
        source=first.node_names[0],
        destination=first.node_names[-1],
        bit_rate=int(analysis.request.bit_rate),
        num_slots=int(analysis.config.num_spectrum_resources),
        free_ratio=round(float(analysis.free_slots_ratio), 2),
        paths=tuple(paths),
    )


def action_from_choice(analysis: RequestAnalysis, choice: Choice) -> int | None:
    """ONG action for a choice, using the most efficient modulation valid at that path and slot.

    Returns ``None`` when the choice is not a valid action (SPEC section 4: counted as invalid).
    """
    if choice is None:
        return reject_action(analysis.config)
    path, slot = choice
    valid = _valid_starts(analysis)
    if not (0 <= path < len(analysis.paths) and 0 <= slot < valid.shape[2]):
        return None
    for offset in _offsets_by_efficiency(analysis):
        if valid[path, offset, slot]:
            return encode_action(
                analysis.config, path_index=path, modulation_offset=offset, initial_slot=slot
            )
    return None


def choice_from_action(analysis: RequestAnalysis, action: int) -> Choice:
    """The (path, slot) of an ONG action; ``None`` for the reject action."""
    decoded = decode_action(analysis.config, int(action))
    return None if decoded is None else (int(decoded.path_index), int(decoded.initial_slot))
