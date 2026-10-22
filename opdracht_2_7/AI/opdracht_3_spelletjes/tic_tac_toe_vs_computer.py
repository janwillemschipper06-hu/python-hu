"""
Boter-kaas-en-eieren: jij (X) tegen de computer (O).

Niveaus:
  1 = makkelijk -> de computer kiest een willekeurig vrij vakje
  2 = moeilijk  -> de computer gebruikt minimax en is onverslaanbaar

Vakjes zijn genummerd van 1 t/m 9 (zoals een telefoon-toetsenbord):

     1 | 2 | 3
    ---+---+---
     4 | 5 | 6
    ---+---+---
     7 | 8 | 9

Starten: python tic_tac_toe_vs_computer.py
"""

import random

SPELER = "X"
COMPUTER = "O"

WIN_LIJNEN = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rijen
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # kolommen
    (0, 4, 8), (2, 4, 6),             # diagonalen
]


def toon_bord(bord):
    """Print het bord. Lege vakjes tonen hun nummer."""
    print()
    for rij in range(3):
        vakjes = []
        for kolom in range(3):
            index = rij * 3 + kolom
            vakjes.append(bord[index] if bord[index] != " " else str(index + 1))
        print("  " + " | ".join(vakjes))
        if rij < 2:
            print(" ---+---+---")
    print()


def bepaal_winnaar(bord):
    """Geeft 'X' of 'O' terug als iemand gewonnen heeft, anders None."""
    for a, b, c in WIN_LIJNEN:
        if bord[a] != " " and bord[a] == bord[b] == bord[c]:
            return bord[a]
    return None


def vrije_vakjes(bord):
    """Lijst met de indexen van alle lege vakjes."""
    return [i for i in range(9) if bord[i] == " "]


def minimax(bord, computer_aan_zet):
    """
    Minimax-algoritme: probeert alle mogelijke zetten tot het einde van het spel.
    Score: +10 = computer wint, -10 = speler wint, 0 = gelijkspel.
    De diepte wordt van de score afgetrokken zodat de computer
    het liefst snel wint (en zo laat mogelijk verliest).
    """
    winnaar = bepaal_winnaar(bord)
    diepte = 9 - len(vrije_vakjes(bord))
    if winnaar == COMPUTER:
        return 10 - diepte
    if winnaar == SPELER:
        return diepte - 10
    if not vrije_vakjes(bord):
        return 0

    if computer_aan_zet:
        beste = -100
        for i in vrije_vakjes(bord):
            bord[i] = COMPUTER
            beste = max(beste, minimax(bord, False))
            bord[i] = " "  # zet terugdraaien
        return beste
    else:
        beste = 100
        for i in vrije_vakjes(bord):
            bord[i] = SPELER
            beste = min(beste, minimax(bord, True))
            bord[i] = " "
        return beste


def computer_zet(bord, niveau):
    """Kies een zet voor de computer, afhankelijk van het niveau."""
    if niveau == "makkelijk":
        return random.choice(vrije_vakjes(bord))

    # Moeilijk: kies de zet met de hoogste minimax-score
    beste_score = -100
    beste_zet = None
    for i in vrije_vakjes(bord):
        bord[i] = COMPUTER
        score = minimax(bord, False)
        bord[i] = " "
        if score > beste_score:
            beste_score = score
            beste_zet = i
    return beste_zet


def vraag_zet(bord):
    """Vraag de speler om een vakje (1-9) en controleer de invoer."""
    while True:
        invoer = input(f"Jouw beurt ({SPELER}), kies een vakje (1-9): ").strip()
        if not invoer.isdigit():
            print("Ongeldige invoer: typ een getal van 1 t/m 9.")
            continue
        nummer = int(invoer)
        if nummer < 1 or nummer > 9:
            print("Dat vakje bestaat niet: kies 1 t/m 9.")
            continue
        if bord[nummer - 1] != " ":
            print("Dat vakje is al bezet, kies een ander vakje.")
            continue
        return nummer - 1


def kies_niveau():
    """Laat de speler kiezen tussen makkelijk en moeilijk."""
    while True:
        keuze = input("Kies niveau: 1 = makkelijk, 2 = moeilijk (onverslaanbaar): ").strip()
        if keuze == "1":
            return "makkelijk"
        if keuze == "2":
            return "moeilijk"
        print("Typ 1 of 2.")


def speel_potje(niveau):
    """Speel één potje. Geeft 'X', 'O' of None (gelijkspel) terug."""
    bord = [" "] * 9
    aan_de_beurt = SPELER  # de speler begint altijd

    while True:
        if aan_de_beurt == SPELER:
            toon_bord(bord)
            index = vraag_zet(bord)
        else:
            index = computer_zet(bord, niveau)
            print(f"De computer kiest vakje {index + 1}.")
        bord[index] = aan_de_beurt

        winnaar = bepaal_winnaar(bord)
        if winnaar:
            toon_bord(bord)
            if winnaar == SPELER:
                print("Gefeliciteerd, je hebt gewonnen!")
            else:
                print("De computer heeft gewonnen!")
            return winnaar
        if not vrije_vakjes(bord):
            toon_bord(bord)
            print("Gelijkspel! Het bord is vol.")
            return None

        aan_de_beurt = COMPUTER if aan_de_beurt == SPELER else SPELER


def nog_een_keer():
    """Vraag of de speler opnieuw wil spelen."""
    while True:
        antwoord = input("Nog een keer spelen? (j/n): ").strip().lower()
        if antwoord in ("j", "ja"):
            return True
        if antwoord in ("n", "nee"):
            return False
        print("Typ 'j' of 'n'.")


def main():
    print("=== Boter-kaas-en-eieren tegen de computer ===")
    scores = {SPELER: 0, COMPUTER: 0, "gelijk": 0}

    try:
        while True:
            niveau = kies_niveau()
            uitslag = speel_potje(niveau)
            if uitslag:
                scores[uitslag] += 1
            else:
                scores["gelijk"] += 1
            print(f"Stand -> jij: {scores[SPELER]}  computer: {scores[COMPUTER]}  "
                  f"gelijk: {scores['gelijk']}")
            if not nog_een_keer():
                break
    except (EOFError, KeyboardInterrupt):
        print("\nSpel gestopt.")

    print("Bedankt voor het spelen!")


if __name__ == "__main__":
    main()
