"""Owning runtime of the credential-free private review qualification."""

import importlib.metadata

import static_evaluator

PYTHON = '3.13.18'
LOCK = 'ddb43ba1bd0ea29ddaba65548b033facaf1972f2783a4ab7c9bbc440640f0c93'
OPENAI_VERSION = '2.54.0'
PYDANTIC_VERSION = '2.14.3'
PINS = {'openai': OPENAI_VERSION, 'pydantic': PYDANTIC_VERSION, 'skillevaluator': static_evaluator.VERSION}
OVERLAY = {**PINS, 'certifi': '2026.10.23', 'pydantic-core': '2.50.4',
           'typing-inspection': '0.4.5', 'httpx': '0.28.1'}


def validate_install():
    static_evaluator.validate_install(python=PYTHON)
    if {name: importlib.metadata.version(name) for name in OVERLAY} != OVERLAY:
        raise ValueError('Unexpected private review dependency overlay')
    try:
        importlib.metadata.version('harbor')
    except importlib.metadata.PackageNotFoundError:
        return
    raise ValueError('Private review environment must exclude Harbor')
