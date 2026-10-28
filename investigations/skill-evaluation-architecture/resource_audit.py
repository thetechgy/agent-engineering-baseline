"""Read-only teardown audit over exact trial-owned Compose projects."""
import subprocess
from harbor.environments.docker.docker import _sanitize_docker_compose_project_name

def audit(sessions):
 rows=[]
 for session in sessions:
  project=_sanitize_docker_compose_project_name(session)
  row={'project':project}
  for kind in ('container','network','volume','image'):
   cmd=['docker',kind,'ls']+(['--all'] if kind in ('container','image') else [])+['--quiet','--filter','label=com.docker.compose.project='+project]
   values=subprocess.check_output(cmd,text=True).split();row[kind]=len(values)
   assert not values,('trial resources remain',project,kind)
  rows.append(row)
 return rows
