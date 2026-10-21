#!/usr/bin/env python3
"""Private report attachments; exact original validators, never inference or approval."""

from dataclasses import dataclass
from datetime import datetime
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_analysis as analysis
import skill_evidence as evidence

require = evidence.require
LIMIT = 1024 * 1024
REPLY_LIMIT = 16 * LIMIT
MAX_ASSESSMENTS = 8
PINS = {'openai': '2.44.0', 'pydantic': '2.13.4', 'skillevaluator': '0.3.0'}
MODULES = ('skill_review.py', 'skill_analysis.py', 'skill_evidence.py', 'skill_reports.py')
# Reviewed source bytes, not commands or report-supplied executable identities.
PROFILES = {
    'current-v2': ('a5392b0eda37485b131ffe416fcb9d6e5ee547d2', (
        '778f26c48da2eb7811a895a8c6b4cc6f3d304262abbfbd86ee5e7bfa97102680',
        'b120aa5ed4d0f1d8267295ab79d4bc5bc05f9dd4a68e39e26131a61401a4d73f',
        '0cb9a970e0325d4212b53dbf3cc7a81a8ad01635109eba7bab9d5ac8d3af73ca',
        '850e7a5d78cf979800b1ca9053c8f9cabb4face1a081c9265a13e9ddb444d316')),
    'baseline-3f47c9d': ('3f47c9de4df362ae9977748ad6353227f403a9b8', (
        '778f26c48da2eb7811a895a8c6b4cc6f3d304262abbfbd86ee5e7bfa97102680',
        'b120aa5ed4d0f1d8267295ab79d4bc5bc05f9dd4a68e39e26131a61401a4d73f',
        '0cb9a970e0325d4212b53dbf3cc7a81a8ad01635109eba7bab9d5ac8d3af73ca',
        '9067eb9126ec0423b8471b8a7f8a7a2b17ab758650cb6937352b5a1ea67dc61a')),
    'podman-1cffcf9': ('1cffcf9947c265f126a3ceee75e5e35249bfd722', (
        'd7bb2414c2c7cc364ea880cddf21a2dc3f739f2fcbcc3c8261bb2877329d534a',
        'b120aa5ed4d0f1d8267295ab79d4bc5bc05f9dd4a68e39e26131a61401a4d73f',
        '0f63d7671743807225c100b64c56221ec62b8437b4ef0ab364791ebc171afc63',
        '51d83cf47b7f64902d1f186364cfafd40933f81afb01c786aa9c3c8d448d9e97')),
    'gh-89f46f0': ('89f46f026cdaaf001487cbcc1425204db29e8952', (
        '778f26c48da2eb7811a895a8c6b4cc6f3d304262abbfbd86ee5e7bfa97102680',
        'b120aa5ed4d0f1d8267295ab79d4bc5bc05f9dd4a68e39e26131a61401a4d73f',
        '0f63d7671743807225c100b64c56221ec62b8437b4ef0ab364791ebc171afc63',
        '51d83cf47b7f64902d1f186364cfafd40933f81afb01c786aa9c3c8d448d9e97')),
}

# Fixed launcher. -I ignores caller PYTHONPATH, user site and working-directory imports.
# Audit hooks restrict audited Python operations; they are NOT an OS sandbox.
RUNNER = r'''
import sys, json
from pathlib import Path

def restrict(event, args):
    if event.startswith('socket.') or event in (
        'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.spawn',
        'os.fork', 'os.forkpty', 'pty.spawn'):
        raise PermissionError('Offline validator operation rejected')
sys.addaudithook(restrict)
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import skill_review as review

try:
    request = json.loads(sys.stdin.buffer.read(1024 * 1024 + 1))
    capture = review.Capture()
    raw = capture.read(Path(request['review']), limit=review.REPORT_LIMIT)
    saved = review.evidence.parse_json(raw, limit=review.REPORT_LIMIT)
    markdown = capture.read(Path(request['review']).with_name('skill-review.md'), limit=review.REPORT_LIMIT)
    context = review.prepare([Path(p) for p in request['inputs']], Path(request['analysis']),
        request['skill'], request['record_id'],
        **{k: Path(request[k]) if request[k] is not None else None for k in ('source', 'support', 'selection')})
    validated = review.validate_review(saved, context)
    review.require(markdown == review.render_review(validated, context), 'Markdown mismatch')
    for guard in (*context.guards, capture.guard()):
        guard()
    response = review.evidence.encoded({
        'report': validated, 'records': context.value['records'],
        'review_digest': review.evidence.digest_bytes(raw),
        'markdown_digest': review.evidence.digest_bytes(markdown),
        'module_names': [Path(m.__file__).name for m in (review, review.analysis, review.evidence, review.evidence.reports)],
        'layout_valid': review.evidence.ROOT == Path(sys.argv[1]).parents[1] and all(
            Path(m.__file__).parent == Path(sys.argv[1])
            for m in (review, review.analysis, review.evidence, review.evidence.reports)),
    })
    review.require(len(response) <= 16 * 1024 * 1024, 'Validator response limit')
    sys.stdout.buffer.write(response)
except Exception:
    sys.exit(1)
'''


