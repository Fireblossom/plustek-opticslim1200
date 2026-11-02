#!/usr/bin/env python3
"""Local OpticSlim 1200 SANE -> AirScan/eSCL integration prototype.

Advertises a scanner to native OS scanning apps. Real client interoperability
must be verified on each target OS; this is not a certified Mopria device.
"""
import argparse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET

import opticslim

SCAN = 'http://schemas.hp.com/imaging/escl/2011/05/03'
PWG = 'http://www.pwg.org/schemas/2010/12/sm'
ET.register_namespace('scan', SCAN)
ET.register_namespace('pwg', PWG)
SCANNER_UUID = str(uuid.uuid5(uuid.NAMESPACE_DNS, 'plustek-opticslim1200-07b3-0413.local'))
FORMATS = {'image/jpeg': 'jpeg', 'image/png': 'png'}
DPIS = (75, 150, 300, 600)


def element(parent, name, text=None):
    ns, local = name.split(':')
    node = ET.SubElement(parent, '{' + (SCAN if ns == 'scan' else PWG) + '}' + local)
    if text is not None:
        node.text = str(text)
    return node


def xml_bytes(root):
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def capabilities():
    root = ET.Element('{' + SCAN + '}ScannerCapabilities')
    for key, value in [('pwg:Version', '2.0'), ('pwg:MakeAndModel', 'Plustek OpticSlim 1200'),
                       ('pwg:SerialNumber', '07B3-0413-LOCAL'), ('scan:UUID', SCANNER_UUID),
                       ('scan:Manufacturer', 'Plustek'), ('scan:ModelName', 'OpticSlim 1200')]:
        element(root, key, value)
    platen = element(root, 'scan:Platen')
    caps = element(platen, 'scan:PlatenInputCaps')
    for key, value in [('MinWidth', 1), ('MaxWidth', 2551), ('MinHeight', 1),
                       ('MaxHeight', 3507), ('MaxPhysicalWidth', 2551), ('MaxPhysicalHeight', 3507)]:
        element(caps, 'scan:' + key, value)
    profiles = element(caps, 'scan:SettingProfiles')
    profile = element(profiles, 'scan:SettingProfile')
    profile.set('name', '0')
    colors = element(profile, 'scan:ColorModes')
    for color in ('RGB24', 'Grayscale8'):
        element(colors, 'scan:ColorMode', color)
    spaces = element(profile, 'scan:ColorSpaces')
    element(spaces, 'scan:ColorSpace', 'RGB')
    resolutions = element(element(profile, 'scan:SupportedResolutions'), 'scan:DiscreteResolutions')
    for dpi in DPIS:
        res = element(resolutions, 'scan:DiscreteResolution')
        element(res, 'scan:XResolution', dpi)
        element(res, 'scan:YResolution', dpi)
    formats = element(profile, 'scan:DocumentFormats')
    for fmt in FORMATS:
        element(formats, 'pwg:DocumentFormat', fmt)
    intents = element(caps, 'scan:SupportedIntents')
    for intent in ('Document', 'TextAndGraphic', 'Photo', 'Preview'):
        element(intents, 'scan:Intent', intent)
    return xml_bytes(root)


def settings(data):
    if len(data) > 65536 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Invalid scan settings document')
    root = ET.fromstring(data)
    if root.tag != '{' + SCAN + '}ScanSettings':
        raise ValueError('Expected eSCL ScanSettings')

    def get(name, default):
        found = [node.text for node in root.iter() if node.tag.split('}')[-1] == name]
        if len(found) > 1:
            raise ValueError('Multiple values for ' + name)
        return found[0] if found else default

    dpi = int(get('XResolution', '150'))
    if dpi not in DPIS or int(get('YResolution', str(dpi))) != dpi:
        raise ValueError('Unsupported resolution')
    mode = get('ColorMode', 'RGB24')
    if mode not in ('RGB24', 'Grayscale8'):
        raise ValueError('Unsupported color mode')
    fmt = get('DocumentFormatExt', None) or get('DocumentFormat', 'image/jpeg')
    if fmt not in FORMATS:
        raise ValueError('Unsupported document format')
    if get('InputSource', 'Platen') != 'Platen':
        raise ValueError('Only platen scanning is available')
    if get('ContentRegionUnits', 'escl:ThreeHundredthsOfInches').split(':')[-1] != 'ThreeHundredthsOfInches':
        raise ValueError('Unsupported region units')
    x, y = int(get('XOffset', '0')), int(get('YOffset', '0'))
    width, height = int(get('Width', '2551')), int(get('Height', '3507'))
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 2551 or y + height > 3507:
        raise ValueError('Scan area out of bounds')
    return {'dpi': dpi, 'mode': 'Color' if mode == 'RGB24' else 'Gray', 'format': fmt,
            'x': x * 25.4 / 300, 'y': y * 25.4 / 300,
            'width': width * 25.4 / 300, 'height': height * 25.4 / 300}


