window.BENCHMARK_DATA = {
  "lastUpdate": 1793132222374,
  "repoUrl": "https://github.com/thetechgy/agent-engineering-baseline",
  "entries": {
    "Agent skill benchmark (standard)": [
      {
        "commit": {
          "author": {
            "name": "Travis McDade",
            "username": "thetechgy",
            "email": "mcdade.travis@gmail.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "21242feb817ec76ad3ff2674ff6b7b4171196733",
          "message": "feat(evals): add change-aware and recurring evaluation orchestration (#102)\n\n* feat(evals): orchestrate change-aware and recurring benchmarks\n\n* fix(evals): recheck main after postapproval assessment\n\n* fix(evals): retain successful qualification attempts across reruns\n\n* fix(evals): reuse validated main evidence before benchmark approval\n\n* fix(evals): distinguish skipped dispatch from uncertain execution",
          "timestamp": "2026-10-27T19:22:56Z",
          "url": "https://github.com/thetechgy/agent-engineering-baseline/commit/21242feb817ec76ad3ff2674ff6b7b4171196733"
        },
        "date": 1793132220997,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Skill Lift",
            "value": 0.0593,
            "unit": "score",
            "extra": "Dataset sha256:cecc0bcea480a3c197e1b4c527009958ada3be67eb0205325f6c16123f9355fe; policy ef7784e6ab747c2b"
          },
          {
            "name": "Effectiveness",
            "value": 0.717,
            "unit": "score",
            "extra": "Dataset sha256:cecc0bcea480a3c197e1b4c527009958ada3be67eb0205325f6c16123f9355fe; policy ef7784e6ab747c2b"
          },
          {
            "name": "Correctness",
            "value": 0.84,
            "unit": "score",
            "extra": "Dataset sha256:cecc0bcea480a3c197e1b4c527009958ada3be67eb0205325f6c16123f9355fe; policy ef7784e6ab747c2b"
          },
          {
            "name": "Discoverability",
            "value": 0.6875,
            "unit": "score",
            "extra": "Dataset sha256:cecc0bcea480a3c197e1b4c527009958ada3be67eb0205325f6c16123f9355fe; policy ef7784e6ab747c2b"
          }
        ]
      }
    ]
  }
}