@dataclass(frozen=True)
class ValidatedReviews:
    """Transient validation witness. No persisted receipt is accepted as authority."""
    items: tuple
    roots: tuple
    guards: tuple
    seal: str

    def check(self, captured):
        require(evidence.identity(self.items) == self.seal, 'Attachment projection changed')
        analysis.check_capture(captured)
        seen = set()
        for item in self.items:
            rid = item['record_id']
            require(rid not in seen and rid in captured.records, 'Attachment record mismatch')
            seen.add(rid)
            require(captured.records[rid]['source']['skill_id'] == item['skill'], 'Attachment skill mismatch')
        for guard in self.guards:
            guard()


def locator(value, path):
    require(type(path) is list and len(path) <= 32, 'Invalid assessment locator')
    for key in path:
        require((type(value) is dict and type(key) is str and key in value) or
                (type(value) is list and type(key) is int and 0 <= key < len(value)), 'Missing assessment field')
        value = value[key]
    return value


def attachment_path(value, parent):
    require(type(value) is str and 0 < len(value) <= 4096, 'Invalid attachment path')
    path = Path(value)
    return path if path.is_absolute() else parent / path


def document(spec, parent, capture, *, structured=True):
    evidence.closed(spec, ('path', 'digest'))
    evidence.sha(spec['digest'])
    path = attachment_path(spec['path'], parent)
    raw = capture.read(path, limit=LIMIT)
    capture.roots.append(path.parent)
    require(evidence.digest_bytes(raw) == spec['digest'], 'Attachment document digest mismatch')
    return (evidence.parse_json(raw, limit=LIMIT) if structured else raw.decode('utf-8')), spec['digest']


def assessment(spec, parent, capture, report, review):
    evidence.closed(spec, ('author_kind', 'attribution', 'document', 'report_digest_locator',
                          'fields', 'narrative', 'rubric', 'rubric_locator', 'freeze'))
    require(spec['author_kind'] in ('independent_ai', 'human_supplied', 'unknown'), 'Invalid assessor category')
    require(type(spec['attribution']) is str and 0 < len(spec['attribution']) <= 200 and
            bool(spec['attribution'].strip()), 'Invalid assessor attribution')
    source, digest = document(spec['document'], parent, capture)
    require(locator(source, spec['report_digest_locator']) == report['review_digest'], 'Assessment report mismatch')
    fields = spec['fields']
    evidence.closed(fields, ('verdict', 'score', 'maximum', 'dimensions', 'limitations'))
    values = {k: None if v is None else locator(source, v) for k, v in fields.items()}
    require(type(values['verdict']) is str and 0 < len(values['verdict']) <= 8000 and
            bool(values['verdict'].strip()), 'Missing assessment verdict')
    score, maximum, dimensions = (values[k] for k in ('score', 'maximum', 'dimensions'))
    require((score is None) == (maximum is None), 'Incomplete assessment score')
    if score is not None:
        require(type(score) is int and type(maximum) is int and 0 <= score <= maximum <= 1000 and maximum > 0,
                'Invalid assessment score')
    if dimensions is not None:
        require(score is not None and type(dimensions) is dict and 0 < len(dimensions) <= 32, 'Invalid rubric dimensions')
        for name, row in dimensions.items():
            require(type(name) is str and 0 < len(name) <= 200, 'Invalid dimension name')
            evidence.closed(row, ('score', 'rationale'))
            require(type(row['score']) is int and 0 <= row['score'] <= maximum and
                    type(row['rationale']) is str and bool(row['rationale'].strip()), 'Invalid dimension result')
        require(sum(row['score'] for row in dimensions.values()) == score, 'Assessment arithmetic mismatch')
    narrative = None; narrative_digest = None
    if spec['narrative'] is not None:
        narrative, narrative_digest = document(spec['narrative'], parent, capture, structured=False)
    rubric = None; rubric_digest = None; rubric_semantic_digest = None
    if spec['rubric'] is not None:
        original_rubric, rubric_digest = document(spec['rubric'], parent, capture)
        rubric_semantic_digest = evidence.identity(original_rubric)
        rubric = locator(original_rubric, spec['rubric_locator'])
        require(type(rubric) is dict and type(rubric.get('dimensions')) is dict, 'Missing rubric dimensions')
        if dimensions is not None:
            require(set(dimensions) == set(rubric['dimensions']), 'Assessment rubric dimensions mismatch')
    else:
        require(spec['rubric_locator'] is None and dimensions is None, 'Assessment rubric missing')
    freeze = None; freeze_digest = None
    if spec['freeze'] is not None:
        original_freeze, freeze_digest = document(spec['freeze'], parent, capture)
        require(type(original_freeze) is dict, 'Invalid freeze record')
        require(rubric is not None and original_freeze.get('rubric_digest') == rubric_semantic_digest,
                'Frozen rubric digest mismatch')
        require(original_freeze.get('context_digest') == report['report']['provenance']['context_digest'],
                'Freeze context mismatch')
        # Only allowlisted presentation metadata, never the complete preservation file.
        freeze = {k: original_freeze[k] for k in ('rubric_digest', 'context_digest', 'original_freeze_utc')
                  if k in original_freeze}
        if 'original_freeze_utc' in freeze:
            stamp = datetime.fromisoformat(freeze['original_freeze_utc'])
            generated = datetime.fromisoformat(report['report']['provenance']['timestamp'])
            require(stamp.utcoffset() is not None and stamp <= generated, 'Inconsistent freeze time')
    value = {'author_kind': spec['author_kind'], 'attribution': spec['attribution'], **values,
             'narrative': narrative, 'rubric': rubric, 'freeze': freeze,
             'provenance': {'assessment_digest': digest, 'analyst_report_digest': report['review_digest'],
                            'narrative_digest': narrative_digest, 'rubric_digest': rubric_digest,
                            'rubric_semantic_digest': rubric_semantic_digest, 'freeze_digest': freeze_digest}}
    require(len(evidence.encoded(value)) <= LIMIT, 'Assessment presentation limit')
    # Screen only the explicit projection. Original preservation metadata may contain
    # private paths; it is authenticated but never included in HTML or diagnostics.
    review.screen_payload(value)
    value['id'] = evidence.identity(value)
    return value


