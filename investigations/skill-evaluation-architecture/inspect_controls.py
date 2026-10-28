"""Inject failure and real SIGINT after trusted Inspect initialization."""
import os,pathlib,signal,subprocess,sys,time
root=pathlib.Path(sys.argv[1]);script=pathlib.Path(__file__).with_name('inspect_gate.py')
subprocess.run([sys.executable,str(script),str(root),'failure'],check=True,timeout=100)
with (root/'evidence/inspect-cancellation.txt').open('w') as f:
 p=subprocess.Popen([sys.executable,str(script),str(root),'cancel'],stdout=f,stderr=subprocess.STDOUT)
 try:
  for _ in range(900):
   if (root/'cancel-ready').exists():break
   if p.poll() is not None:raise AssertionError('cancel worker exited before initialization')
   time.sleep(.1)
  else:raise TimeoutError('Inspect cancellation readiness')
  p.send_signal(signal.SIGINT)
  p.wait(timeout=30)
 finally:
  if p.poll() is None:p.kill();p.wait()
remaining=subprocess.check_output(['docker','ps','-aq','--filter','name=architecture-inspect'],text=True).strip()
assert not remaining,'Inspect containers remain'
print('Inspect failure/cancellation cleanup controls passed')
