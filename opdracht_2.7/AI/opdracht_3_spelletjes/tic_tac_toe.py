"""
Boter-kaas-en-eieren (tic-tac-toe) voor 2 spelers in de terminal.

De vakjes zijn genummerd van 1 t/m 9:

     1 | 2 | 3
    ---+---+---
     4 | 5 | 6
    ---+---+---
     7 | 8 | 9

Starten: python tic_tac_toe.py
"""

# Alle combinaties van vakjes (index 0-8) waarmee je wint
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


def bord_vol(bord):
    """True als er geen lege vakjes meer zijn."""
    return " " not in bord


def vraag_zet(bord, speler):
    """Vraag de speler om een vakje (1-9) en controleer de invoer."""
    while True:
        invoer = input(f"Speler {speler}, kies een vakje (1-9): ").strip()
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


def speel_potje():
    """Speel één potje. Geeft de winnaar ('X'/'O') of None (gelijkspel) terug."""
    bord = [" "] * 9
    speler = "X"

    while True:
        toon_bord(bord)
        index = vraag_zet(bord, speler)
        bord[index] = speler

        winnaar = bepaal_winnaar(bord)
        if winnaar:
            toon_bord(bord)
            print(f"Speler {winnaar} heeft gewonnen!")
            return winnaar
        if bord_vol(bord):
            toon_bord(bord)
            print("Gelijkspel! Het bord is vol.")
            return None

        # Beurt naar de andere speler
        speler = "O" if speler == "X" else "X"


def nog_een_keer():
    """Vraag of de spelers opnieuw willen spelen."""
    while True:
        antwoord = input("Nog een keer spelen? (j/n): ").strip().lower()
        if antwoord in ("j", "ja"):
            return True
        if antwoord in ("n", "nee"):
            return False
        print("Typ 'j' of 'n'.")


def main():
    print("=== Boter-kaas-en-eieren ===")
    scores = {"X": 0, "O": 0, "gelijk": 0}

    try:
        while True:
            uitslag = speel_potje()
            if uitslag:
                scores[uitslag] += 1
            else:
                scores["gelijk"] += 1
            print(f"Stand -> X: {scores['X']}  O: {scores['O']}  gelijk: {scores['gelijk']}")
            if not nog_een_keer():
                break
    except (EOFError, KeyboardInterrupt):
        # Invoer gestopt (bijv. Ctrl+C of einde van gepipete invoer)
        print("\nSpel gestopt.")

    print("Bedankt voor het spelen!")


if __name__ == "__main__":
    main()
