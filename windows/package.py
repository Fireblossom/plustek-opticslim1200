"""Collect only the Cygwin runtime DLLs imported by scanimage and cygpath."""
from pathlib import Path
import json
import hashlib
import os
import re
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
cygwin = root / '.cache/cygwin'
binary = cygwin / 'tmp/opticslim-build/backends-1.4.0/frontend/scanimage.exe'
output = root / 'dist/win64'
bindir = output / 'bin'
bindir.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env['PATH'] = str(cygwin / 'bin') + os.pathsep + env.get('PATH', '')
queue = [binary, cygwin / 'bin/cygpath.exe']
copied = set()
while queue:
    source = queue.pop()
    if source.name.lower() in copied:
        continue
    copied.add(source.name.lower())
    shutil.copy2(source, bindir / source.name)
    report = subprocess.run([str(cygwin / 'bin/objdump.exe'), '-p', str(source)],
                            check=True, capture_output=True, text=True, env=env).stdout
    for name in re.findall(r'DLL Name:\s*(\S+)', report):
        dependency = cygwin / 'bin' / name
        if dependency.is_file():
            queue.append(dependency)
license_dir = output / 'licenses'
license_dir.mkdir(exist_ok=True)
shutil.copy2(cygwin / 'tmp/opticslim-build/backends-1.4.0/COPYING', license_dir / 'SANE-COPYING.txt')
manifest = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(bindir.iterdir())}
(output / 'SHA256.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Packaged {len(manifest)} executable/runtime files in {output}')
