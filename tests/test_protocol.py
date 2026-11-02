"""Protocol tests can use the compiled SANE test backend, never physical USB."""
import http.client
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import airscan_bridge as bridge
import opticslim

REQUEST = b'''<scan:ScanSettings xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03"
 xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
 <pwg:Version>2.0</pwg:Version><scan:InputSource>Platen</scan:InputSource>
 <scan:ColorMode>RGB24</scan:ColorMode><scan:XResolution>75</scan:XResolution>
 <scan:YResolution>75</scan:YResolution><scan:DocumentFormatExt>image/png</scan:DocumentFormatExt>
 <pwg:ScanRegions><pwg:ScanRegion><pwg:Width>1500</pwg:Width><pwg:Height>1500</pwg:Height>
 <pwg:XOffset>0</pwg:XOffset><pwg:YOffset>0</pwg:YOffset></pwg:ScanRegion></pwg:ScanRegions>
 </scan:ScanSettings>'''


class ValidationTests(unittest.TestCase):
    def test_web_page_disguised_as_firmware_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'cism216.fw'
            path.write_bytes(b'<!DOCTYPE html><html>' + b' ' * 8192)
            with self.assertRaises(ValueError):
                opticslim.firmware_info(path)

    def test_scan_settings_reject_unsafe_or_unavailable_modes(self):
        for invalid in [REQUEST.replace(b'>1500<', b'>999999<', 1),
                        REQUEST.replace(b'RGB24', b'RGB48'),
                        REQUEST.replace(b'>75<', b'>1200<', 1),
                        REQUEST.replace(b'Platen', b'Feeder'),
                        b'<!DOCTYPE x><x/>']:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    bridge.settings(invalid)

    def test_capabilities_are_well_formed_and_do_not_advertise_feeder(self):
        root = ET.fromstring(bridge.capabilities())
        self.assertIsNotNone(root.find('.//{' + bridge.SCAN + '}PlatenInputCaps'))
        self.assertIsNone(root.find('.//{' + bridge.SCAN + '}Adf'))


@unittest.skipUnless(os.environ.get('SCAN_TEST_BINARY'), 'Requires compiled SANE test backend')
class RealEngineProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        conf = Path(cls.temp.name)
        (conf / 'dll.conf').write_text('test\n')
        (conf / 'test.conf').write_text('number_of_devices 1\n')
        binary = Path(os.environ['SCAN_TEST_BINARY']).resolve()
        env = os.environ.copy()
        env['SANE_CONFIG_DIR'] = opticslim.native_path(conf, binary)
        cls.server = bridge.ThreadingHTTPServer(('127.0.0.1', 0), bridge.Handler)
        cls.server.engine = bridge.Engine(binary, env, 'test:0')
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=30)
        conn.request(method, path, body=body)
        response = conn.getresponse()
        code, headers, data = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return code, headers, data

    def test_real_png_transfer_busy_and_job_completion(self):
        self.assertEqual(200, self.request('GET', '/eSCL/ScannerCapabilities')[0])
        code, headers, _ = self.request('POST', '/eSCL/ScanJobs', REQUEST)
        self.assertEqual(201, code)
        location = headers['Location']
        self.assertEqual(503, self.request('POST', '/eSCL/ScanJobs', REQUEST)[0])
        self.assertEqual(405, self.request('HEAD', location + '/NextDocument')[0])
        code, headers, image = self.request('GET', location + '/NextDocument')
        self.assertEqual(200, code)
        self.assertEqual('image/png', headers['Content-Type'])
        self.assertEqual(b'\x89PNG\r\n\x1a\n', image[:8])
        width, height = struct.unpack('>II', image[16:24])
        # 1500/300 inches = exactly 127 mm, avoiding the test backend's 1 mm quantization.
        self.assertEqual((375, 375), (width, height))
        offset, payload = 8, b''
        while offset < len(image):
            size = struct.unpack('>I', image[offset:offset + 4])[0]
            kind = image[offset + 4:offset + 8]
            data = image[offset + 8:offset + 8 + size]
            crc = struct.unpack('>I', image[offset + 8 + size:offset + 12 + size])[0]
            self.assertEqual(zlib.crc32(kind + data), crc)
            if kind == b'IDAT':
                payload += data
            offset += 12 + size
        self.assertTrue(zlib.decompress(payload))
        self.assertEqual(404, self.request('GET', location + '/NextDocument')[0])
        self.assertEqual(200, self.request('DELETE', location)[0])


if __name__ == '__main__':
    unittest.main()
