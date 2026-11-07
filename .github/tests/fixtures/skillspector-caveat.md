# SkillSpector missing-reference control

`skillspector-caveat-response.json` is an actual SkillSpector 2.13.4 response
from released source `54824463814a0be01360792523ec7245a69190fc`, using the
scanner lock retained in this repository. Its input is the adjacent
`skillspector-caveat/SKILL.md.txt` (unchanged scanner input bytes, stored as data
so documentation lint does not interpret its deliberate control payload).
Run from this directory:

```sh
fixture_dir=$(mktemp -d)
cp skillspector-caveat/SKILL.md.txt "$fixture_dir/SKILL.md"
skillspector scan "$fixture_dir" --format json --no-llm
```

This is a synthetic input, not an actual repository skill scan. The producer
emits P2 at `SKILL.md:7`, YR4 at `SKILL.md:3`, and a missing-reference caveat at
`SKILL.md:6`. The command exits 0; process success does not erase the findings.
The original response SHA-256 is
`8ebe7e903e0ee9d0b88f5e7c82dc9bd439d6f2203d44d4ff4b90215e79da4b23`.
Only `skill.source`, an absolute local path, is replaced with `<fixture>` in
the committed copy. No completion flags, counts, findings, locations or ledger
entries are changed. The sanitized response SHA-256 is
`b4c7e383470b531df1480a04d923055becd1782507a59fb700d2b205efd82e71`.
The original response remains in retained qualification evidence.

`qualify_scanner_caveats.py` proves rejection by the pristine retained adapter,
then finding preservation and conservative coverage through the patched adapter.
Its mutations are explicitly synthetic negative controls. Separately, its
before/after catalog execution scans unchanged installed repository skills,
validates their datasets and projects them through the existing report path.
