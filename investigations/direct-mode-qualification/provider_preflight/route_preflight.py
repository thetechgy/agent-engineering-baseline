"""Non-inference transport observation; never reads credentials or sends POST."""
import datetime,hashlib,http.client,json,socket,ssl,subprocess,sys
from pathlib import Path
out=Path(sys.argv[1]);out.parent.mkdir(parents=True,exist_ok=True)
r={'schema':'provider-route-preflight-v1','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'route':'https://api.openai.com/v1/responses','intended_model':'gpt-5.6-sol','transport_test':'GET /v1/models/gpt-5.6-sol without credentials','inference_requests':0,'credentials_read':False,'account_model_access':'unverified-no-dedicated-key','count_endpoint_fee_micro_usd':None,'live_execution':'blocked-separate-authorization-and-billing'}
try:
 c=http.client.HTTPSConnection('api.openai.com',443,timeout=8,context=ssl.create_default_context())
 c.connect();r['tls_version']=c.sock.version();r['peer_certificate_sha256']=hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest();r['certificate_hostname_verified']=True
 c.request('GET','/v1/models/gpt-5.6-sol',headers={'Accept':'application/json'});response=c.getresponse();r['http_status']=response.status;response.read(65536);c.close()
except Exception as e:r['transport_observation']='unavailable-'+type(e).__name__
source=Path(sys.argv[2]) if len(sys.argv)>2 else None
if source and source.exists():
 data=json.loads(subprocess.check_output(['git','-C',str(source),'show','6ff1e1ca3b30fc8b914720681fcf5fe62e95f856:codex-rs/models-manager/models.json']))
 r['pinned_catalog_presence']={name:[m.get('tool_mode') for m in data['models'] if m['slug']==name] for name in ('gpt-5.6-sol','gpt-6.1-sol')}
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
