"""Create a personal migration zip, excluding build caches and scanned documents."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

root = Path(__file__).resolve().parent
output = root / 'dist/OpticSlim1200-personal-test-kit.zip'
files = []
for folder in ('windows', 'macos', 'tests', 'dist/win64', '.runtime/firmware'):
    files.extend(p for p in (root / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for name in ('README.md', 'VALIDATION.md', 'LICENSE', 'THIRD_PARTY.md', 'opticslim.py', 'airscan_bridge.py',
             'requirements.txt', 'package_personal.py', '.gitignore', '.gitattributes'):
    files.append(root / name)
output.parent.mkdir(exist_ok=True)
with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
    for path in sorted(files):
        name = 'OpticSlim1200/' + path.relative_to(root).as_posix()
        if path.name.endswith(('.sh', '.command')):
            info = ZipInfo.from_file(path, arcname=name)
            info.create_system = 3
            info.external_attr = 0o100755 << 16
            archive.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED)
        else:
            archive.write(path, arcname=name)
print(output)
print(f'{len(files)} files; {output.stat().st_size} bytes')
