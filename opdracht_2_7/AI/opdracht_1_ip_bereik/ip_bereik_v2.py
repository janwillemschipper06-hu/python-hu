# opdracht 1 - ip bereik versie 2
# verbeterde versie: drukt de ip-adressen onder elkaar af
# met bij elk adres het subnet en het masker
# netwerk- en broadcastadres worden gemarkeerd
# het subnet is instelbaar via een command-line argument (standaard 192.168.1.0/28)

import ipaddress
import sys

# standaard subnet
standaard_subnet = "192.168.1.0/28"

# als er een argument is meegegeven, gebruik dat subnet
if len(sys.argv) > 1:
    subnet_tekst = sys.argv[1]
else:
    subnet_tekst = standaard_subnet

# maak het netwerk object
netwerk = ipaddress.ip_network(subnet_tekst)

# loop door alle adressen heen en druk ze onder elkaar af
for ip in netwerk:
    # bepaal of dit het netwerk- of broadcastadres is
    markering = ""
    if ip == netwerk.network_address:
        markering = "  <-- netwerkadres"
    elif ip == netwerk.broadcast_address:
        markering = "  <-- broadcastadres"

    # druk het adres netjes af met subnet en masker erbij
    print(f"{str(ip):<15} subnet: {netwerk.with_prefixlen}   (masker {netwerk.netmask}){markering}")
