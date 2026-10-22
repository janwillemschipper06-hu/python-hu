"""
Space Shooter: schiet de vijanden uit de lucht!

Besturing:
  Pijltje links / A   -> naar links
  Pijltje rechts / D  -> naar rechts
  Spatie              -> schieten
  R                   -> opnieuw beginnen (na game over)

Elke geraakte vijand = 10 punten. Komt een vijand onderaan
of raakt hij je schip, dan verlies je een leven. Na 3 levens is het game over.

Gemaakt met tkinter (standaardbibliotheek), starten: python space_shooter.py
"""

import random
import tkinter as tk

# Instellingen
BREEDTE = 500
HOOGTE = 600
SCHIP_BREEDTE = 40
SCHIP_HOOGTE = 20
SCHIP_SNELHEID = 20
KOGEL_SNELHEID = 12
VIJAND_GROOTTE = 30
START_LEVENS = 3
FRAME_TIJD = 30  # milliseconden per frame (~33 fps)


class SpaceShooter:
    def __init__(self, root):
        self.root = root
        self.root.title("Space Shooter")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=BREEDTE, height=HOOGTE, bg="black")
        self.canvas.pack()

        # Toetsen koppelen
        self.root.bind("<Left>", lambda e: self.beweeg(-SCHIP_SNELHEID))
        self.root.bind("<Right>", lambda e: self.beweeg(SCHIP_SNELHEID))
        self.root.bind("a", lambda e: self.beweeg(-SCHIP_SNELHEID))
        self.root.bind("d", lambda e: self.beweeg(SCHIP_SNELHEID))
        self.root.bind("<space>", lambda e: self.schiet())
        self.root.bind("r", lambda e: self.herstart())

        self.loop_id = None
        self.nieuw_spel()

    def nieuw_spel(self):
        """Zet alles terug naar de beginsituatie."""
        self.canvas.delete("all")
        self.score = 0
        self.levens = START_LEVENS
        self.game_over = False
        self.kogels = []
        self.vijanden = []
        self.vijand_snelheid = 3
        self.frame_teller = 0

        # Sterren als achtergrond
        for _ in range(50):
            x = random.randint(0, BREEDTE)
            y = random.randint(0, HOOGTE)
            self.canvas.create_oval(x, y, x + 2, y + 2, fill="white", outline="")

        # Ruimteschip (driehoek) onderaan
        midden = BREEDTE // 2
        onder = HOOGTE - 20
        self.schip = self.canvas.create_polygon(
            midden, onder - SCHIP_HOOGTE,
            midden - SCHIP_BREEDTE // 2, onder,
            midden + SCHIP_BREEDTE // 2, onder,
            fill="cyan",
        )

        self.info_tekst = self.canvas.create_text(
            10, 10, anchor="nw", fill="white", font=("Arial", 14), text=""
        )
        self.update_info()

        self.loop_id = self.root.after(FRAME_TIJD, self.spel_loop)

    def herstart(self):
        """R-toets: opnieuw beginnen als het game over is."""
        if self.game_over:
            self.nieuw_spel()

    def update_info(self):
        self.canvas.itemconfig(
            self.info_tekst, text=f"Score: {self.score}    Levens: {self.levens}"
        )

    def beweeg(self, dx):
        """Beweeg het schip naar links of rechts, maar niet buiten het scherm."""
        if self.game_over:
            return
        x1, _, x2, _ = self.canvas.bbox(self.schip)
        if x1 + dx < 0:
            dx = -x1
        if x2 + dx > BREEDTE:
            dx = BREEDTE - x2
        self.canvas.move(self.schip, dx, 0)

    def schiet(self):
        """Maak een nieuwe kogel boven het schip."""
        if self.game_over:
            return
        x1, y1, x2, _ = self.canvas.bbox(self.schip)
        midden = (x1 + x2) // 2
        kogel = self.canvas.create_rectangle(
            midden - 2, y1 - 10, midden + 2, y1, fill="yellow", outline=""
        )
        self.kogels.append(kogel)

    def maak_vijand(self):
        """Maak een vijand op een willekeurige plek bovenaan."""
        x = random.randint(0, BREEDTE - VIJAND_GROOTTE)
        vijand = self.canvas.create_rectangle(
            x, -VIJAND_GROOTTE, x + VIJAND_GROOTTE, 0, fill="red", outline="orange"
        )
        self.vijanden.append(vijand)

    @staticmethod
    def overlapt(a, b):
        """True als twee rechthoeken (x1, y1, x2, y2) elkaar raken."""
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

    def spel_loop(self):
        """Wordt elk frame aangeroepen: alles bewegen en botsingen controleren."""
        if self.game_over:
            return

        self.frame_teller += 1

        # Af en toe een nieuwe vijand, en het spel wordt langzaam sneller
        if self.frame_teller % 40 == 0:
            self.maak_vijand()
        if self.frame_teller % 300 == 0:
            self.vijand_snelheid += 0.5

        # Kogels omhoog bewegen en weghalen als ze uit beeld zijn
        for kogel in self.kogels[:]:
            self.canvas.move(kogel, 0, -KOGEL_SNELHEID)
            if self.canvas.coords(kogel)[3] < 0:
                self.canvas.delete(kogel)
                self.kogels.remove(kogel)

        schip_box = self.canvas.bbox(self.schip)

        # Vijanden omlaag bewegen en botsingen controleren
        for vijand in self.vijanden[:]:
            self.canvas.move(vijand, 0, self.vijand_snelheid)
            vijand_box = self.canvas.coords(vijand)

            # Geraakt door een kogel?
            geraakt = False
            for kogel in self.kogels[:]:
                if self.overlapt(vijand_box, self.canvas.coords(kogel)):
                    self.canvas.delete(kogel)
                    self.kogels.remove(kogel)
                    geraakt = True
                    break
            if geraakt:
                self.canvas.delete(vijand)
                self.vijanden.remove(vijand)
                self.score += 10
                continue

            # Botst tegen het schip of komt onderaan -> leven kwijt
            if self.overlapt(vijand_box, schip_box) or vijand_box[1] > HOOGTE:
                self.canvas.delete(vijand)
                self.vijanden.remove(vijand)
                self.levens -= 1

        self.update_info()

        if self.levens <= 0:
            self.toon_game_over()
        else:
            self.loop_id = self.root.after(FRAME_TIJD, self.spel_loop)

    def toon_game_over(self):
        self.game_over = True
        self.canvas.create_text(
            BREEDTE // 2, HOOGTE // 2 - 30, text="GAME OVER",
            fill="red", font=("Arial", 36, "bold"),
        )
        self.canvas.create_text(
            BREEDTE // 2, HOOGTE // 2 + 20, text=f"Eindscore: {self.score}",
            fill="white", font=("Arial", 18),
        )
        self.canvas.create_text(
            BREEDTE // 2, HOOGTE // 2 + 60, text="Druk op R om opnieuw te spelen",
            fill="white", font=("Arial", 14),
        )


def main():
    root = tk.Tk()
    SpaceShooter(root)
    root.mainloop()


if __name__ == "__main__":
    main()
