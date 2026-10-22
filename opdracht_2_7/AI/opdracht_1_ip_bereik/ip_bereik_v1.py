# opdracht 1 - ip bereik versie 1
# genereert een lijst van alle ip-adressen in subnet 192.168.1.0/28
# inclusief netwerk- en broadcastadres

import ipaddress

# maak het netwerk object van het subnet
netwerk = ipaddress.ip_network("192.168.1.0/28")

# zet alle adressen in een lijst (inclusief netwerk- en broadcastadres)
alle_adressen = [str(ip) for ip in netwerk]

# druk de python-lijst gewoon af
print(alle_adressen)
