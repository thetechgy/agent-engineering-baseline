"""Restore authenticated private-review validator snapshots for fixture tests."""

from pathlib import Path
import copy
import zipfile

import skill_evidence as evidence
import skill_report_reviews as attachments

FIXTURE = Path(__file__).parent / 'fixtures/skill_report_reviews/historical-modules.zip'
PARITY = FIXTURE.with_name('retirement-parity.zip')
PARITY_DIGEST = 'sha256:448de8e1c8b5a749f43e93af0d1049c1962aff8b845bb9adc8e016c413158e19'
PESTER_PARITY = FIXTURE.with_name('retirement-pester-parity.zip')
PESTER_PARITY_DIGEST = 'sha256:2d671322550a381e25becbc9ebb8b97cd144c8a8a6607d3256a45e0f577eb6ce'
PESTER_RECORD = 'public/skills/powershell-pester-6/behavioral/synthetic-control/public-report.json'


def parity_archive(*, pester=False):
    path, digest = (PESTER_PARITY, PESTER_PARITY_DIGEST) if pester else (PARITY, PARITY_DIGEST)
    evidence.require(evidence.digest_bytes(path.read_bytes()) == digest,
                     'Retained review fixture digest mismatch')
    return zipfile.ZipFile(path)


def restore_parity_case(test, archive, root, *, key=None):
    catalog = evidence.parse_json(archive.read('catalog.json'))
    expected = catalog[key] if key else catalog
    prefix = key + '/' if key else ''
    for member in archive.namelist():
        if member == 'catalog.json' or not member.startswith(prefix):
            continue
        name = member.removeprefix(prefix)
        evidence.relative(name)
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(archive.read(member))
    spec = copy.deepcopy(expected['attachment'])
    frozen_tooling(test, root / 'tooling', spec['profile'])
    for name in ('review', 'analysis', 'source', 'support', 'selection', 'tooling'):
        if spec[name] is not None:
            spec[name] = str(root / spec[name])
    spec['inputs'] = [str(root / name) for name in spec['inputs']]
    path = root / 'attachment.json'
    path.write_bytes(evidence.encoded(spec))
    return spec, path, expected


def frozen_tooling(test, tooling, profile):
    """Restore the exact retained validator and data named by a profile."""
    scripts = tooling / '.github/scripts'; scripts.mkdir(parents=True)
    archive_path = (FIXTURE.with_name('review-runtime-v2-modules.zip') if profile == 'current-v5' else
                    FIXTURE.with_name('pester-packaging-modules.zip') if profile == 'current-v4' else
                    FIXTURE.with_name('review-runtime-modules.zip') if profile == 'current-v3' else FIXTURE)
    with zipfile.ZipFile(archive_path) as archive:
        for name, expected in zip(attachments.MODULES, attachments.PROFILES[profile][1]):
            raw = archive.read(expected + '.py')
            test.assertEqual(evidence.digest_bytes(raw), 'sha256:' + expected)
            (scripts / name).write_bytes(raw)
        if profile in attachments.REGISTRY_DIGESTS:
            digest = attachments.REGISTRY_DIGESTS[profile]
            if profile == 'custom-metrics-v3':
                with zipfile.ZipFile(FIXTURE.with_name('refresh-95-registry.zip')) as refreshed:
                    asset = refreshed.read(digest + '.json')
            else:
                asset = archive.read(digest + '.json')
            test.assertEqual(evidence.digest_bytes(asset), 'sha256:' + digest)
            registry = tooling / '.github/evals/custom-metrics.json'
            registry.parent.mkdir()
            registry.write_bytes(asset)
        for member, digest in attachments.SUPPORT_FILES.get(profile, {}).items():
            data = archive.read(digest + Path(member).suffix)
            test.assertEqual(evidence.digest_bytes(data), 'sha256:' + digest)
            target = tooling / member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return scripts