def run_validator(request, modules, capture, roots):
    guards = (capture.guard(),)
    temporary = evidence.write_outputs({}, input_paths=roots, input_guards=guards)
    try:
        evidence.write_outputs({}, temporary / '.github', input_paths=roots, input_guards=guards)
        scripts = evidence.write_outputs({}, temporary / '.github' / 'scripts', input_paths=roots,
                                         input_guards=guards, rendered=modules)
        try:
            response = subprocess.run([sys.executable, '-I', '-B', '-c', RUNNER, str(scripts)],
                input=evidence.encoded(request), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                cwd=temporary, env={'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1', 'GIT_NO_LAZY_FETCH': '1'},
                timeout=120, check=False)
        except subprocess.TimeoutExpired:
            raise ValueError('Original validator deadline exceeded; omit attachment for base report') from None
        require(response.returncode == 0, 'Original validator rejected attachment; omit attachment for base report')
        require(len(response.stdout) <= REPLY_LIMIT, 'Validator response limit')
        value = evidence.parse_json(response.stdout, limit=REPLY_LIMIT)
        evidence.closed(value, ('report', 'records', 'review_digest', 'markdown_digest', 'module_names', 'layout_valid'))
        require(value['module_names'] == list(MODULES) and value['layout_valid'] is True, 'Validator layout mismatch')
        return value
    finally:
        # The new caller-owned 0700 tree contains only our copied public code.
        # Same-UID and privileged interference are outside the existing writer boundary.
        shutil.rmtree(temporary)


