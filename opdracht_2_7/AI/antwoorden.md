# Opdracht 2.7.5 – Weekopdracht AI

Alle scripts staan in `opdracht_2_7/AI/`, met per onderdeel een eigen map. Getest op Windows 11 met Python 3.14 en PowerShell 7 / 5.1.

---

## 1 – IP-bereik genereren

**Prompt 1:** "Genereer code die een lijst van alle IP-adressen binnen mijn subnet 192.168.1.0/28 genereert."
→ `opdracht_1_ip_bereik/ip_bereik_v1.py`

```
['192.168.1.0', '192.168.1.1', '192.168.1.2', '192.168.1.3', '192.168.1.4', '192.168.1.5', '192.168.1.6', '192.168.1.7', '192.168.1.8', '192.168.1.9', '192.168.1.10', '192.168.1.11', '192.168.1.12', '192.168.1.13', '192.168.1.14', '192.168.1.15']
```

Dit werkt, maar het is een Python-lijst. Die lees je niet makkelijk als je geen programmeur bent.

**Prompt 2:** "Genereer de uitvoer zo dat er een lijst onder elkaar komt met ip adressen. Bij elk ip-adres graag ook het subnet vermelden."
→ `opdracht_1_ip_bereik/ip_bereik_v2.py`

```
192.168.1.0     subnet: 192.168.1.0/28   (masker 255.255.255.240)  <-- netwerkadres
192.168.1.1     subnet: 192.168.1.0/28   (masker 255.255.255.240)
192.168.1.2     subnet: 192.168.1.0/28   (masker 255.255.255.240)
...
192.168.1.14    subnet: 192.168.1.0/28   (masker 255.255.255.240)
192.168.1.15    subnet: 192.168.1.0/28   (masker 255.255.255.240)  <-- broadcastadres
```

**Werkt het? Tevreden?** Ja. Zelf nog aangepast:
- het netwerk- en broadcastadres worden gemarkeerd;
- het subnet is in te stellen als argument, bijvoorbeeld `python ip_bereik_v2.py 10.0.0.0/29`.

---

## 2 – Port scanner

→ `opdracht_2_portscanner/port_scanner.py`

**Prompt:** "Maak een poort scanner die controleert of poort ssh of rdp openstaat op een gegeven IP-adres"
Het script controleert poort 22 (SSH) en 3389 (RDP) met een socket en een timeout van 0,5 s.

Daarna is de regel `# scan all ips in subnet 192.168.1.0/28` toegevoegd. Daaronder staat de code die alle hosts in het subnet scant, parallel met `ThreadPoolExecutor`. Start die scan met `python port_scanner.py --subnet`.

```
=== scan 127.0.0.1 ===
127.0.0.1: poort 22 (SSH) is dicht
127.0.0.1: poort 3389 (RDP) is dicht

=== scan subnet 192.168.1.0/28 ===
192.168.1.1: poort 22 (SSH) is dicht
192.168.1.1: poort 3389 (RDP) is dicht
... (.1 t/m .14, alles dicht)
```

**Werkt het?** Ja. Alle poorten zijn dicht, omdat er op mijn netwerk geen hosts met SSH of RDP in 192.168.1.0/28 zitten. Door de threading staan de regels niet altijd in dezelfde volgorde.

---

## 3 – Tic, tac, toe

Map: `opdracht_2_7/AI/opdracht_3_spelletjes/`

