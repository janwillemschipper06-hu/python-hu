import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "app.db"

conn = sqlite3.connect(DB_PATH)

conn.execute("DROP TABLE IF EXISTS nummers")
conn.execute("CREATE TABLE nummers (getal INTEGER)")

# randint is inclusive, so 1..499 gives numbers >0 and <500
random_numbers = [(random.randint(1, 499),) for _ in range(1000)]
conn.executemany("INSERT INTO nummers (getal) VALUES (?)", random_numbers)
conn.commit()

sum_numbers = conn.execute("SELECT SUM(getal) FROM nummers").fetchone()[0]
average_number = conn.execute("SELECT AVG(getal) FROM nummers").fetchone()[0]
min_number, max_number = conn.execute("SELECT MIN(getal), MAX(getal) FROM nummers").fetchone()

conn.close()

print("Som:", sum_numbers)
print("Gemiddelde:", average_number)
print("Laagste:", min_number, "Hoogste:", max_number)
