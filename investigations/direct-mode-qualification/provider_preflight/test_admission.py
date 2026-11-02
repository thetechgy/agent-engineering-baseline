"""Replay-only regression tests; never connect to a provider or execute artifact code."""
import os,unittest,zipfile
from pathlib import Path
from contextlib import nullcontext
from policy import decode
from admission import admit
from admission_controls import admission_controls

@unittest.skipUnless(os.environ.get('AEB_PREFLIGHT_ARCHIVE') or os.environ.get('AEB_PREFLIGHT_DIRECTORY'),'Provide retained fake qualification evidence')
class AdmissionControls(unittest.TestCase):
 def test_native_positive_and_specific_corruption_stops(self):
  archive=os.environ.get('AEB_PREFLIGHT_ARCHIVE')
  with zipfile.ZipFile(archive) if archive else nullcontext() as z:
   def raw(n):return z.read('provider-preflight/normal/'+n) if z else (Path(os.environ['AEB_PREFLIGHT_DIRECTORY'])/n).read_bytes()
   def read(n):return decode(raw(n))
   requests=[read(f'request-{i}.json') for i in range(1,7)]
   responses=[raw(f'response-{i}.sse') for i in range(1,7)]
   audit=[decode(line) for line in raw('relay.jsonl').splitlines()]
   effects=read('independent-effects.json');capture=read('native.json')
   self.assertEqual(admit(capture,requests,responses,audit,effects['effects'],effects['nonce'])['original_submissions'],5)
   for case in ('retained-request','outbound-request','observed-response','admitted-response','context-type','context-id','context-bytes','late-submission','late-output'):
    with self.subTest(corruption=case):
     self.assertEqual(admission_controls(capture,requests,responses,audit,effects['effects'],effects['nonce'],case),[case])
if __name__=='__main__':unittest.main()
