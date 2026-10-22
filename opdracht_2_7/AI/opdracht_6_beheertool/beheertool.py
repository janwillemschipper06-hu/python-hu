"""Beheertool: een simpel menu met netwerk- en systeemfuncties.

Opties:
  1. Ping een host
  2. Port scanner (controleer of poort 22 / SSH open staat)
  3. IP scanner (scan een subnet op hosts die "up" zijn)
  4. DNS lookup (hostname -> IP's en reverse lookup)
  5. Systeeminformatie
  0. Afsluiten
"""
import ipaddress
import os
import platform
import shutil
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

MAX_HOSTS_ZONDER_WAARSCHUWING = 1024


def is_windows():
    """Geeft True terug als we op Windows draaien."""
    return platform.system().lower() == "windows"


def ping_commando(host, aantal=4, timeout_sec=None):
    """Bouw het juiste ping-commando voor Windows (-n) of Linux/macOS (-c)."""
    if is_windows():
        commando = ["ping", "-n", str(aantal)]
        if timeout_sec is not None:
            commando += ["-w", str(int(timeout_sec * 1000))]  # milliseconden
    else:
        commando = ["ping", "-c", str(aantal)]
        if timeout_sec is not None:
            commando += ["-W", str(max(1, int(timeout_sec)))]  # seconden
    return commando + [host]


def vraag_ip(tekst):
    """Vraag om een IP-adres en controleer het. Geeft None bij ongeldige invoer."""
    invoer = input(tekst).strip()
    try:
        return str(ipaddress.ip_address(invoer))
    except ValueError:
        print(f"Fout: '{invoer}' is geen geldig IP-adres.")
        return None


