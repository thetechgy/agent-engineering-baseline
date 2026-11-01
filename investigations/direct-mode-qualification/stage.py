"""Derivative qualification projection; production fixture/grader bytes remain inputs."""
import json,sys,shlex
from pathlib import Path
repo,out=map(Path,sys.argv[1:]);sys.path.insert(0,str(repo/'.github/scripts'))
import gh_evaluations as gh
source=gh.stage(repo,out/'source/gh',['gh-010-partial'])
env=source/'evals/harbor/gh-010-partial/environment'
s=(env/'Dockerfile').read_text();s=s.replace('&& python3 -I /opt/gh-eval/setup.py --build && rm -rf /opt/gh-eval/source','')
s+='COPY codex /opt/codex\nRUN chmod -R a+rX /opt/codex\n'
s+='RUN python3 -I -c '+shlex.quote("import importlib.util;from pathlib import Path;s=importlib.util.spec_from_file_location('fixture_setup','/opt/gh-eval/setup.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.setup(Path('/workspace'),Path('/opt/gh-eval/source'),install=True,private=Path('/opt/gh-eval/build-state'))")+' && rm -rf /opt/gh-eval/build-state\n'
(env/'Dockerfile').write_text(s)
import shutil
shutil.copytree(out/'codex',env/'codex')
task=env.parent/'task.toml';s=task.read_text().split('[environment.healthcheck]')[0];s=s.replace('network_mode = "public"','network_mode = "no-network"');task.write_text(s)
s=(source/'evals/grader.py').read_text().split('def main():')[0]
s+="def main():\n    evidence=json.loads(regular_text(Path('/opt/gh-eval/native.json')))\n    entry=json.loads(regular_text(Path(os.environ.get('HARBOR_ENTRY_JSON','/tests/entry.json'))))\n    calls=evidence['calls']\n    activation=any(c['action_input']=={'cmd':'cat /workspace/skills/gh/SKILL.md'} for c in calls)\n    if activation!=evidence['activation']:raise ValueError('activation contradiction')\n    reward=grade(entry,Path('/workspace'),calls,activation,SimpleNamespace(dispatch=dispatch,digest=digest),'')\n    target=Path(os.environ.get('HARBOR_REWARD_JSON','/logs/verifier/reward.json'))\n    target.write_text(json.dumps(reward)+'\\n')\n    Path(os.environ.get('HARBOR_REWARD_TXT','/logs/verifier/reward.txt')).write_text(str(reward['custom_metrics']['gh_gate']))\nif __name__=='__main__':main()\n"
(source/'evals/grader.py').write_text(s)
print(source)
