import io, json, tarfile, tempfile, shutil
from pathlib import Path
from public_release import inspect, allowed
allowed_repo={'site.tar.gz','README.md','.github/workflows/deploy.yml','ci/check.py','ci/public_release.py'}
import subprocess
tracked=set(subprocess.check_output(['git','ls-files'],text=True).splitlines())
if tracked != allowed_repo: raise SystemExit('Unexpected repository files: '+str(tracked ^ allowed_repo))
root=Path('release');root.mkdir()
seen=set();total=0
with tarfile.open('site.tar.gz','r:gz') as archive:
    for m in archive:
        if not m.isfile() or not allowed(m.name) or m.name in seen: raise ValueError('Unsafe archive member')
        seen.add(m.name);total+=m.size
        if total>1024**3 or len(seen)>20000 or m.size>50*1024**2: raise ValueError('Release exceeds limit')
        p=root/m.name;p.parent.mkdir(parents=True,exist_ok=True)
        with archive.extractfile(m) as src,p.open('wb') as dst:shutil.copyfileobj(src,dst)
files,routes=inspect(root,True)
print('Public isolation and hashes passed:',len(files),'files;',len(routes),'routes')
