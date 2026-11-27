"""Owning runtime of the credential-free private review qualification."""

import importlib.metadata

import static_evaluator

PYTHON = '3.13.18'
RETAINED_LOCK = 'de37abd87a5603daf2d253ec450f200eab0530ae4b03c852cb2de32e7178142b'
LOCK = '09f7411cde907ab8b7c2b0b377bc40f6fe3112320863d7d5525eb4e86d753f73'
OPENAI_VERSION = '3.60.0'
PYDANTIC_VERSION = '2.14.4'
PINS = {'openai': OPENAI_VERSION, 'pydantic': PYDANTIC_VERSION, 'skillevaluator': static_evaluator.VERSION}
RETAINED_121 = 'review-121-v1'
SDK3_PROFILES = ('active', 'review-121-v2')
RETAINED_OVERLAY = {'openai': '2.54.0', 'pydantic': '2.14.3', 'certifi': '2026.10.23',
                    'pydantic-core': '2.50.4', 'typing-inspection': '0.4.5', 'httpx': '0.28.1'}
OVERLAY = {**RETAINED_OVERLAY, **PINS, 'pydantic-core': '2.50.5',
           'httpx2': '2.16.2', 'httpcore2': '2.16.2'}


def owner(profile):
    return static_evaluator.VERSIONS if profile in (*SDK3_PROFILES, RETAINED_121) else static_evaluator.RETAINED


def validator_pins(profile='active'):
    pins = OVERLAY if profile in SDK3_PROFILES else RETAINED_OVERLAY
    return {**pins, 'skillevaluator': owner(profile)['skillevaluator']}


def validate_install(profile='active'):
    static_evaluator.validate_install(python=PYTHON, owner=owner(profile))
    expected = validator_pins(profile)
    if {name: importlib.metadata.version(name) for name in expected} != expected:
        raise ValueError('Unexpected private review dependency overlay')
    try:
        importlib.metadata.version('harbor')
    except importlib.metadata.PackageNotFoundError:
        return
    raise ValueError('Private review environment must exclude Harbor')