def load(paths, captured):
    """Independently validate all supplied attachments or fail without report output."""
    require(0 < len(paths) <= analysis.MAX_REPORTS, 'Analyst attachment limit')
    try:
        versions = {k: importlib.metadata.version(k) for k in PINS}
    except importlib.metadata.PackageNotFoundError:
        raise ValueError('Pinned validator environment required') from None
    require(sys.version_info[:2] == (3, 13) and versions == PINS, 'Pinned validator environment required')
    import skill_review as review  # Optional dependency, never needed by a base report.
    capture = review.Capture()
    items = []; roots = []; original_records = []; seen = set()
    for path in paths:
        path = evidence.safe_path(path, directory_identities=capture.directories)
        spec = capture.json(path, limit=LIMIT)
        parent = path.parent
        roots.append(parent)
        evidence.closed(spec, ('schema_version', 'profile', 'tooling', 'skill', 'record_id', 'review',
                              'review_digest', 'markdown_digest', 'inputs', 'analysis', 'source', 'support',
                              'selection', 'assessments'))
        require(type(spec['schema_version']) is int and spec['schema_version'] == 1, 'Attachment schema mismatch')
        require(type(spec['profile']) is str and spec['profile'] in PROFILES, 'Unsupported validator profile')
        evidence.skill_id(spec['skill']); evidence.sha(spec['record_id'])
        rid = spec['record_id']
        require(rid not in seen and rid in captured.records, 'Duplicate or missing attachment record')
        selected = captured.records[rid]
        require(selected['kind'] != 'inventory' and selected['source']['skill_id'] == spec['skill'], 'Attachment skill mismatch')
        seen.add(rid)
        require(type(spec['inputs']) is list and 0 < len(spec['inputs']) <= analysis.MAX_INPUTS, 'Original input limit')
        request = {k: spec[k] for k in ('skill', 'record_id')}
        request['inputs'] = [str(attachment_path(p, parent)) for p in spec['inputs']]
        for key in ('review', 'analysis', 'source', 'support', 'selection'):
            require(spec[key] is not None or key in ('source', 'support', 'selection'), 'Missing original input')
            request[key] = str(attachment_path(spec[key], parent)) if spec[key] is not None else None
        for key in ('inputs', 'source', 'support'):
            for raw in (request[key] if key == 'inputs' else [request[key]]):
                if raw is not None:
                    capture.tree(Path(raw)); roots.append(Path(raw))
        for key in ('analysis', 'selection'):
            if request[key] is not None:
                capture.read(Path(request[key]), limit=analysis.JSON_LIMIT)
                roots.append(Path(request[key]).parent)
        raw = capture.read(Path(request['review']), limit=LIMIT)
        markdown = capture.read(Path(request['review']).with_name('skill-review.md'), limit=LIMIT)
        roots.append(Path(request['review']).parent)
        for key, data in (('review_digest', raw), ('markdown_digest', markdown)):
            evidence.sha(spec[key])
            require(spec[key] == evidence.digest_bytes(data), 'Analyst report digest mismatch')
        require(spec['tooling'] is not None or spec['profile'] == 'current-v2', 'Historical tooling snapshot required')
        tooling = attachment_path(spec['tooling'], parent) if spec['tooling'] is not None else evidence.ROOT
        modules = {}
        revision, hashes = PROFILES[spec['profile']]
        for name, digest in zip(MODULES, hashes):
            data = capture.read(tooling / '.github' / 'scripts' / name)
            require(evidence.digest_bytes(data) == 'sha256:' + digest, 'Unreviewed validator module')
            modules[name] = data
        roots.append(tooling)
        require(type(spec['assessments']) is list and len(spec['assessments']) <= MAX_ASSESSMENTS, 'Assessment limit')
        # Capture assessment originals before any temporary output is allocated.
        # This provisional projection confers no authority: original validation
        # below must still reproduce the entire report exactly.
        provisional = {'review_digest': spec['review_digest'], 'report': evidence.parse_json(raw, limit=LIMIT)}
        assessments = [assessment(row, parent, capture, provisional, review) for row in spec['assessments']]
        require(len({row['provenance']['assessment_digest'] for row in assessments}) == len(assessments), 'Duplicate assessment document')
        require(len(capture.members) + len(capture.states) <= analysis.MAX_ENTRIES, 'Attachment entry limit')
        require(len(evidence.encoded(request)) <= LIMIT, 'Validator request limit')
        result = run_validator(request, modules, capture, tuple((*roots, *capture.roots)))
        require(result['review_digest'] == spec['review_digest'] and result['markdown_digest'] == spec['markdown_digest'],
                'Validated report capture mismatch')
        require(evidence.encoded(result['report']) == evidence.encoded(evidence.parse_json(raw, limit=LIMIT)), 'Validated report changed')
        require(result['records'].get(rid) == selected, 'Original and consolidated record mismatch')
        original_records.extend(result['records'].values())
        items.append({'record_id': rid, 'skill': spec['skill'], 'profile': spec['profile'], 'tooling_revision': revision,
                      'review_digest': spec['review_digest'], 'markdown_digest': spec['markdown_digest'],
                      'reference_deadlines': sorted({evidence.REVIEWED_REFERENCE_EXPIRY[(ref['artifact_id'], ref['artifact_digest'])]
                          for record in result['records'].values() for ref in record['references']
                          if (ref['artifact_id'], ref['artifact_digest']) in evidence.REVIEWED_REFERENCE_EXPIRY}),
                      'report': result['report'], 'assessments': sorted(assessments, key=lambda row: row['id'])})

    def current_references():
        for record in original_records:
            evidence.validate_evidence(record, public=True, _observed_at=evidence.utc_now())
    guards = (capture.guard(), current_references)
    values = tuple(sorted(items, key=lambda row: row['record_id']))
    result = ValidatedReviews(values, tuple(dict.fromkeys((*roots, *capture.roots))), guards, evidence.identity(values))
    result.check(captured)
    return result
