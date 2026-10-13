"""File: test_live.py
Modification: 2026-10-12 — RCON wire protocol + response guard tests with local fake server.
"""
from pathlib import Path
import socket
import struct
import sys
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lowy_outpost_finder.live import RCON, RCONError, query_marked


class LiveTests(unittest.TestCase):
    def test_marked_status_variants(self):
        self.assertFalse(query_marked('Chunk [0, 0] is not marked as force loaded in minecraft:overworld'))
        self.assertTrue(query_marked('Chunk [0, 0] is marked as force loaded in minecraft:overworld'))
        self.assertIsNone(query_marked('Unknown or incomplete command'))

    def test_rcon_local_mock_packets(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        commands = []
        def exact(conn, n):
            result = b''
            while len(result) < n:
                result += conn.recv(n - len(result))
            return result
        def respond(conn, rid, kind, body):
            raw = struct.pack('<ii', rid, kind) + body.encode() + b'\0\0'
            conn.sendall(struct.pack('<i', len(raw)) + raw)
        def serve():
            with listener:
                conn, _ = listener.accept()
                with conn:
                    for i in range(2):
                        n = struct.unpack('<i', exact(conn, 4))[0]
                        raw = exact(conn, n)
                        rid, kind = struct.unpack_from('<ii', raw)
                        command = raw[8:-2].decode()
                        commands.append((kind, command))
                        if i == 0:
                            respond(conn, 13, 0, '')
                            respond(conn, 13, 2, '')
                        else:
                            respond(conn, 23, 0, 'OK')
        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        with RCON('127.0.0.1', port, 'secret') as conn:
            self.assertEqual(conn.command('save-all flush'), 'OK')
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(commands, [(3, 'secret'), (2, 'save-all flush')])


if __name__ == '__main__':
    unittest.main()
