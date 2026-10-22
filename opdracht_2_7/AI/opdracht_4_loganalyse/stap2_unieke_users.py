"""Stap 2: haal alle unieke (geldige) gebruikersnamen uit het OpenSSH log.

Geldige users herkennen we aan deze patronen in het log:
  - "Accepted password for X from ..."
  - "Failed password for X from ..."   (maar NIET "for invalid user X")
  - "pam_unix(sshd:auth): ... user=X"
  - "session opened for user X"
"""
import re
from pathlib import Path

# Het logbestand staat in dezelfde map als dit script
LOGBESTAND = Path(__file__).parent / "OpenSSH_2k.log"

# Reguliere expressies voor de patronen met een geldige gebruikersnaam
PATRONEN = [
    re.compile(r"Accepted password for (\S+) from"),
    re.compile(r"Failed password for (?!invalid user )(\S+) from"),
    re.compile(r"pam_unix\(sshd:auth\):.*\suser=(\S+)"),
    re.compile(r"session opened for user (\S+)"),
]


def zoek_geldige_users(pad):
    """Lees het log regel voor regel en verzamel unieke geldige users."""
    users = set()
    with open(pad, encoding="utf-8", errors="replace") as bestand:
        for regel in bestand:
            for patroon in PATRONEN:
                match = patroon.search(regel)
                if match:
                    users.add(match.group(1))
    return users


def main():
    users = zoek_geldige_users(LOGBESTAND)
    print(f"Unieke geldige gebruikersnamen in {LOGBESTAND.name}:")
    for user in sorted(users):
        print(f"  - {user}")
    print(f"Totaal: {len(users)} unieke geldige users")


if __name__ == "__main__":
    main()
