"""A WebSocket client for the DevTools endpoint of the test's browser, with nothing but the standard library (the bundle's Python carries no packages beyond NVDA's own)."""
import base64, hashlib, os, socket, struct
from urllib.parse import urlsplit

GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


class WebSocket:
    def __init__(self, url, timeout=5.0):
        u = urlsplit(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = u.path + ('?' + u.query if u.query else '')
        # no Origin header: Chrome refuses a connection that names an origin it was not told to allow
        self.sock.sendall(f'GET {path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode())
        head = b''
        while b'\r\n\r\n' not in head:
            chunk = self.sock.recv(4096)
            if not chunk: raise ConnectionError('the browser closed the connection during the handshake')
            head += chunk
        head, self._buffer = head.split(b'\r\n\r\n', 1)
        if b' 101 ' not in head.split(b'\r\n', 1)[0]: raise ConnectionError(head.split(b'\r\n', 1)[0].decode(errors='replace'))
        expected = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        if expected.lower().encode() not in head.lower(): raise ConnectionError('the handshake answer does not carry the key it should')
        self.sock.settimeout(None)

    def send(self, text):
        payload = text.encode()
        header = bytearray([0x81])
        n = len(payload)
        if n < 126: header.append(0x80 | n)
        elif n < 65536: header += bytes([0x80 | 126]) + struct.pack('>H', n)
        else: header += bytes([0x80 | 127]) + struct.pack('>Q', n)
        mask = os.urandom(4)
        self.sock.sendall(bytes(header) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _read(self, n):
        while len(self._buffer) < n:
            chunk = self.sock.recv(65536)
            if not chunk: raise ConnectionError('the browser closed the connection')
            self._buffer += chunk
        out, self._buffer = self._buffer[:n], self._buffer[n:]
        return out

    def recv(self):
        """The next text message, whole (continuation frames joined). Answers a ping, and raises ConnectionError when the browser closes."""
        message = b''
        while True:
            b0, b1 = self._read(2)
            opcode, n = b0 & 0x0F, b1 & 0x7F
            if n == 126: n = struct.unpack('>H', self._read(2))[0]
            elif n == 127: n = struct.unpack('>Q', self._read(8))[0]
            mask = self._read(4) if b1 & 0x80 else None
            data = self._read(n)
            if mask: data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8: raise ConnectionError('the browser closed the connection')
            if opcode == 0x9: self._pong(data); continue
            if opcode == 0xA: continue
            message += data
            if b0 & 0x80: return message.decode()

    def _pong(self, data):
        mask = os.urandom(4)
        self.sock.sendall(bytes([0x8A, 0x80 | len(data)]) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def close(self):
        try: self.sock.close()
        except OSError: pass
