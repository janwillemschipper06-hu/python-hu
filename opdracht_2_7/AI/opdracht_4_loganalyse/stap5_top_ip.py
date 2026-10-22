"""Stap 5: vanaf welk IP-adres wordt het meest (geprobeerd) ingelogd?

Een inlogpoging = een regel met "Accepted password" of "Failed password".
Bij "message repeated N times: [ Failed password ...]" tellen we N pogingen.
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

LOGBESTAND = Path(__file__).parent / "OpenSSH_2k.log"

# Groep 1 = Accepted/Failed, groep 2 = gebruikersnaam, groep 3 = IP-adres
POGING = re.compile(
    r"(Accepted|Failed) password for (?:invalid user\s+)?(\S+) from (\d+\.\d+\.\d+\.\d+)"
)
HERHAALD = re.compile(r"message repeated (\d+) times")


def lees_pogingen(pad):
    """Tel pogingen per IP, gelukte logins per IP en users per IP."""
    pogingen_per_ip = Counter()
    gelukt_per_ip = Counter()
    users_per_ip = defaultdict(Counter)
    with open(pad, encoding="utf-8", errors="replace") as bestand:
        for regel in bestand:
            match = POGING.search(regel)
            if not match:
                continue
            resultaat, user, ip = match.groups()
            herhaald = HERHAALD.search(regel)
            aantal = int(herhaald.group(1)) if herhaald else 1
            pogingen_per_ip[ip] += aantal
            users_per_ip[ip][user] += aantal
            if resultaat == "Accepted":
                gelukt_per_ip[ip] += aantal
    return pogingen_per_ip, gelukt_per_ip, users_per_ip


def toon_users(ip, users_per_ip):
    """Print welke users vanaf dit IP (proberen) in te loggen, met aantallen."""
    for user, aantal in users_per_ip[ip].most_common():
        print(f"    {user:<15} {aantal:>4}x")


def main():
    pogingen, gelukt, users_per_ip = lees_pogingen(LOGBESTAND)

    print("=== Top 5 IP-adressen met de meeste inlogpogingen ===")
    for plek, (ip, aantal) in enumerate(pogingen.most_common(5), start=1):
        print(f"  {plek}. {ip:<16} {aantal:>4} pogingen "
              f"({len(users_per_ip[ip])} verschillende users)")
    print()

    top_ip, top_aantal = pogingen.most_common(1)[0]
    print(f"IP met de meeste inlogpogingen: {top_ip} ({top_aantal} pogingen)")
    print("  Users vanaf dit IP:")
    toon_users(top_ip, users_per_ip)
    print()

    if gelukt:
        print("=== IP-adressen met succesvolle logins ===")
        for ip, aantal in gelukt.most_common(5):
            print(f"  {ip:<16} {aantal} gelukte login(s)")
        succes_ip, succes_aantal = gelukt.most_common(1)[0]
        print(f"IP met de meeste succesvolle logins: {succes_ip} ({succes_aantal}x)")
        print("  Users vanaf dit IP:")
        toon_users(succes_ip, users_per_ip)
    else:
        print("Er zijn geen succesvolle logins gevonden.")


if __name__ == "__main__":
    main()
