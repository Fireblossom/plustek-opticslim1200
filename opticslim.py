#!/usr/bin/env python3
"""OpticSlim 1200 SANE integration prototype. Requires Python 3.10+."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
STATE = ROOT / '.runtime'


def run(argv, **kwargs):
    return subprocess.run([str(x) for x in argv], check=True, **kwargs)


def find_scanimage(explicit=None):
    candidates = [explicit] if explicit else [
        ROOT / 'dist/win64/bin/scanimage.exe',
        '/opt/homebrew/bin/scanimage', '/usr/local/bin/scanimage',
        shutil.which('scanimage'),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise RuntimeError('scanimage not found. See README.md for Windows build or macOS setup.')


def native_path(path, scanimage):
    """Cygwin binaries need POSIX paths, including paths in config files."""
    path = Path(path).resolve()
    cygpath = scanimage.parent / 'cygpath.exe'
    if os.name == 'nt' and cygpath.exists():
        return run([cygpath, '-u', path], capture_output=True, text=True).stdout.strip()
    if os.name == 'nt':
        raise RuntimeError('Windows package is missing cygpath.exe; rebuild the package.')
    return str(path)


def firmware_info(path):
    data = path.read_bytes()
    # Sanity check only: this does NOT prove model compatibility.
    if not 1024 <= len(data) <= 65536:
        raise ValueError('Firmware size is implausible (expected 1–64 KiB).')
    first = data[:512].lstrip().lower()
    if first.startswith((b'<', b'http', b'mz')) or b'<html' in first:
        raise ValueError('This looks like a web page or executable, not raw scanner firmware.')
    return {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def import_firmware(args):
    source = args.file.resolve(strict=True)
    info = firmware_info(source)
    target = STATE / 'firmware/cism216.fw'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != source.read_bytes():
        raise RuntimeError('A different firmware is already installed. Preserve it before replacing.')
    if target != source:
        shutil.copyfile(source, target)
    info.update(source=str(source), source_info=args.source_info,
                model='OpticSlim 1200', hardware_verified=False)
    (target.parent / 'provenance.json').write_text(
        json.dumps(info, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(info, indent=2, ensure_ascii=False))
    print('Imported. Model compatibility is unverified until a real scan succeeds.')


def sane_env(scanimage, debug=False):
    conf = STATE / 'etc/sane.d'
    conf.mkdir(parents=True, exist_ok=True)
    (conf / 'dll.conf').write_text('gt68xx\n', encoding='ascii')
    (conf / 'test.conf').write_text('number_of_devices 0\n', encoding='ascii')
    content = 'usb 0x07b3 0x0413\n'
    firmware = STATE / 'firmware/cism216.fw'
    if firmware.exists():
        fwpath = native_path(firmware, scanimage)
        if any(char in fwpath for char in '\r\n"'):
            raise ValueError('Firmware path contains unsupported config characters.')
        content += f'firmware "{fwpath}"\n'
    (conf / 'gt68xx.conf').write_text(content, encoding='utf-8')
    env = os.environ.copy()
    env['PATH'] = str(scanimage.parent) + os.pathsep + env.get('PATH', '')
    env['SANE_CONFIG_DIR'] = native_path(conf, scanimage)
    if debug:
        env.update(SANE_DEBUG_GT68XX='5', SANE_DEBUG_SANEI_USB='4', SANE_DEBUG_DLL='3')
    return env


def get_devices(scanimage, env):
    try:
        result = run([scanimage, '-f', '%d|%v|%m%n'], env=env,
                     capture_output=True, text=True, timeout=45)
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr, file=sys.stderr, end='')
        raise
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')
    devices = []
    for line in result.stdout.splitlines():
        fields = line.split('|')
        if len(fields) == 3 and fields[0].startswith('gt68xx:') and \
                fields[1].lower() == 'plustek' and fields[2].lower() == 'opticslim 1200':
            devices.append(fields[0])
    return devices


def scan(args, scanimage, env):
    firmware = STATE / 'firmware/cism216.fw'
    if not firmware.exists():
        raise RuntimeError('Missing OpticSlim 1200 firmware. Run import-firmware first.')
    firmware_info(firmware)
    devices = get_devices(scanimage, env)
    if args.device:
        if args.device not in devices:
            raise RuntimeError('Requested device is not an enumerated OpticSlim 1200.')
        device = args.device
    elif len(devices) == 1:
        device = devices[0]
    else:
        raise RuntimeError(f'Expected one OpticSlim 1200, found {len(devices)}. Use list / --device.')
    output = args.output.resolve()
    if output.suffix.lower() != '.png':
        raise ValueError('Output must have a .png extension.')
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=output.name + '.', suffix='.part', dir=output.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            # Keep image bytes out of text-mode shell redirection (Windows PS 5.1).
            run([scanimage, '-d', device, '--format=png', '--mode', args.mode,
                 '--resolution', args.dpi, '--depth', '8', '-l', '0', '-t', '0',
                 '-x', args.width, '-y', args.height], env=env, stdout=stream, timeout=600)
        with temporary.open('rb') as stream:
            if stream.read(8) != b'\x89PNG\r\n\x1a\n':
                raise RuntimeError('Scanner did not produce a PNG image; output was not saved.')
        # Exclusive creation protects pre-existing output, including concurrent runs.
        try:
            with output.open('xb') as destination, temporary.open('rb') as source:
                shutil.copyfileobj(source, destination)
        except FileExistsError:
            raise
        except BaseException:
            output.unlink(missing_ok=True)
            raise
        print(f'Saved {output}')
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scanimage', help='Override path to SANE scanimage executable')
    parser.add_argument('--debug', action='store_true')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Inspect runtime and firmware; does not start a scan')
    commands.add_parser('list', help='Enumerate only OpticSlim 1200 devices')
    imp = commands.add_parser('import-firmware')
    imp.add_argument('file', type=Path)
    imp.add_argument('--source-info', required=True, help='Where this model-specific firmware came from')
    sc = commands.add_parser('scan')
    sc.add_argument('output', type=Path)
    sc.add_argument('--device')
    sc.add_argument('--dpi', type=int, choices=[50, 75, 150, 300, 600], default=150)
    sc.add_argument('--mode', choices=['Color', 'Gray'], default='Color')
    sc.add_argument('--width', type=float, default=50, help='mm, default 50 for first test')
    sc.add_argument('--height', type=float, default=50, help='mm, default 50 for first test')
    args = parser.parse_args(argv)
    try:
        if args.command == 'import-firmware':
            import_firmware(args)
            return 0
        binary = find_scanimage(args.scanimage)
        if args.command == 'doctor':
            print(f'Host: {platform.system()} {platform.machine()}')
            print(f'scanimage: {binary}')
            run([binary, '--version'])
            firmware = STATE / 'firmware/cism216.fw'
            print(f'Firmware: {firmware_info(firmware) if firmware.exists() else "MISSING"}')
            print('USB target: 07b3:0413. See VALIDATION.md for tested hosts and remaining checks.')
            return 0
        env = sane_env(binary, args.debug)
        if args.command == 'list':
            devices = get_devices(binary, env)
            print('\n'.join(devices) if devices else 'No OpticSlim 1200 found.')
            return 0 if devices else 2
        if not (0 < args.width <= 218 and 0 < args.height <= 299):
            raise ValueError('Scan area must be within 218 × 299 mm.')
        scan(args, binary, env)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
