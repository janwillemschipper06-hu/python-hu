"""Opdracht 2.2.3 - deel 2

Leest message.txt en signature.bin en controleert de ondertekening met de
publieke sleutel. Print "Signature OK" of "Signature NOK!!!".
"""

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

# --- publieke sleutel inlezen ---
with open("opdracht_2.2/public_key.pem", "rb") as f:
    public_key = RSA.import_key(f.read())

# --- bestand lezen (binary!) en hashen ---
with open("opdracht_2.2/message.txt", "rb") as f:
    message = f.read()

h = SHA256.new(message)  # not SHA as written in the documentation

# --- ondertekening inlezen ---
with open("opdracht_2.2/signature.bin", "rb") as f:
    signature = f.read()

# --- controleren ---
try:
    pkcs1_15.new(public_key).verify(h, signature)
    print("Signature OK")
except (ValueError, TypeError):
    print("Signature NOK!!!")
