"""Reviewed registration for campaign extensions and current source selection."""

from dataclasses import dataclass
from pathlib import Path
import re

from evaluation_campaign_core import require
import skill_reports as reports

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = '.github/evals/campaign-onboarding.json'
LEGACY_SELECTIONS = ('.github/evals/campaigns/selections-sol62.json',
                     '.github/evals/campaigns/selections-1710-sol62.json')


def registered_file(workspace, member):
    path = workspace / member
    require(path.resolve() == path and path.is_relative_to(workspace) and path.is_file(),
            'Unsafe campaign registration member')
    return path


def registration(workspace=ROOT):
    value = reports.read_json(registered_file(workspace, REGISTRATION))
    require(type(value) is dict and set(value) == {'version', 'current_source', 'current_effectiveness', 'families'}
            and type(value['version']) is int and value['version'] == 1, 'Campaign registration version')
    source = value['current_source']
    require(type(source) is int and 53 <= source <= 999, 'Invalid current campaign source version')
    effectiveness = value['current_effectiveness']
    require(type(effectiveness) is str and re.fullmatch(r'pester-effectiveness-v[0-9]+', effectiveness),
            'Invalid current effectiveness profile')
    families = value['families']
    require(type(families) is list and len(families) <= 64
            and all(type(member) is str and re.fullmatch(
                r'\.github/evals/[a-z0-9-]+(?:/[a-z0-9-]+)?/onboarding\.json', member) for member in families)
            and len(set(families)) == len(families), 'Invalid campaign family paths')
    return value


def current_source(workspace=ROOT):
    return registration(workspace)['current_source']


@dataclass(frozen=True)
class Family:
    member: str
    skill: str
    adapter: str
    class_name: str
    dataset: str
    source_fixtures: tuple[str, ...]
    registry: Path
    selections: dict
    definitions: frozenset[str]
    definition_ids: frozenset[str]


def task_families(workspace=ROOT):
    result = {}
    claimed = set()
    claimed_definitions = set()
    for member in registration(workspace)['families']:
        path = registered_file(workspace, member)
        folder = path.parent.relative_to(workspace)
        spec = reports.read_json(path)
        require(type(spec) is dict and set(spec) == {'adapter', 'class', 'dataset', 'source_fixtures'},
                'Invalid task family registration')
        skill = folder.parts[2]
        require(skill != 'campaigns', 'Task families require a skill-owned directory')
        adapter = spec['adapter']
        class_name = spec['class']
        require(type(adapter) is str and re.fullmatch(r'[a-z0-9-]+', adapter)
                and adapter not in result, 'Invalid or duplicate task family adapter')
        require(type(class_name) is str and class_name.isidentifier(), 'Invalid task adapter class')
        dataset = spec['dataset']
        require(type(dataset) is str and re.fullmatch(r'[a-z0-9-]+\.json', dataset), 'Invalid campaign dataset')
        dataset = (folder / dataset).as_posix()
        fixtures = spec['source_fixtures']
        require(type(fixtures) is list and len(fixtures) <= 64
                and all(type(item) is str and re.fullmatch(r'(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_.-]+', item)
                        and item not in ('.', '..') for item in fixtures)
                and len(set(fixtures)) == len(fixtures), 'Invalid campaign source fixtures')
        fixtures = tuple(f'.apm/skills/{skill}/evals/{item}' for item in fixtures)
        registry = registered_file(workspace, folder / 'selections.json')
        choices = reports.read_json(registry)
        require(type(choices) is dict and set(choices) == {'version', 'campaigns'}
                and type(choices['version']) is int and choices['version'] == 1, 'Task selection registry version')
        rows = choices['campaigns']
        require(type(rows) is dict and 0 < len(rows) <= 128, 'Invalid task selection registry')
        definitions = set()
        for identity, row in rows.items():
            require(re.fullmatch(r'[a-z0-9-]+', identity) and identity not in claimed,
                    'Invalid or duplicate campaign selection')
            claimed.add(identity)
            require(type(row) is dict and set(row) == {'definition', 'controls', 'producers'}
                    and type(row['controls']) is list and 0 < len(row['controls']) <= 64
                    and type(row['producers']) is list, 'Invalid task selection')
            for definition in [row['definition'], *row['controls']]:
                require(type(definition) is str and Path(definition).parent == folder
                        and re.fullmatch(r'[a-z0-9-]+\.json', Path(definition).name)
                        and definition == Path(definition).as_posix(), 'Unregistered definition path')
                registered_file(workspace, definition)
                definitions.add(definition)
        identities = {}
        for definition in definitions:
            value = reports.read_json(workspace / definition)
            identity = value.get('id')
            require(type(identity) is str and re.fullmatch(r'[a-z0-9-]+', identity)
                    and identity not in claimed_definitions, 'Invalid or duplicate task definition identity')
            claimed_definitions.add(identity)
            identities[identity] = definition
        require(all(identities.get(identity) == row['definition'] for identity, row in rows.items()),
                'Selection/definition mismatch')
        result[adapter] = Family(member, skill, adapter, class_name, dataset, fixtures, registry, rows,
                                 frozenset(definitions), frozenset(identities))
    return result


def family_for_definition(workspace, member):
    return next((family for family in task_families(workspace).values() if member in family.definitions), None)
