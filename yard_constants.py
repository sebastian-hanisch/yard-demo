"""Defaults, Regler-Grenzen, Farben und Beispielszenarien."""

N_JOBS_DEFAULT = 30
N_JOBS_RANGE = (8, 40)

N_VEHICLES_DEFAULT = 3
N_VEHICLES_RANGE = (1, 6)

ARRIVAL_WINDOW_DEFAULT = 120
ARRIVAL_WINDOW_RANGE = (60, 300)

PEAK_PCT_DEFAULT = 70
PEAK_PCT_RANGE = (0, 100)

BUFFER_DEFAULT = 15
BUFFER_RANGE = (5, 60)

DEPARTURE_PCT_DEFAULT = 45
DEPARTURE_PCT_RANGE = (0, 70)

YARD_LENGTH_DEFAULT = 450
YARD_LENGTH_RANGE = (200, 900)

N_DOORS_DEFAULT = 10
N_DOORS_RANGE = (4, 16)

RANDOM_SEED_DEFAULT = 9
RANDOM_SEED_RANGE = (0, 2_000_000_000)

# --- Feste Modellannahmen (bewusst keine Regler: würden die Demo nur überladen) ---
COUPLING_MIN = 4  # Minuten je Auftrag für An- und Abkuppeln (Stützen, Bremsleitung, Sicherung)
SPEED_M_PER_MIN = 150  # ca. 9 km/h Hofgeschwindigkeit (Rangierbetrieb)
YARD_WIDTH = 170  # Meter (Tiefe des Hofs: Tore bei y=0, Stellplatzreihen dahinter)
PARK_ROW_YS = (55, 80, 105, 130)
PARK_COL_SPACING = 15  # Meter zwischen Stellplätzen einer Reihe

# Prioritätsklassen: (Gewicht, Fristpuffer-Faktor relativ zum Regler "Ø Fristpuffer")
KIND_DEPARTURE = "Abfahrt"
KIND_SETUP = "Bereitstellung"
KIND_CLEAR = "Abräumen"
KINDS = (KIND_DEPARTURE, KIND_SETUP, KIND_CLEAR)
KIND_WEIGHTS = {KIND_DEPARTURE: 4, KIND_SETUP: 2, KIND_CLEAR: 1}
KIND_SLACK_FACTOR = {KIND_DEPARTURE: 0.6, KIND_SETUP: 1.0, KIND_CLEAR: 2.5}
KIND_COLORS = {KIND_DEPARTURE: "#d62728", KIND_SETUP: "#1f77b4", KIND_CLEAR: "#7f7f7f"}
KIND_DESCRIPTIONS = {
    KIND_DEPARTURE: "beladene Brücke vom Tor zum Abfahrtsfeld (Frist = Abfahrt der Linie)",
    KIND_SETUP: "Brücke vom Ankunftsfeld ans Tor zur Entladung (Frist = Beginn des Tor-Slots)",
    KIND_CLEAR: "leere Brücke vom Tor ins Mittelfeld räumen (großzügige Frist)",
}

# Zielfunktion: Gewichtete Verspätung hat strikten Vorrang, Leerfahrtzeit nur als
# lexikografischer Tie-Breaker (siehe yard_cp_solver.py). OBJ_BIG muss größer sein als jede
# mögliche Gesamt-Leerfahrtzeit (max. 40 Aufträge x wenige Minuten je Anfahrt).
OBJ_BIG = 100_000

# Parameter der ATC-Regel (Apparent Tardiness Cost): wie weit voraus "Dringlichkeit" zählt.
# Kleines K = schon bei viel Restpuffer wird ein Auftrag als dringend behandelt.
ATC_K = 1.0

ILS_ITERATIONS = 40

EXACT_SOLVE_TIME_LIMIT_SECONDS = 10

# Seeds sind an Sweeps über je 10 Seeds kalibriert (siehe README) und bewusst so gewählt, dass der
# Verlauf FIFO > Frist zuerst > ATC > Vorausplanung sichtbar wird. Das ist NICHT der Regelfall
# für ATC gegen EDD: bei mäßiger Last gewinnt EDD auf den meisten einzelnen Seeds, ATC senkt nur
# im Mittel (überlastete Seeds) - die App wählt deshalb die beste Online-Regel je Szenario neu.
PRESETS = {
    "Ruhiger Vormittag": dict(
        n_jobs=14, n_vehicles=3, arrival_window=180, peak_pct=20, buffer=30, departure_pct=25,
        yard_length=400, n_doors=8, seed=3,
    ),
    "Abfahrts-Stoßzeit": dict(
        n_jobs=30, n_vehicles=3, arrival_window=120, peak_pct=70, buffer=15, departure_pct=45,
        yard_length=450, n_doors=10, seed=9,
    ),
    "Zu wenig Hoffahrzeuge": dict(
        n_jobs=32, n_vehicles=2, arrival_window=150, peak_pct=50, buffer=20, departure_pct=30,
        yard_length=500, n_doors=8, seed=1,
    ),
    "Weitläufiger Hof": dict(
        n_jobs=30, n_vehicles=4, arrival_window=100, peak_pct=50, buffer=12, departure_pct=35,
        yard_length=850, n_doors=14, seed=10,
    ),
}
