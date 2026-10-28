"""Real CLI rejection controls on unchanged gh staging, with a local catalog only."""
import http.server,json,os,pathlib,subprocess,sys,threading
root=pathlib.Path(sys.argv[1]);repo=pathlib.Path(sys.argv[2]);out=root/'evidence/cli-controls';out.mkdir(parents=True)
sys.path.insert(0,str(repo/'.github/scripts'))
import gh_evaluations as gh
source=gh.stage(repo,root/'cli-source/gh',['gh-001'])
requests=[]
class Catalog(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        requests.append({'method':'GET','path':self.path})
        if self.path!='/v1/models':self.send_error(404);return
        body=json.dumps({'object':'list','data':[{'id':'gpt-5.6-sol','object':'model','owned_by':'fixture'}]}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        requests.append({'method':'POST','path':self.path});self.send_error(418,'CLI control prohibits model calls')
server=http.server.ThreadingHTTPServer(('127.0.0.1',8991),Catalog);threading.Thread(target=server.serve_forever,daemon=True).start()
rows=[]
try:
    for name,label,mode,kwargs,expected in [
      ('unrelated-wrapper','candidate','architecture-poc',[],'must subclass it'),
      ('native-wrapper-staging-guard','candidate','aeb-native',['--ek','profile=producer-smoke'],'healthcheck is not allowed in a paired baseline'),
      ('released-staging-guard','released','docker',[],'healthcheck is not allowed in a paired baseline'),
      ('released-custom-mode','released','aeb-native',[],'aeb-native'),
    ]:
        executable=root/label/'.venv/bin/skillevaluator'
        env={'PATH':str(executable.parent)+':'+os.environ['PATH'],'HOME':str(root/'home'),'DOCKER_CONFIG':os.environ['DOCKER_CONFIG'],'PYTHON_DOTENV_DISABLED':'1','PYTHONDONTWRITEBYTECODE':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_NOSYSTEM':'1','SKILL_EVAL_LLM_PROVIDER':'openai-compatible','SKILL_EVAL_LLM_MODEL':'gpt-5.6-sol','SKILL_EVAL_LLM_API_KEY':'qualification-sentinel-not-a-real-key','SKILL_EVAL_LLM_BASE_URL':'http://127.0.0.1:8991/v1','SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE':str(root/(name+'.key'))}
        cmd=[str(executable),'tier3','evaluate',str(source),'--agents','codex','--agent-model','codex=gpt-5.6-sol','--env-mode',mode,'--grading-mode','default_plus_custom','--n-attempts','1','--no-stop-on-pass','--n-concurrent','1','--max-agents','1','--harbor-keep-jobs','--results-dir',str(root/('results-'+name)),*kwargs]
        r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=90);text=r.stdout+'\n'+r.stderr;(out/(name+'.txt')).write_text(text)
        rows.append({'name':name,'source':label,'exit_code':r.returncode,'intended_rejection_observed':expected in text})
        (out/'summary.json').write_text(json.dumps({'evidence_class':'actual-skillevaluator-cli','rows':rows,'fixture_projection':'unchanged production gh-001 staging','catalog_requests':requests},indent=2))
        assert r.returncode!=0 and expected in text,(name,r.returncode,text[-2500:])
    assert not any(r['method']=='POST' for r in requests),'model request attempted in rejection control'
finally:server.shutdown()
print(json.dumps(rows))
