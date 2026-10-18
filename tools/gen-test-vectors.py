"""Generate the Chapter 45 test vectors (docs/spec/15-implementation-guide.md).

Oracles: pyca/cryptography, PyNaCl (libsodium) and the openssl CLI must produce
identical Ed25519 signatures; CIDs and the IPNS name are computed by hand and with
the multiformats library and must match. Requires: pip install cryptography pynacl
multiformats; openssl on PATH. Prints the values; Chapter 45 hardcodes them.
"""
import base64, hashlib, json, subprocess, sys, tempfile, os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import nacl.signing
from multiformats import CID, multihash, multibase

SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")  # RFC 8032 7.1 TEST 1
PUB_RFC = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
SIG_EMPTY_RFC = ("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")

def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def sign_all(msg, use_openssl=True):
    s1 = Ed25519PrivateKey.from_private_bytes(SEED).sign(msg)
    s2 = nacl.signing.SigningKey(SEED).sign(msg).signature
    if not use_openssl:
        assert s1 == s2, 'Ed25519 implementations disagree'
        return s1
    der = bytes.fromhex("302e020100300506032b657004220420") + SEED
    with tempfile.TemporaryDirectory() as d:
        open(f"{d}/k.der","wb").write(der); open(f"{d}/m","wb").write(msg)
        subprocess.run(["openssl","pkey","-inform","DER","-in",f"{d}/k.der","-out",f"{d}/k.pem"],check=True,capture_output=True)
        s3 = subprocess.run(["openssl","pkeyutl","-sign","-rawin","-inkey",f"{d}/k.pem","-in",f"{d}/m"],check=True,capture_output=True).stdout
    assert s1 == s2 == s3, "Ed25519 implementations disagree"
    return s1

pub = Ed25519PrivateKey.from_private_bytes(SEED).public_key().public_bytes_raw()
assert pub.hex() == PUB_RFC, "public key mismatch with RFC 8032"
assert sign_all(b"", use_openssl=False).hex() == SIG_EMPTY_RFC, "RFC 8032 TEST 1 signature mismatch"
print("oracle check: RFC 8032 TEST 1 reproduced by pyca and PyNaCl (OpenSSL CLI cannot sign empty input)")

# did:key and IPNS name for the test key
didkey_mb = multibase.encode(bytes([0xed,0x01]) + pub, "base58btc")
did = "did:key:" + didkey_mb
pb = bytes([0x08,0x01,0x12,0x20]) + pub
ipns_lib = CID("base36", 1, "libp2p-key", multihash.wrap(pb, "identity")).encode("base36")
# by hand: CIDv1(0x01) libp2p-key(0x72) identity(0x00) len 0x24
raw = bytes([0x01,0x72,0x00,0x24]) + pb
n = int.from_bytes(raw,"big"); a="0123456789abcdefghijklmnopqrstuvwxyz"; out=""
while n: n,r = divmod(n,36); out = a[r]+out
ipns_hand = "k" + out
assert ipns_lib == ipns_hand, (ipns_lib, ipns_hand)
print("did:key:", did); print("ipns:", ipns_lib, len(ipns_lib))

activity = ('{"@context":["https://www.w3.org/ns/activitystreams","https://corundum.example/ns/v1"],'
            '"@type":"Note","attributedTo":"' + did + '","content":"Hello, world!",'
            '"published":"2025-06-01T12:00:00Z","seq":0}').encode()
json.loads(activity)
cid_lib = str(CID("base32", 1, "raw", multihash.digest(activity, "sha2-256")))
cid_hand = "b" + base64.b32encode(bytes([0x01,0x55,0x12,0x20]) + hashlib.sha256(activity).digest()).decode().lower().rstrip("=")
assert cid_lib == cid_hand
print("activity bytes:", activity.decode()); print("len", len(activity)); print("sha256", hashlib.sha256(activity).hexdigest()); print("id", cid_lib)

hdr = ('{"alg":"Ed25519","b64":false,"crit":["b64","corundumType"],"corundumType":"Activity","kid":"' + ipns_lib + '"}').encode()
json.loads(hdr)
prot = b64u(hdr)
sig = sign_all(prot.encode() + b"." + activity)
Ed25519PrivateKey.from_private_bytes(SEED).public_key().verify(sig, prot.encode()+b"."+activity)
sr = json.dumps({"signatures":[{"protected":prot,"signature":b64u(sig)}]}, separators=(",",":")).encode()
print("protected header:", hdr.decode()); print("protected b64u:", prot); print("signature hex:", sig.hex())
print("SigningRecord:", sr.decode())
print("SigningRecord CID:", CID("base32",1,"raw",multihash.digest(sr,"sha2-256")))

def jws(header_bytes, payload):
    p = b64u(header_bytes)
    return p, b64u(sign_all(p.encode() + b"." + payload))

neg = {
 "wrong-type": ('{"alg":"Ed25519","b64":false,"crit":["b64","corundumType"],"corundumType":"RootManifest","kid":"' + ipns_lib + '"}').encode(),
 "extra-param": ('{"alg":"Ed25519","b64":false,"crit":["b64","corundumType"],"corundumType":"Activity","kid":"' + ipns_lib + '","typ":"JOSE"}').encode(),
 "deprecated-alg": ('{"alg":"EdDSA","b64":false,"crit":["b64","corundumType"],"corundumType":"Activity","kid":"' + ipns_lib + '"}').encode(),
}
for k, h in neg.items():
    json.loads(h); p, sg = jws(h, activity)
    print(f"NEG {k}: header={h.decode()}"); print(f"NEG {k}: protected={p}"); print(f"NEG {k}: signature={sg}")
tampered = activity.replace(b"Hello, world!", b"Hello, world.")
assert len(tampered) == len(activity)
try:
    Ed25519PrivateKey.from_private_bytes(SEED).public_key().verify(sig, prot.encode()+b"."+tampered); print("TAMPER VERIFIED?!"); sys.exit(1)
except Exception as e:
    print("NEG tampered-payload: original signature fails over", tampered.decode()[:0] + "payload with '!' changed to '.'", type(e).__name__)
