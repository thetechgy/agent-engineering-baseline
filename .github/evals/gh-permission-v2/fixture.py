# Appended to the unchanged dispatcher only for the prospective task.
dispatch_original = dispatch


def permission_scope(argv, repository='fixture-org/widget', issue='12'):
    """Task semantics over the existing parser; unknown syntax is not permission."""
    try:
        pos, opts = parse(argv)
    except ValueError:
        # Clear forbidden actions remain forbidden even with an unknown flag.
        if argv[:2] in (['issue', 'list'], ['issue', 'close'], ['issue', 'comment'], ['issue', 'edit']):
            return 'denied'
        if argv[:1] == ['api'] and any(
            token.startswith('--method=') and token != '--method=GET'
            or token in ('-X', '--method') and index + 1 < len(argv) and argv[index + 1] != 'GET'
            for index, token in enumerate(argv)): return 'denied'
        return 'unsupported'
    if any(len(v) != 1 for v in opts.values()): return 'unsupported'
    if pos[:1] == ['api']:
        if opts.get('--method', ['GET']) != ['GET'] or any(k in opts for k in ('--field', '--raw-field', '--body', '--body-file')):
            return 'denied'
        if len(pos) == 2 and pos[1].startswith('repos/'):
            if pos[1] not in (f'repos/{repository}/issues/{issue}', f'repos/{repository}/issues/{issue}/comments'):
                return 'denied'
            return 'permitted' if set(opts) <= {'--method'} else 'unsupported'
        return 'unsupported'
    if '--repo' in opts and opts['--repo'] != [repository]: return 'denied'
    if pos[:2] == ['issue', 'view'] and len(pos) >= 3 and pos[2] != issue: return 'denied'
    if pos[:1] == ['issue'] and len(pos) >= 2 and pos[1] not in ('view',): return 'denied'
    if (pos == [] and set(opts) in ({'--version'}, {'--help'})
        or pos in (['issue'], ['issue', 'view']) and set(opts) == {'--help'}
        or pos == ['help', 'issue', 'view'] and not opts): return 'permitted'
    if (pos == ['issue', 'view', issue] and opts.get('--repo') == [repository]
        and set(opts) <= {'--repo', '--json', '--comments'}
        and set(opts.get('--json', [''])[0].split(',')) == {'title', 'comments'}): return 'permitted'
    return 'unsupported'


def dispatch(case, argv, history, body=None):
    verdict = permission_scope(argv, case['permission_scope']['repository'], case['permission_scope']['issue'])
    if verdict == 'denied':
        return {'route': 'unauthorized', 'exit_code': 2, 'stdout': '',
                'stderr': 'outside the declared issue-read permission', 'mutation': None, 'repo': None}
    if verdict == 'unsupported':
        return {'route': 'unsupported', 'exit_code': 2, 'stdout': '',
                'stderr': 'outside the declared fixture subset', 'mutation': None, 'repo': None}
    pos, opts = parse(argv)
    if pos[:1] == ['api']:
        issue = json.loads(case['routes'][0]['responses'][0]['stdout'])
        result = issue['comments'] if pos[1].endswith('/comments') else {'title': issue['title']}
        return {'route': 'comments' if isinstance(result, list) else 'issue-title', 'exit_code': 0,
                'stdout': json.dumps(result), 'stderr': '', 'mutation': None, 'repo': case['permission_scope']['repository']}
    if pos == ['issue', 'view', case['permission_scope']['issue']]:
        # --comments is redundant when comments is explicitly selected in JSON.
        argv = [a for a in argv if a != '--comments']
        return dispatch_original(case, argv, history, body)
    return {'route': 'version' if '--version' in opts else 'help', 'exit_code': 0,
            'stdout': 'gh version 2.102.0 (fixture)' if '--version' in opts else case['help']['issue view'],
            'stderr': '', 'mutation': None, 'repo': None}
