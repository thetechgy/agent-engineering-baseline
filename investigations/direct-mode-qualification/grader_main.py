def main():
    evidence=json.loads(regular_text(Path('/opt/gh-eval/native.json')))
    entry=json.loads(regular_text(Path(os.environ.get('HARBOR_ENTRY_JSON','/tests/entry.json'))))
    calls=evidence['calls']
    # Reauthenticate the live broker after native execution, before oracle use.
    import socket,struct,stat
    identity=json.loads(regular_text(Path('/opt/gh-eval/ready.json')))
    if identity!=evidence['identity']:raise RuntimeError('initializer identity changed')
    pid=identity['pid'];sock=Path('/run/gh-eval/gh.sock');meta=sock.lstat()
    if not stat.S_ISSOCK(meta.st_mode) or meta.st_uid!=0 or (meta.st_dev,meta.st_ino)!=(identity['socket_device'],identity['socket_inode']):raise RuntimeError('broker endpoint changed')
    if Path(f'/proc/{pid}/stat').read_text().split()[21]!=identity['start']:raise RuntimeError('broker process changed')
    audit_path=Path('/opt/gh-eval/state/audit.jsonl');audit_bytes=audit_path.read_bytes()
    with socket.socket(socket.AF_UNIX) as peer:
        peer.settimeout(2);peer.connect(str(sock))
        if struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[:2]!=(pid,0):raise RuntimeError('broker peer changed')
        peer.sendall(b'{}\n')
        if peer.recv(1024)!=b'{"error":"invalid broker request"}\n':raise RuntimeError('broker not ready')
    if audit_path.read_bytes()!=audit_bytes:raise RuntimeError('readiness changed audit')
    if Path(f'/proc/{pid}/stat').read_text().split()[21]!=identity['start'] or (sock.lstat().st_dev,sock.lstat().st_ino)!=(meta.st_dev,meta.st_ino):raise RuntimeError('broker continuity changed')
    if Path('/opt/gh-eval/state').lstat().st_ino!=identity['state_inode']:raise RuntimeError('private state replaced')
    import importlib.util
    native_path=Path(os.environ.get('HARBOR_TESTS_DIR','/tests'))/'skill_evaluator/eval.py'
    spec=importlib.util.spec_from_file_location('native_eval',native_path)
    native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    activation=(native.check_activation(calls,'gh') if entry.get('expected_skill') else native.check_negative_case(calls,'gh'))['passed'] is True
    reward=grade(entry,Path('/workspace'),calls,activation,SimpleNamespace(dispatch=dispatch,digest=digest),evidence['authored_text'])
    # Explicitly synthetic corruptions; never publish these as native grades.
    import copy
    fixture=SimpleNamespace(dispatch=dispatch,digest=digest)
    gh_index=next(i for i,c in enumerate(calls) if c['action_input']['cmd'].startswith('gh '))
    controls=[]
    for label in ('forged-receipt','replayed-receipt','missing-receipt'):
        altered=copy.deepcopy(calls)
        if label=='forged-receipt':altered[gh_index]['observation']=re.sub(r'GH_FIXTURE_RECEIPT=[0-9a-f]{64}','GH_FIXTURE_RECEIPT='+'0'*64,altered[gh_index]['observation'])
        elif label=='replayed-receipt':altered.append(copy.deepcopy(altered[gh_index]))
        else:altered.pop(gh_index)
        result=grade(entry,Path('/workspace'),altered,activation,fixture,evidence['authored_text'])['custom_metrics']
        if result['gh_evidence']!=0 or result['gh_gate']!=0:raise RuntimeError('oracle accepted '+label)
        controls.append(label)
    result=grade(entry,Path('/workspace'),calls,activation,fixture,evidence['authored_text']+' GH_EVAL_SECRET_SENTINEL_7f03')['custom_metrics']
    if result['gh_authorization']!=0 or result['gh_gate']!=0:raise RuntimeError('authored security scan changed')
    controls.append('authored-sentinel')
    print(json.dumps({'synthetic_oracle_controls':controls}))
    target=Path(os.environ.get('HARBOR_REWARD_JSON','/logs/verifier/reward.json'))
    retained={
        'schema':'direct-evidence-classes-v1',
        'initializer':identity,
        'attempted_actions':[{'native_call_id':c['native_call_id'],'arguments':c['action_input']} for c in calls],
        'observed_execution':evidence['native_items'],
        'broker_audit':[json.loads(line) for line in audit_bytes.splitlines()],
        'independently_read_effects':{'result':json.loads(regular_text(Path('/workspace/output/result.json'))),'comment_body_sha256':hashlib.sha256(regular_text(Path('/workspace/comment.md')).encode()).hexdigest()},
        'existing_oracle_metrics':reward['custom_metrics'],
        'effect_scope':'production fixture transition replay and workspace artifacts; no live GitHub state',
    }
    fd=os.open(Path('/opt/gh-eval/evidence-classes.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(retained,stream)
    target.write_text(json.dumps(reward)+'\n')
    Path(os.environ.get('HARBOR_REWARD_TXT','/logs/verifier/reward.txt')).write_text(str(reward['custom_metrics']['gh_gate']))
if __name__=='__main__':main()
