"""Owning runtime of the credential-free private review qualification."""

import importlib.metadata

import static_evaluator

PYTHON = '3.13.18'
LOCK = 'de37abd87a5603daf2d253ec450f200eab0530ae4b03c852cb2de32e7178142b'
OPENAI_VERSION = '2.54.0'
PYDANTIC_VERSION = '2.14.3'
PINS = {'openai': OPENAI_VERSION, 'pydantic': PYDANTIC_VERSION, 'skillevaluator': static_evaluator.VERSION}
OVERLAY = {**PINS, 'certifi': '2026.10.23', 'pydantic-core': '2.50.4',
           'typing-inspection': '0.4.5', 'httpx': '0.28.1'}


def validator_pins(*, retained=False):
    owner = static_evaluator.RETAINED if retained else static_evaluator.VERSIONS
    return {**OVERLAY, 'skillevaluator': owner['skillevaluator']}


def validate_install(*, retained=False):
    owner = static_evaluator.RETAINED if retained else static_evaluator.VERSIONS
    static_evaluator.validate_install(python=PYTHON, owner=owner)
    expected = validator_pins(retained=retained)
    if {name: importlib.metadata.version(name) for name in expected} != expected:
        raise ValueError('Unexpected private review dependency overlay')
    try:
        importlib.metadata.version('harbor')
    except importlib.metadata.PackageNotFoundError:
        return
    raise ValueError('Private review environment must exclude Harbor')