1. **"maak tic, tac toe in python"** → `tic_tac_toe.py`. Twee spelers kiezen om de beurt een vakje (1-9). Het spel herkent winst en gelijkspel, controleert de invoer en kan opnieuw starten.
2. **"in welke directory staat het bestand?"** → `C:\HU opleiding\Jaar 3\Automation\python-hu\opdracht_2_7\AI\opdracht_3_spelletjes\`
3. **Starten vanuit PowerShell:** `python tic_tac_toe.py` werkt. Getest met winst, gelijkspel en foute invoer.
4. **"leuk, maar ik wil liever tegen de computer spelen"** → `tic_tac_toe_vs_computer.py`. Je speelt X en de computer O. Er zijn twee niveaus:
   - Makkelijk: de computer kiest willekeurig.
   - Moeilijk: de computer gebruikt minimax en is onverslaanbaar. Test: 1000 potjes tegen een willekeurige speler gaven 0 keer winst voor de speler.
5. **"nice! nu een nieuw spel, liever iets uit de lucht schieten spelletje of zo"** → `space_shooter.py` (tkinter):
   - Besturing: pijltjes of A/D om te bewegen, spatie om te schieten.
   - Vijanden vallen naar beneden. Elke raak geeft +10 punten.
   - Je hebt 3 levens. Bij game over begin je opnieuw met R.
   - Het spel wordt langzaam sneller.
6. **"wat betekenen die cijfers (+ en - in kleur groen en rood) tijdens het genereren"**
   Dat is een *diff*: de wijzigingen die de AI in het bestand maakt.
   - Groen met `+` = aantal regels dat is **toegevoegd**.
   - Rood met `-` = aantal regels dat is **verwijderd**.
   - `+120 -0` betekent dus een nieuw bestand van 120 regels. `+15 -4` betekent dat er 15 regels bij zijn gekomen en 4 zijn weggehaald of vervangen.
7. **Tegoed:** *zelf aflezen in Codex en hier invullen:* ______

---

## 4 – Loganalyse

Map: `opdracht_2_7/AI/opdracht_4_loganalyse/`. Daarin staat ook `OpenSSH_2k.log`, gedownload van loghub.

### Stap 2 – Unieke gebruikers (`stap2_unieke_users.py`)

```
Unieke geldige gebruikersnamen in OpenSSH_2k.log:
  - ftp
  - fztu
  - git
  - mysql
  - root
  - sshd
  - uucp
Totaal: 7 unieke geldige users
```

### Stap 3 – Ook invalid users (`stap3_valid_invalid.py`)

```
VALID users (bestaande accounts) (7):
  ftp  fztu  git  mysql  root  sshd  uucp

INVALID users (bestaan niet op het systeem) (57):
  0  0101  123  1234  123456  FILTER  Management  PlcmSpIp  abc  admin  anonymous  api
  boot  bssh  butter  chen  cheng  cisco  cyrus  default  deploy  dff  eoor  ftpuser
  ghost  guest  ingrid  inspur  jay  magnos  matlab  monitor  nagios  nagios1  operator
  oracle  oralce  pgadmin  pi  postgres  postgres1  redhat  sandeep  support  ted  test
  test1  test2  test9  ubnt  ubuntu  user  utsims  vnc  webmaster  www  zhangyan
```

**Wat is user "0" op ieder Linux-systeem?**
UID 0 is altijd **root**, de superuser met volledige rechten, wat de gebruikersnaam ook is. Als "0" als loginnaam in een SSH-log staat, probeert een aanvaller waarschijnlijk blind root-toegang te krijgen. Dat past bij het brute-force-patroon in dit log: 276 root-pogingen vanaf één IP en 85 keer "POSSIBLE BREAK-IN ATTEMPT". Root-login via SSH hoort daarom uit te staan (`PermitRootLogin no`).

### Stap 4 – Totalen (`stap4_totalen.py`)

```
=== Unieke gebruikers ===
Unieke valid users   : 7
Unieke invalid users : 57
Totaal unieke users  : 64

=== Aantal logregels per categorie ===
Totaal aantal logregels: 2000
  Accepted password (gelukte login)   : 1
  Failed password (valid user)        : 385
  Failed password (invalid user)      : 135
  Invalid user ... from               : 113
  pam_unix authentication failure     : 494
  Session opened                      : 1
  POSSIBLE BREAK-IN ATTEMPT           : 85

