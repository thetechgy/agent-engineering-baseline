"""Check retained evidence as bounded data; never extract or execute producer content."""
import hashlib,json,pathlib,stat,zipfile
root=pathlib.Path(__file__).resolve().parent
manifest=json.loads((root/'archive/manifest.json').read_text())
for row in manifest['runs']:
    archive=root/'archive'/row['archive'];data=archive.read_bytes()
    assert len(data)==row['compressed_bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
    run=json.loads((root/'archive'/row['run_metadata']).read_text())
    assert run['id']==row['run_id'] and run['run_attempt']==1 and run['head_sha']==row['source_revision']
    assert run['head_branch']=='experiment/native-codex-qualification' and run['event']=='push'
    assert run['repository']['full_name']=='thetechgy/agent-engineering-baseline'
    assert run['path']=='.github/workflows/experimental-native-qualification.yml'
    with zipfile.ZipFile(archive) as z:
        members=z.infolist();assert len(members)<1024 and sum(m.file_size for m in members)<16*1024*1024
        assert len({m.filename for m in members})==len(members)
        for m in members:
            p=pathlib.PurePosixPath(m.filename)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in m.filename
            assert stat.S_IFMT(m.external_attr>>16) in (0,stat.S_IFREG)
        assert len(members)==row['members'] and sum(m.file_size for m in members)==row['uncompressed_bytes']
        if row.get('final'):
            identity=json.loads(z.read('runtime-identities.json'));assert identity['source']==row['source_revision'] and identity['run_id']==str(row['run_id'])
            assert set(json.loads(z.read('outcomes.json')).values())=={0}
            contract=json.loads(z.read('contract/summary.json'));assert len(contract['rows'])==6 and contract['cleanup_verified']
            assert all(r['admission']=='unavailable' and r['security_grade_available'] is False for r in contract['rows'])
            cli=json.loads(z.read('cli-controls/summary.json'));assert len(cli['rows'])==4 and all(r['intended_rejection_observed'] for r in cli['rows'])
    print(row['run_id'],row['source_revision'],row['sha256'],'verified; data only')