# ---------- Optie 1: ping ----------
def optie_ping():
    host = input("Welke host wil je pingen (IP of hostname)? ").strip()
    if not host or " " in host or host.startswith("-"):
        print("Fout: ongeldige host.")
        return
    print(f"Bezig met pingen van {host}...\n")
    try:
        resultaat = subprocess.run(ping_commando(host), capture_output=True,
                                   text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as fout:
        print(f"Fout bij uitvoeren van ping: {fout}")
        return
    print(resultaat.stdout.strip() or resultaat.stderr.strip())
    if resultaat.returncode == 0:
        print(f"\nResultaat: {host} is bereikbaar.")
    else:
        print(f"\nResultaat: {host} is NIET bereikbaar.")


# ---------- Optie 2: port scanner ----------
def poort_open(ip, poort, timeout=2):
    """Probeer een TCP-verbinding te maken. True = poort staat open."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((ip, poort)) == 0


def optie_portscan():
    ip = vraag_ip("Welk IP-adres wil je controleren op poort 22 (SSH)? ")
    if ip is None:
        return
    try:
        if poort_open(ip, 22):
            print(f"Poort 22 (SSH) op {ip} staat OPEN.")
        else:
            print(f"Poort 22 (SSH) op {ip} is DICHT of gefilterd.")
    except OSError as fout:
        print(f"Fout bij verbinden: {fout}")


# ---------- Optie 3: IP scanner ----------
def host_is_up(ip):
    """Ping een host 1 keer met korte timeout. Geeft True als hij antwoordt."""
    try:
        resultaat = subprocess.run(ping_commando(ip, aantal=1, timeout_sec=1),
                                   capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    # Op Windows geeft "Destination host unreachable" soms ook returncode 0,
    # daarom controleren we ook op "TTL=" in de uitvoer.
    if is_windows():
        return resultaat.returncode == 0 and "ttl=" in resultaat.stdout.lower()
    return resultaat.returncode == 0


def optie_ipscan():
    invoer = input("Welk subnet wil je scannen (bijv. 192.168.1.0/24)? ").strip()
    try:
        netwerk = ipaddress.ip_network(invoer, strict=False)
    except ValueError:
        print(f"Fout: '{invoer}' is geen geldig subnet.")
        return

    # Bij /31 en /32 geeft hosts() alle adressen, anders zonder netwerk/broadcast
    hosts = [str(h) for h in netwerk.hosts()] or [str(netwerk.network_address)]
    print(f"Subnet {netwerk} bevat {len(hosts)} host(s).")
    if len(hosts) > MAX_HOSTS_ZONDER_WAARSCHUWING:
        antwoord = input("Waarschuwing: dit is een groot subnet en kan lang duren. "
                         "Doorgaan? (j/n) ").strip().lower()
        if antwoord != "j":
            print("Scan afgebroken.")
            return

    print("Bezig met scannen...")
    with ThreadPoolExecutor(max_workers=64) as pool:
        resultaten = list(pool.map(host_is_up, hosts))

    actief = [ip for ip, up in zip(hosts, resultaten) if up]
    if actief:
        print(f"{len(actief)} host(s) up:")
        for ip in actief:
            print(f"  [UP] {ip}")
    else:
        print("Geen actieve hosts gevonden.")


# ---------- Optie 4: DNS lookup (zelf bedacht) ----------
def optie_dns():
    naam = input("Welke hostname wil je opzoeken (bijv. google.com)? ").strip()
    if not naam:
        print("Fout: geen hostname ingevoerd.")
        return
    try:
        info = socket.getaddrinfo(naam, None)
    except socket.gaierror as fout:
        print(f"Fout: kan '{naam}' niet opzoeken ({fout}).")
        return

    # Unieke IP-adressen verzamelen, volgorde behouden
    adressen = []
    for item in info:
        ip = item[4][0]
        if ip not in adressen:
            adressen.append(ip)

    print(f"IP-adressen van {naam}:")
    for ip in adressen:
        try:
            reverse = socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror, OSError):
            reverse = "(geen reverse DNS)"
        print(f"  {ip:<40} -> reverse: {reverse}")


# ---------- Optie 5: systeeminformatie (zelf bedacht) ----------
def lokaal_ip():
    """Bepaal het lokale IP via een UDP-socket (er wordt niets verstuurd)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "onbekend"


def optie_systeeminfo():
    schijf = shutil.disk_usage(os.path.abspath(os.sep))
    gb = 1024 ** 3
    print(f"Hostname      : {socket.gethostname()}")
    print(f"OS            : {platform.system()} {platform.release()} ({platform.version()})")
    print(f"Python-versie : {platform.python_version()}")
    print(f"Lokaal IP     : {lokaal_ip()}")
    print(f"CPU-aantal    : {os.cpu_count()}")
    print(f"Schijf ({os.path.abspath(os.sep)}) : totaal {schijf.total / gb:.1f} GB, "
          f"gebruikt {schijf.used / gb:.1f} GB, vrij {schijf.free / gb:.1f} GB")


# ---------- Hoofdmenu ----------
MENU = {
    "1": ("Ping een host", optie_ping),
    "2": ("Port scanner (poort 22 / SSH)", optie_portscan),
    "3": ("IP scanner (subnet)", optie_ipscan),
    "4": ("DNS lookup", optie_dns),
    "5": ("Systeeminformatie", optie_systeeminfo),
}


def toon_menu():
    print("\n===== BEHEERTOOL =====")
    for nummer, (omschrijving, _) in MENU.items():
        print(f"{nummer}. {omschrijving}")
    print("0. Afsluiten")


def main():
    while True:
        toon_menu()
        try:
            keuze = input("Maak een keuze: ").strip()
        except EOFError:
            # Geen invoer meer (bijv. bij gepipete invoer): netjes stoppen
            print("\nGeen invoer meer, afsluiten.")
            break
        print()
        if keuze == "0":
            print("Tot ziens!")
            break
        if keuze in MENU:
            try:
                MENU[keuze][1]()
            except EOFError:
                print("\nGeen invoer meer, afsluiten.")
                break
        else:
            print("Ongeldige keuze, kies 0 t/m 5.")


if __name__ == "__main__":
    sys.exit(main())
