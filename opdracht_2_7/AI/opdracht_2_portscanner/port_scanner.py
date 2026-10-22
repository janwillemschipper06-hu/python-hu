# opdracht 2 - portscanner
# controleert of poort 22 (SSH) of 3389 (RDP) openstaat op een ip-adres
# gebruikt socket met een korte timeout
# ip wordt gevraagd via input() of meegegeven via argv
# met het argument --subnet wordt het hele subnet 192.168.1.0/28 gescand

import socket
import sys
import ipaddress
from concurrent.futures import ThreadPoolExecutor

# poorten die we willen controleren
POORTEN = {22: "SSH", 3389: "RDP"}

# timeout in seconden (ongeveer 0.5s)
TIMEOUT = 0.5


def scan_poort(ip, poort):
    # maak een socket en probeer verbinding te maken
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)
    resultaat = sock.connect_ex((ip, poort))  # 0 betekent open
    sock.close()
    return resultaat == 0


def scan_ip(ip):
    # scan beide poorten op 1 ip-adres en druk het resultaat af
    for poort, naam in POORTEN.items():
        if scan_poort(ip, poort):
            print(f"{ip}: poort {poort} ({naam}) is OPEN")
        else:
            print(f"{ip}: poort {poort} ({naam}) is dicht")


# scan all ips in subnet 192.168.1.0/28
def scan_subnet(subnet_tekst="192.168.1.0/28"):
    netwerk = ipaddress.ip_network(subnet_tekst)
    # gebruik een ThreadPoolExecutor zodat het snel gaat
    with ThreadPoolExecutor(max_workers=50) as pool:
        # scan elke host in het subnet
        pool.map(scan_ip, [str(ip) for ip in netwerk.hosts()])


if __name__ == "__main__":
    # als --subnet is meegegeven, scan het hele subnet
    if len(sys.argv) > 1 and sys.argv[1] == "--subnet":
        # eventueel een eigen subnet als tweede argument, anders standaard
        if len(sys.argv) > 2:
            scan_subnet(sys.argv[2])
        else:
            scan_subnet()
    elif len(sys.argv) > 1:
        # een ip-adres meegegeven via argv
        scan_ip(sys.argv[1])
    else:
        # vraag het ip-adres via input()
        ip = input("Geef een ip-adres om te scannen: ")
        scan_ip(ip)