Totaal wachtwoordpogingen (Accepted + Failed regels): 521
```

### Stap 5 – IP met de meeste logins (`stap5_top_ip.py`)

```
=== Top 5 IP-adressen met de meeste inlogpogingen ===
  1. 183.62.140.253    286 pogingen (10 verschillende users)
  2. 187.141.143.180    80 pogingen (28 verschillende users)
  3. 103.99.0.122       46 pogingen (19 verschillende users)
  4. 112.95.230.3       26 pogingen (3 verschillende users)
  5. 5.188.10.180       18 pogingen (7 verschillende users)

IP met de meeste inlogpogingen: 183.62.140.253 (286 pogingen)
  Users vanaf dit IP:
    root             276x
    oracle             2x
    zhangyan           1x
    dff                1x
    test               1x
    ubuntu             1x
    git                1x
    boot               1x
    123456             1x
    123                1x

=== IP-adressen met succesvolle logins ===
  119.137.62.142   1 gelukte login(s)
IP met de meeste succesvolle logins: 119.137.62.142 (1x)
  Users vanaf dit IP:
    fztu               1x
```

Conclusie: 183.62.140.253 doet een brute-force-aanval op root. In het hele log is maar één login gelukt: user `fztu` vanaf 119.137.62.142.

### Stap 6 – Aantal chatberichten Copilot

*Zelf aflezen via het Copilot-icoon rechtsonder in VS Code en hier invullen:* ______

---

## 5 – Pingtool (PowerShell GUI)

→ `opdracht_5_pingtool/ping_tool.ps1`

Starten:

```powershell
powershell -ExecutionPolicy Bypass -File .\ping_tool.ps1
```

Het venster is gemaakt met Windows Forms en heeft:
- een tekstvak voor de hostname (Enter = pingen);
- een keuze voor het aantal pings (standaard 4);
- een Ping-knop;
- een groot uitvoervak.

Per antwoord zie je het adres en de tijd in ms. Daarna volgt een samenvatting: verzonden, ontvangen, percentage verlies en minimum/maximum/gemiddelde tijd. Een onbekende host of time-out geeft een nette foutmelding.

Getest in PowerShell 7 en 5.1 met `localhost`, een niet-bestaande host en een onbereikbaar IP. Zonder venster testen kan met `. .\ping_tool.ps1 -GeenGui`.

---

## 6 – Beheertool (Python)

→ `opdracht_6_beheertool/beheertool.py`. Starten met `python beheertool.py`.

Hoofdmenu:

| Optie | Functie |
|---|---|
| 1 | Ping een host. Gebruikt `-n` op Windows en `-c` op Linux. |
| 2 | Port scanner: kijkt of poort 22 (SSH) open staat op een IP. |
| 3 | IP scanner: zoekt in een heel subnet (bijv. `192.168.1.0/24`) naar hosts die up zijn. Scant parallel en waarschuwt bij meer dan 1024 hosts. |
| 4 | *Zelf bedacht:* DNS lookup. Zoekt de IP's bij een hostname en doet een reverse lookup. |
| 5 | *Zelf bedacht:* systeeminformatie: hostname, OS, Python-versie, lokaal IP, aantal CPU's en vrije schijfruimte. |
| 0 | Afsluiten |

Bij ongeldige invoer (verkeerd IP of subnet, of een onbekende menukeuze) volgt een foutmelding en ga je terug naar het menu.

Testresultaten (zie `testuitvoer.txt`):
1. Ping 127.0.0.1: 4 antwoorden, 0% verlies.
2. Poort 22 op 127.0.0.1: dicht, want er draait lokaal geen SSH-server. `999.1.1.1` geeft een foutmelding.
3. Subnet `127.0.0.0/30`: 127.0.0.1 en 127.0.0.2 zijn up.
4. `google.com` geeft 142.251.39.142 en een IPv6-adres, plus een reverse lookup.
5. Systeeminformatie wordt correct getoond.