@dataclass
class Job:
    id: str
    options: dict
    created: float = field(default_factory=time.monotonic)
    done: threading.Event = field(default_factory=threading.Event)
    data: bytes = b''
    error: str = ''
    canceled: bool = False
    delivered: bool = False


class Engine:
    def __init__(self, binary, env, device, refresh_device=False):
        self.binary, self.env, self.device = binary, env, device
        self.refresh_device = refresh_device
        self.lock = threading.Lock()
        self.job = None

    def acquire(self, options):
        with self.lock:
            old = self.job
            if old and (not old.done.is_set() or (not old.delivered and not old.canceled and
                                                 time.monotonic() - old.created < 600)):
                return None
            self.job = job = Job(str(uuid.uuid4()), options)
            threading.Thread(target=self.work, args=(job,), daemon=True).start()
            return job

    def work(self, job):
        o = job.options
        try:
            device = self.device
            if self.refresh_device:
                devices = opticslim.get_devices(self.binary, self.env)
                if len(devices) != 1:
                    raise RuntimeError(f'Expected one connected OpticSlim 1200, found {len(devices)}')
                device = devices[0]
            cmd = [self.binary, '-d', device, '--format=' + FORMATS[o['format']],
                   '--mode', o['mode'], '--depth', '8', '--resolution', o['dpi'],
                   '-l', o['x'], '-t', o['y'], '-x', o['width'], '-y', o['height']]
            result = opticslim.run(cmd, env=self.env, capture_output=True, timeout=600)
            signature = b'\x89PNG\r\n\x1a\n' if o['format'] == 'image/png' else b'\xff\xd8'
            if not result.stdout.startswith(signature):
                raise RuntimeError('Invalid image returned by scanning engine')
            if not job.canceled:
                job.data = result.stdout
        except Exception as error:
            job.error = str(error)
            print(f'Acquisition failed: {error}', file=sys.stderr)
        finally:
            job.done.set()

    def status(self):
        root = ET.Element('{' + SCAN + '}ScannerStatus')
        element(root, 'pwg:Version', '2.0')
        job = self.job
        element(root, 'pwg:State', 'Processing' if job and not job.done.is_set() else 'Idle')
        jobs = element(root, 'scan:Jobs')
        if job:
            info = element(jobs, 'scan:JobInfo')
            element(info, 'pwg:JobUri', '/eSCL/ScanJobs/' + job.id)
            element(info, 'pwg:JobUuid', 'urn:uuid:' + job.id)
            state = ('Canceled' if job.canceled else 'Aborted' if job.error else
                     'Completed' if job.delivered else 'Processing')
            element(info, 'pwg:JobState', state)
            element(info, 'scan:ImagesCompleted', int(job.done.is_set() and not job.error))
            element(info, 'scan:ImagesToTransfer', int(bool(job.data) and not job.delivered))
        return xml_bytes(root)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, format, *args):
        super().log_message(format + ' [client=%s]', *args,
                            self.headers.get('User-Agent', 'unspecified')[:160])

    def reply(self, code, body=b'', mime='application/xml', **headers):
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.close_connection = True
        if self.command != 'HEAD':
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self):
        path = self.path.split('?')[0].rstrip('/')
        engine = self.server.engine
        if path == '/eSCL/ScannerCapabilities':
            return self.reply(200, capabilities())
        if path == '/eSCL/ScannerStatus':
            return self.reply(200, engine.status())
        if path in ('', '/eSCL'):
            return self.reply(200, b'Plustek OpticSlim 1200 AirScan bridge\n', 'text/plain')
        job = engine.job
        if job and path == '/eSCL/ScanJobs/' + job.id + '/NextDocument':
            if not job.done.wait(610):
                return self.reply(503)
            with engine.lock:
                if job.canceled or job.delivered:
                    return self.reply(404)
                if job.error:
                    return self.reply(500)
                data, job.data, job.delivered = job.data, b'', True
            return self.reply(200, data, job.options['format'])
        return self.reply(404)

    def do_HEAD(self):
        if self.path.split('?')[0].rstrip('/') in ('/eSCL/ScannerCapabilities', '/eSCL/ScannerStatus'):
            self.do_GET()
        else:
            self.reply(405)

    def do_POST(self):
        if self.path.rstrip('/') != '/eSCL/ScanJobs':
            return self.reply(404)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                return self.reply(400)
            self.connection.settimeout(10)
            options = settings(self.rfile.read(length))
        except (ValueError, ET.ParseError, OSError):
            return self.reply(400)
        job = self.server.engine.acquire(options)
        if job is None:
            return self.reply(503)
        # Relative Locations are valid HTTP and avoid trusting a client Host header.
        return self.reply(201, Location='/eSCL/ScanJobs/' + job.id)

    def do_DELETE(self):
        engine = self.server.engine
        with engine.lock:
            job = engine.job
            if not job or self.path.rstrip('/') != '/eSCL/ScanJobs/' + job.id:
                return self.reply(404)
            # Discard delivery immediately; keep USB serialized until acquisition ends.
            job.canceled, job.data = True, b''
        return self.reply(200)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scanimage')
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--address', default='127.0.0.1', help='Local bind/advertised IPv4 address')
    parser.add_argument('--no-mdns', action='store_true', help='HTTP protocol testing only')
    args = parser.parse_args()
    binary = opticslim.find_scanimage(args.scanimage)
    if not (opticslim.STATE / 'firmware/cism216.fw').exists():
        parser.error('Import the model-specific firmware first with opticslim.py')
    env = opticslim.sane_env(binary)
    devices = opticslim.get_devices(binary, env)
    if len(devices) != 1:
        parser.error(f'Expected exactly one OpticSlim 1200; found {len(devices)}')
    server = ThreadingHTTPServer((args.address, args.port), Handler)
    server.daemon_threads = True
    server.engine = Engine(binary, env, devices[0], refresh_device=True)
    zc = info = None
    try:
        if not args.no_mdns:
            for folder in (opticslim.ROOT / '.runtime/python', opticslim.ROOT / '.cache/python-deps'):
                sys.path.insert(0, str(folder))
            from zeroconf import Zeroconf, ServiceInfo, IPVersion
            zc = Zeroconf(ip_version=IPVersion.V4Only)
            info = ServiceInfo('_uscan._tcp.local.',
                               'Plustek OpticSlim 1200._uscan._tcp.local.',
                               addresses=[socket.inet_aton(args.address)], port=args.port,
                               server='opticslim1200.local.', properties={
                                   'txtvers': '1', 'vers': '2.0', 'rs': 'eSCL',
                                   'ty': 'Plustek OpticSlim 1200', 'is': 'platen',
                                   'pdl': ','.join(FORMATS), 'cs': 'color,grayscale',
                                   'UUID': SCANNER_UUID, 'duplex': 'F', 'note': 'Local USB scanner'})
            zc.register_service(info)
        print(f'AirScan bridge: http://{args.address}:{args.port}/eSCL', flush=True)
        print('Open Image Capture on macOS, or add a scanner in Windows Settings.', flush=True)
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        if zc:
            if info:
                zc.unregister_service(info)
            zc.close()
        server.server_close()


if __name__ == '__main__':
    main()
