"""Bounded launch diagnostics from Harbor's existing command logger, not transcripts."""
import json, logging, os, re
from pathlib import Path

SENTINEL = 'NONSECRET-DIRECT-HARBOR-DIAGNOSTIC-ONLY'

def sanitize(value, secrets=()):
    text = str(value or '')
    for secret in (SENTINEL, *secrets):
        if secret:
            text = text.replace(secret, '<REDACTED>')
    text = re.sub(r'(?im)(authorization[\"\s]*[:=][\"\s]*(?:bearer|basic)?\s*)[^\s\"\r\n,}]+', r'\1<REDACTED>', text)
    text = re.sub(r'(?i)((?:OPENAI_API_KEY|CODEX_API_KEY|api[_-]key)[\"\s]*[:=]\s*)[\"\']?[^\s\"\'\n,}]+', r'\1<CREDENTIAL>', text)
    text = re.sub(r'(cat >[^\n]*auth.json[^\n]*<<EOF\n).*?\nEOF', r'\1<AUTH_JSON_REDACTED>\nEOF', text, flags=re.S)
    text = re.sub(r'(printf %s ).*?( > /installed-agent/codex-home/config.toml)', r'\1<CONFIG_TOML>\2', text, flags=re.S)
    text = re.sub(r'(codex exec .*? -- ).*?( 2>&1 </dev/null \| tee)', r'\1<TASK_PROMPT>\2', text, flags=re.S)
    # Never export model text, tool results, or submitted code embedded in JSONL.
    lines=[]
    for line in text.splitlines():
        try: event=json.loads(line)
        except ValueError: event=None
        if isinstance(event,dict) and str(event.get('type','')).startswith('item.'):
            line='<TASK_EVENT_OMITTED>'
        lines.append(line)
    return '\n'.join(lines)[:12000]

class LaunchDiagnostics(logging.Handler):
    """Consume pinned Harbor DEBUG records; checkpoint each result before cleanup."""
    def __init__(self, destination, secrets=()):
        super().__init__(logging.DEBUG)
        self.destination=Path(destination); self.secrets=secrets
        self.data={'commands':[], 'primary_failure':None, 'cleanup_failures':[]}
        self.pending=None

    def save(self):
        self.destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.destination.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.data,indent=2)+'\n'); temporary.replace(self.destination)

    def emit(self, record):
        message=record.getMessage()
        if message.startswith('Running command: '):
            command=message.removeprefix('Running command: ')
            stage=('cli_startup' if 'codex exec ' in command else
                   'cleanup' if 'rm -rf' in command or 'cp -R "$CODEX_HOME/sessions"' in command else
                   'authentication_setup' if 'auth.json' in command else
                   'configuration_upload' if 'config.toml' in command else
                   'ownership_check' if 'stat -c' in command else 'directory_setup')
            self.pending={'stage':stage,'command':sanitize(command,self.secrets),
                'user':str(getattr(record,'user',None)) if getattr(record,'user',None) not in (None,'None') else 'agent (task default)',
                'cwd':'/workspace (task workdir)','exit_status':None}
            self.data['commands'].append(self.pending);self.save()
        elif self.pending is not None and message in ('Command failed','Command outputs captured'):
            self.pending.update(exit_status=getattr(record,'return_code',0),
                stdout=sanitize(getattr(record,'stdout',''),self.secrets),
                stderr=sanitize(getattr(record,'stderr',''),self.secrets),
                stream_note='Harbor Docker merges stderr into stdout')
            if self.pending['exit_status']:
                if self.pending['stage']=='cleanup':self.data['cleanup_failures'].append(dict(self.pending))
                elif self.data['primary_failure'] is None:self.data['primary_failure']=dict(self.pending)
            self.save();self.pending=None

    def exception(self, exc):
        self.data['native_exception']={'type':type(exc).__name__,'message':sanitize(str(exc),self.secrets)}
        self.save()


def sanitized_exception(value):
    secrets=tuple(os.environ.get(k,'') for k in ('OPENAI_API_KEY','CODEX_API_KEY'))
    return {k:sanitize(v,secrets) for k,v in value.items() if k in ('exception_type','occurred_at','exception_message')}
