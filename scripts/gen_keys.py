"""Generate RSA-2048 keypair for the auth service."""
import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

CERT_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "auth", "certs")
os.makedirs(CERT_DIR, exist_ok=True)

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

priv_path = os.path.join(CERT_DIR, "private.pem")
with open(priv_path, "wb") as f:
    f.write(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))

pub_path = os.path.join(CERT_DIR, "public.pem")
with open(pub_path, "wb") as f:
    f.write(key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))

print("✓ Keys generated")
print(f"  private: {priv_path}")
print(f"  public:  {pub_path}")
