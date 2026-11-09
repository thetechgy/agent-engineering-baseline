"""Adapter-owned runtime/model validation and matched native APM deployment."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess

from evaluation_campaign_core import require

ROOT = Path(__file__).resolve().parents[2]


def read_profile(path, validators=None):
    import skill_reports as reports
    value = reports.read_json(path)
    adapters = {'codex': validate_codex} if validators is None else validators
    adapter = value.get('adapter')
    require(adapter in adapters, 'Unsupported runtime adapter: ' + str(adapter) + '; claude-code and copilot are extension targets only')
    # The owning adapter validates its complete model/provider/configuration tuple.
    resolved = adapters[adapter](value)
    return {'profile': value, 'resolved': resolved}


def validate_codex(value):
    import skill_reports as reports
    from codex_pilot_contract import PROFILE
    require(set(value) == {'id', 'adapter', 'frozen_profile', 'frozen_profile_sha256', 'capabilities', 'inference_enabled'},
            'Unsupported Codex profile settings')
    require(value['frozen_profile'] == '.github/evals/codex-pilot.json' and
            value['frozen_profile_sha256'] == hashlib.sha256((ROOT / value['frozen_profile']).read_bytes()).hexdigest(),
            'Qualified Codex profile drift')
    require(value['inference_enabled'] is False and value['capabilities'] == ['oracle', 'non-forwarding-cli-probe'],
            'Unsupported Codex capabilities or inference setting')
    return dict(PROFILE, agent='codex')



def adapter_for(runtime):
    from importlib import import_module
    modules = {'codex': 'evaluation_codex'}
    name = runtime['profile']['adapter']
    require(name in modules, 'Unsupported runtime adapter: ' + name)
    return import_module(modules[name])
