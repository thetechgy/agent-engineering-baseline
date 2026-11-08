# Pilot iteration admission: pester-cli-pilot-external-v4

This version corrects the bounded pilot evaluator after inspection of the two
unchanged submissions from live run 42448389611. It is not a prospectively frozen
validation of those outputs. Original v3 outcomes remain `unsupported/ast_kind`,
with correctness, reference pass and mutation detection unmeasured.

The shared production runner, task requirements, subject, reference, mutants,
metric definitions, scoring, dependency pins and verifier isolation are unchanged.
The new pilot profile has distinct grader and producer identities. Older profiles
remain registered with their original identities and require their retained
source snapshots for native reprojection.

## Supported iteration and mutation

The complete recursive AST walk inspects every initializer, condition, iterator
and body expression, including nested script blocks and unreachable expressions.
`for` and the previously supported `foreach` use the same command, variable,
property, type, invocation and Pester restrictions. A loop never bypasses admission
of its children. Arbitrary commands, imports, functions, methods/reflection,
dynamic invocation, environment/provider access and framework configuration stay
unsupported, including inside any loop component.

Prefix/postfix `++` and `--` are admitted only when their operand is a plain
variable expression permitted by the existing variable policy. Bare variables
and explicit `local:`, `private:` or `script:` variables are supported. Splats,
forbidden scopes, reserved framework/control variables and names beginning `__`
remain forbidden. Mutation of `PSScriptRoot`, `true`, `false` or `null` is explicitly
rejected. Member/index targets, parenthesized targets and casts used as mutation
targets are unsupported. A cast of an increment expression's result does not
change its underlying plain-variable target.

Assignment targets retain the existing plain-variable requirement. No member or
index assignment is enabled. Mutation is not restricted to a particular counter
name, retained file, test case or literal value. All four increment/decrement
forms are qualified with independent counters and positive/failing assertions.

Loop components may be omitted, including `for (;;)`. Admission does not claim to
prove termination. The unchanged isolated verifier enforces CPU, memory, process
and wall limits. Exhaustion remains an unscoreable timeout; it does not become an
assertion failure or a measured zero.

## Supported types

The existing type subset remains `int`/`int32`, `bool`, `string`, `object`,
`object[]`, `pscustomobject`, `hashtable` and the existing ArgumentException /
ArgumentOutOfRangeException annotations. This version adds the signed 64-bit
integer aliases `long` and `int64`, consistent with the documented primitive-input
conversion contract. It does not admit arbitrary .NET types or invocation of
their members. Both aliases have independent controls; other type families stay
unsupported.

## Retrospective evidence

The immutable corpus lives outside skill packages and every live agent image
context. Source artifact 13605202225, run/attempt/revision, archive digest, both
submission digests and original public-record identity are checked before replay.
The trusted oracle only copies each original byte sequence to its own arm. The
same corrected offline verifier grades both arms, without model credentials,
inference, retries or judges. Native results identify the new evaluator version
and link the original outcomes, which are never overwritten or scored as zero.
The existing consolidated report shows original and retrospective results beside
each other, with the post-output-inspection limitation visible.

## Separate PATH qualification

The original image declares the pinned PowerShell directory on PATH, but the live
login shell did not resolve `pwsh`; the absolute binary executed successfully.
Independent before/after agent controls test login-shell lookup and the same
PowerShell 7.6.9 binary. A root-owned `/usr/local/bin/pwsh` symlink is the sole
operational correction. It changes neither executable bytes nor dependencies.
These PATH observations are separate from retrospective grades and do not
establish a skill weakness or benefit.
