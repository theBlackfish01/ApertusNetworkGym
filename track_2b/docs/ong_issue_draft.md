# Issue for Optical Networking Gym

To post at <https://github.com/carlosnatalino/optical-networking-gym/issues/new>. Not sent yet.
The title is the line under "Title"; the description is everything under "Description"
(paragraphs are on one line each, because GitHub keeps line breaks in an issue).
Measured on 2026-10-09 at commit `f7c4491` (WSL2 Ubuntu 24.04, Python 3.12, compiled kernels).
Checked again on 2026-10-12: `f7c4491` is still the head of the repository, no existing issue
covers this, and the script gives 58 MB at the start and 615 MB after 2,000 requests.

## Title

Request-analysis cache grows without bound during an episode (about 0.28 MB per request)

## Description

Found at commit `f7c4491` (current `main`), Python 3.12 on Ubuntu 24.04 (WSL2), compiled kernels.

**Summary**

`RequestAnalysisEngine` keeps every `RequestAnalysis` it builds in `_analysis_cache` and only clears it on a full reset. The cache key includes `state.allocation_state_version`, which changes with every allocation and release, so entries from earlier versions can never be hit again, but they stay referenced together with their arrays. Memory grows linearly with the number of requests, independent of how many services are active.

**Measurement**

`jocn_benchmark`, load 270, seed 1, BM-LS-KSP driving the episode; resident memory of the process:

| Requests | 0 | 250 | 500 | 750 | 1,000 | 1,500 | 2,000 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RSS, MB | 59 | 132 | 202 | 272 | 341 | 478 | 616 |

Active services level off around 260 while memory keeps growing by about 0.28 MB per request (roughly 0.9 GB for a 3,000-request episode). With several environments in parallel this exhausted an 8 GB machine.

**Reproduction**

```python
from optical_networking_gym import make_env
from optical_networking_gym.heuristics import select_heuristic_action

def rss_mb():
    for line in open("/proc/self/status"):
        if line.startswith("VmRSS"):
            return int(line.split()[1]) // 1024

env = make_env(scenario="jocn_benchmark", load=270.0, seed=1, episode_length=3000)
_, info = env.reset(seed=1)
print(0, rss_mb(), "MB")
for i in range(1, 2001):
    _, _, _, _, info = env.step(select_heuristic_action("jocn_ls_bm_ksp", env, info))
    if i % 250 == 0:
        cache = env.simulator.analysis_engine._analysis_cache
        print(i, rss_mb(), "MB", len(cache), "cached analyses")
```

The cache holds one more analysis after every request (251 after 250 requests, 2,001 after 2,000).

**Cause**

`runtime/request_analysis.py`, `RequestAnalysisEngine.build`: the key is `(state.state_id, state.allocation_state_version, source, destination, bit_rate, needs_inspection)` and nothing evicts. `clear_cache()` is called from the simulator only in `_apply_runtime_config`, that is on reset. `tracemalloc` attributes the growth to the arrays created in `_build_analysis` and `_build_path_slot_features`, and `gc.get_referrers` on an old analysis leads to that dict.

**Possible fixes**

- Drop all entries whenever `(state_id, allocation_state_version)` differs from the last one seen. The cache then only serves the repeated builds for the pending request, which is what it is used for within a step (simulator, action mask, observation).
- Or keep a single entry, or a small LRU.

**Workaround**

Clearing the cache after every `step()` in a subclass of `OpticalEnv`:

```python
from optical_networking_gym.envs.optical_env import OpticalEnv

class Env(OpticalEnv):
    def step(self, action):
        result = super().step(action)
        self.simulator.analysis_engine.clear_cache()
        return result
```

Over 800 requests with first fit and with BM-LS-KSP this produced the same actions and the same blocking as the unmodified environment, at the same speed, with flat memory.

Happy to open a pull request with the first fix if that is useful.
