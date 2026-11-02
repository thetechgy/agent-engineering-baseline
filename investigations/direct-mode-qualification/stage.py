"""Derivative qualification projection; production fixture/grader bytes remain inputs."""
import json,sys,shlex
from pathlib import Path
repo,out=map(Path,sys.argv[1:]);sys.path.insert(0,str(repo/'.github/scripts'))
import gh_evaluations as gh
source=gh.stage(repo,out/'source/gh',['gh-010-partial'])
env=source/'evals/harbor/gh-010-partial/environment'
s=(env/'Dockerfile').read_text();s=s.replace('&& python3 -I /opt/gh-eval/setup.py --build && rm -rf /opt/gh-eval/source','')
s+='COPY codex /opt/codex\nRUN chmod -R a+rX /opt/codex && python3 -m pip install --no-deps --no-index /opt/codex/idna-3.18-py3-none-any.whl\n'
s+='RUN python3 -I -c '+shlex.quote("import importlib.util;from pathlib import Path;s=importlib.util.spec_from_file_location('fixture_setup','/opt/gh-eval/setup.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.setup(Path('/workspace'),Path('/opt/gh-eval/source'),install=True,private=Path('/opt/gh-eval/build-state'))")+' && rm -rf /opt/gh-eval/build-state\n'
(env/'Dockerfile').write_text(s)
import shutil
shutil.copytree(out/'codex',env/'codex')
task=env.parent/'task.toml';s=task.read_text().split('[environment.healthcheck]')[0];s=s.replace('network_mode = "public"','network_mode = "no-network"');task.write_text(s)
s=(source/'evals/grader.py').read_text().split('def main():')[0]
s+=Path(__file__).with_name('grader_main.py').read_text()
(source/'evals/grader.py').write_text(s)
print(source)
