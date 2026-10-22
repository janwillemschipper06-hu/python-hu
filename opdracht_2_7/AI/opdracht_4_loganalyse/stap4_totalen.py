"""Stap 4: totalen van unieke users en het aantal logregels per categorie."""
import re
from collections import Counter
from pathlib import Path

LOGBESTAND = Path(__file__).parent / "OpenSSH_2k.log"

VALID_PATRONEN = [
    re.compile(r"Accepted password for (\S+) from"),
    re.compile(r"Failed password for (?!invalid user )(\S+) from"),
    re.compile(r"pam_unix\(sshd:auth\):.*\suser=(\S+)"),
    re.compile(r"session opened for user (\S+)"),
]

INVALID_PATRONEN = [
    re.compile(r"Invalid user\s+(\S+) from"),
    re.compile(r"Failed password for invalid user\s+(\S+) from"),
    re.compile(r"input_userauth_request: invalid user\s+(\S+)"),
]

# Categorieen van logregels die we willen tellen
CATEGORIEEN = {
    "Accepted password (gelukte login)": re.compile(r"Accepted password for "),
    "Failed password (valid user)": re.compile(r"Failed password for (?!invalid user )"),
    "Failed password (invalid user)": re.compile(r"Failed password for invalid user "),
    "Invalid user ... from": re.compile(r"Invalid user .* from"),
    "pam_unix authentication failure": re.compile(r"pam_unix\(sshd:auth\): authentication failure"),
    "Session opened": re.compile(r"session opened for user "),
    "POSSIBLE BREAK-IN ATTEMPT": re.compile(r"POSSIBLE BREAK-IN ATTEMPT"),
}


def analyseer(pad):
    """Lees het log en geef (valid users, invalid users, tellingen, aantal regels) terug."""
    valid, invalid = set(), set()
    tellingen = Counter()
    aantal_regels = 0
    with open(pad, encoding="utf-8", errors="replace") as bestand:
        for regel in bestand:
            aantal_regels += 1
            for patroon in VALID_PATRONEN:
                match = patroon.search(regel)
                if match:
                    valid.add(match.group(1))
            for patroon in INVALID_PATRONEN:
                match = patroon.search(regel)
                if match:
                    invalid.add(match.group(1))
            for naam, patroon in CATEGORIEEN.items():
                if patroon.search(regel):
                    tellingen[naam] += 1
    return valid, invalid, tellingen, aantal_regels


def main():
    valid, invalid, tellingen, aantal_regels = analyseer(LOGBESTAND)

    print("=== Unieke gebruikers ===")
    print(f"Unieke valid users   : {len(valid)}")
    print(f"Unieke invalid users : {len(invalid)}")
    print(f"Totaal unieke users  : {len(valid | invalid)}")
    print()
    print("=== Aantal logregels per categorie ===")
    print(f"Totaal aantal logregels: {aantal_regels}")
    for naam in CATEGORIEEN:
        print(f"  {naam:<36}: {tellingen[naam]}")
    pogingen = (tellingen["Accepted password (gelukte login)"]
                + tellingen["Failed password (valid user)"]
                + tellingen["Failed password (invalid user)"])
    print()
    print(f"Totaal wachtwoordpogingen (Accepted + Failed regels): {pogingen}")


if __name__ == "__main__":
    main()
