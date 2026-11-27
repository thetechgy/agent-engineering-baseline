# Podman case 2 decision rule

Compare the current Podman skill with matched no skill on case 2. Run one
serial pair of three attempts per arm on GPT-6.2 Sol at High with Codex
CLI 0.172.0. The two arms get the same prompt and input files. The current
arm also gets the deployed skill.

A pass requires a submitted PostgreSQL 18 Quadlet whose effective database
directory is covered by persistent storage. A measured grade of zero is a
task failure. Keep invalid, unsupported and operational failures separate.
If the run stops before both arms have three measured grades, record the
stop and the available grades.

| Current | No skill | Decision |
| --- | --- | --- |
| 3/3 | 3/3 | Keep the skill. This case does not separate the arms on this runtime. |
| At least 2/3 | At most 1/3 | The skill helped on this case in this pair. |
| At most 1/3 | At least 2/3 | The skill may be hurting on this case. Investigate. |
| 0/3 | 0/3 | Record a shared failure as its own finding. |
| Any other complete split | | Allow one separately approved repeat. Record inconclusive if it does not resolve the result. |

The cases were written alongside the skill. One case and three attempts per
arm give limited evidence about skill effectiveness. In two earlier
benchmarks on GPT-5.6 Sol with Codex CLI 0.155.1, both arms corrected the
case 2 mount. That result concerns generated configuration. Database startup
and persistence across restarts are outside this check.
[Earlier case 2 review](https://github.com/thetechgy/agent-engineering-baseline/pull/160).

The protocol records the decision rule digest. Preparation and fresh
inspection use the exact revision. Any model run or repeat requires a separate
allocation approved by the owner and approval of its matching
`skill-benchmark` environment gate.
