"""Stap 3: toon geldige (valid) en ongeldige (invalid) gebruikers apart.

Invalid users (bestaan niet op het systeem) herkennen we aan:
  - "Invalid user X from ..."
  - "Failed password for invalid user X from ..."
  - "input_userauth_request: invalid user X [preauth]"
"""
import re
from pathlib import Path

LOGBESTAND = Path(__file__).parent / "OpenSSH_2k.log"

# Patronen voor geldige users (bestaande accounts)
VALID_PATRONEN = [
    re.compile(r"Accepted password for (\S+) from"),
    re.compile(r"Failed password for (?!invalid user )(\S+) from"),
    re.compile(r"pam_unix\(sshd:auth\):.*\suser=(\S+)"),
    re.compile(r"session opened for user (\S+)"),
]

# Patronen voor ongeldige users (\s+ omdat er soms twee spaties staan)
INVALID_PATRONEN = [
    re.compile(r"Invalid user\s+(\S+) from"),
    re.compile(r"Failed password for invalid user\s+(\S+) from"),
    re.compile(r"input_userauth_request: invalid user\s+(\S+)"),
]


def zoek_users(pad, patronen):
    """Verzamel alle unieke gebruikersnamen die bij de patronen passen."""
    users = set()
    with open(pad, encoding="utf-8", errors="replace") as bestand:
        for regel in bestand:
            for patroon in patronen:
                match = patroon.search(regel)
                if match:
                    users.add(match.group(1))
    return users


def print_lijst(titel, users):
    """Print een gesorteerde lijst, zes namen per regel."""
    print(f"{titel} ({len(users)}):")
    gesorteerd = sorted(users)
    for i in range(0, len(gesorteerd), 6):
        print("  " + "".join(f"{u:<14}" for u in gesorteerd[i:i + 6]))
    print()


def main():
    valid = zoek_users(LOGBESTAND, VALID_PATRONEN)
    invalid = zoek_users(LOGBESTAND, INVALID_PATRONEN)
    print_lijst("VALID users (bestaande accounts)", valid)
    print_lijst("INVALID users (bestaan niet op het systeem)", invalid)


if __name__ == "__main__":
    main()
