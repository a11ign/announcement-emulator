"""The run's certificate authority (A11-165): made fresh for each run, kept where it was made, never committed.

    <replay venv python> ca.py init <dir>      writes <dir>/mitmproxy-ca.pem (the key, mode 600) and mitmproxy-ca-cert.pem, and prints their thumbprint and SPKI hash as JSON

The fleet's Edge trusts the certificate (Trusted Root store) and the emulator's Chrome trusts its SPKI hash (`--ignore-certificate-errors-spki-list`), for the length of the run only.
Web Page Replay's own bundled certificate is not used: its private key is public."""
import sys, os, json, base64, hashlib
from cryptography import x509
from cryptography.hazmat.primitives import serialization


def identify(cert_pem_path):
    """The two names of a certificate the run uses: its SHA-1 thumbprint (Windows' store, upper-case hex) and the base64 SHA-256 of its public key (Chrome's flag)."""
    with open(cert_pem_path, 'rb') as f: cert = x509.load_pem_x509_certificate(f.read())
    der = cert.public_bytes(serialization.Encoding.DER)
    spki = cert.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return {'thumbprint': hashlib.sha1(der).hexdigest().upper(), 'spki': base64.b64encode(hashlib.sha256(spki).digest()).decode(), 'cert': os.path.abspath(cert_pem_path)}


def init(directory):
    from mitmproxy.certs import CertStore
    os.makedirs(directory, mode=0o700, exist_ok=True)
    CertStore.from_store(directory, 'mitmproxy', 2048)
    os.chmod(os.path.join(directory, 'mitmproxy-ca.pem'), 0o600)
    return identify(os.path.join(directory, 'mitmproxy-ca-cert.pem'))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'init': print(json.dumps(init(sys.argv[2])))
    elif len(sys.argv) == 3 and sys.argv[1] == 'identify': print(json.dumps(identify(sys.argv[2])))
    else: sys.exit(__doc__)
