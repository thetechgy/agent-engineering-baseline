"""Bounded retained-artifact validation; never extract or execute artifacts."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

root=Path(__file__).resolve().parent/'results/archive'
for metadata_path in sorted(root.glob('*-artifacts.json')):
    run_id=metadata_path.name.split('-')[0]
    metadata=json.loads(metadata_path.read_text())
    assert metadata['total_count']==len(metadata['artifacts'])==1
    artifact=metadata['artifacts'][0]
    run=json.loads((root/f'{run_id}-run.json').read_text())
    assert run['repository']['full_name']=='thetechgy/agent-engineering-baseline'
    assert run['head_branch']=='experiment/code-mode-evidence-166'
    assert run['path']=='.github/workflows/experimental-code-mode-evidence.yml'
    assert run['event']=='push' and run['run_attempt']==1
    assert artifact['workflow_run']['head_sha']==run['head_sha']
    raw=(root/f'{run_id}-1.zip').read_bytes()
    assert len(raw)==artifact['size_in_bytes'] and len(raw)<16*1024*1024
    assert artifact['digest']=='sha256:'+hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members=archive.infolist()
        assert len(members)<100 and sum(m.file_size for m in members)<16*1024*1024
        assert len({m.filename for m in members})==len(members)
        for member in members:
            path=PurePosixPath(member.filename)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in member.filename
            assert stat.S_IFMT(member.external_attr>>16) in (0,stat.S_IFREG)
        summary=json.loads(archive.read('summary.json'))
        for version in ('166','165'):
            assert summary[version]['stock_full_submission_contract']=='failed'
            assert summary[version]['direct_runtime_feasible']
    print(run_id,run['head_sha'],run['conclusion'],'verified as data; no production admission')
