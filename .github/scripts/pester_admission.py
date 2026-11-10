"""Versioned Pester expression admission; no scoring or runtime changes."""
from codex_pilot_effectiveness import runner_bytes as previous_runner, execution_profile_bytes as previous_document

POLICY = 'pester-collection-numeric-v1'
# PowerShell numeric accelerators plus their exact CLR names. These are type
# tests only: no new casts, constructors, static access or method invocation.
NUMERIC_TYPES = ('sbyte', 'byte', 'short', 'int16', 'ushort', 'uint16',
    'int', 'int32', 'uint', 'uint32', 'long', 'int64', 'ulong', 'uint64',
    'single', 'float', 'double', 'decimal', 'bigint',
    'System.SByte', 'System.Byte', 'System.Int16', 'System.UInt16',
    'System.Int32', 'System.UInt32', 'System.Int64', 'System.UInt64',
    'System.Single', 'System.Double', 'System.Decimal', 'System.Numerics.BigInteger')


def runner_bytes():
    source = previous_runner().decode()
    old = "$__pePolicy.properties -notcontains $__peNode.Member.Value"
    assert source.count(old) == 1
    source = source.replace(old, "(@($__pePolicy.properties) + @('Count', 'Length')) -notcontains $__peNode.Member.Value")
    old = "if ($__peNode.TypeName.FullName -notin @('int',"
    assert source.count(old) == 1
    names = ', '.join("'" + name + "'" for name in NUMERIC_TYPES)
    # The complete FindAll walk inspects the operand and all nested expressions.
    # Type tests must use a literal type on the right side of -is or -isnot.
    extra = """$__peNumericTest = $__peKind -eq 'TypeExpressionAst' -and
                    $__peNode.Parent -is [System.Management.Automation.Language.BinaryExpressionAst] -and
                    $__peNode.Parent.Operator -in @('Is', 'IsNot') -and
                    $__peNode.Parent.Right -eq $__peNode -and
                    $__peNode.TypeName.FullName -in @(""" + names + """)
                if (-not $__peNumericTest -and $__peNode.TypeName.FullName -notin @('int',"""
    source = source.replace(old, extra)
    return source.encode()


def execution_profile_bytes():
    return previous_document() + b"\nSuccessor expression admission: pester-collection-numeric-v1 (output-informed). Literal instance Count and Length reads are supported, subject to recursive operand inspection. Numeric -is/-isnot tests support the fixed PowerShell integer, floating-point, decimal and BigInteger accelerators and their CLR names. No additional casts, arbitrary types/members, dynamic/static access, methods, reflection or member/index writes are admitted. This successor does not change historical profiles or establish task correctness.\n"
