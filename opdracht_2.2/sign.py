"""Opdracht 2.2.3 - deel 1

Maakt een RSA keypair (private_key.pem + public_key.pem), leest message.txt
binair in en schrijft de digitale ondertekening naar signature.bin.
"""

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

message_file = "opdracht_2.2/message.txt"
signature_file = "opdracht_2.2/signature.bin"
private_key_file = "opdracht_2.2/private_key.pem"
public_key_file = "opdracht_2.2/public_key.pem"

# --- keypair maken ---
key = RSA.generate(2048)

private_key = key.export_key()
with open(private_key_file, "wb") as f:
    f.write(private_key)


public_key = key.publickey().export_key()
with open(public_key_file, "wb") as f:
    f.write(public_key)

print("Keypair gemaakt:", private_key_file, "en", public_key_file)

# --- bestand lezen (binary!) en hashen ---
with open(message_file, "rb") as f:  # 'rb' !
    message = f.read()
    

h = SHA256.new(message)  # not SHA as written in the documentation

# --- ondertekenen ---
signature = pkcs1_15.new(key).sign(h)

with open(signature_file, "wb") as f:
    f.write(signature)

print("Ondertekening geschreven naar", signature_file)
