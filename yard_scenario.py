"""Instanzerzeugung: Fahraufträge für Wechselbrücken auf einem Betriebshof.

Ein Betriebshof hat Tore an der Hallenwand (y = 0) und dahinter drei Stellplatzfelder
(Ankunft / Mittelfeld / Abfahrt) in vier Reihen. Jeder Auftrag verschiebt EINE Wechselbrücke von
einem Ort zu einem anderen - Aufträge kommen im Laufe des Schichtfensters herein (Freigabezeit)
und haben eine Frist (z. B. Beginn des Tor-Slots oder Abfahrt der Linie).

Bewusste Design-Entscheidung (aus quaycrane-demo/berth-allocation-demo gelernt): ALLE Zeiten
sind echte Ganzzahlen in Minuten. Fahrzeiten werden schon hier AUFGERUNDET (`math.ceil`, nie
`round`) und als fertige Matrix mitgegeben - Heuristik, Prüfung und CP-SAT-Modell lesen dieselben
Zahlen, also kann zwischen den drei Wegen keine Rundungsdifferenz entstehen."""

import math
import random
from dataclasses import dataclass

import yard_constants as C


@dataclass(frozen=True)
class Job:
    index: int
    name: str
    kind: str  # C.KIND_DEPARTURE | C.KIND_SETUP | C.KIND_CLEAR
    pick_xy: tuple  # Meter
    drop_xy: tuple
    pick_label: str
    drop_label: str
    release: int  # Minuten; frühestens ab dann kann die Brücke aufgenommen werden
    deadline: int  # Minuten; Frist für "Brücke abgestellt" (Ende des Auftrags)
    service: int  # Minuten: An-/Abkuppeln + beladene Fahrt (ohne Anfahrt zur Brücke)
    weight: int  # Gewicht der Verspätung


@dataclass(frozen=True)
class Instance:
    jobs: tuple
    n_vehicles: int
    yard_length: int
    yard_width: int
    depot_xy: tuple
    doors: tuple  # ((x, y, label), ...)
    arrival_window: int
    approach_from_depot: tuple  # Minuten: Depot -> Abholort von Auftrag j
    approach: tuple  # approach[i][j]: leer von Abstellort von Auftrag i zum Abholort von Auftrag j
    horizon: int  # sichere obere Schranke (Minuten) für Planung und CP-SAT

    def approach_time(self, prev, job):
        """Leerfahrt zum Abholort von `job`; `prev` = Index des zuletzt bedienten Auftrags oder
        None (Fahrzeug steht noch am Depot)."""
        return self.approach_from_depot[job] if prev is None else self.approach[prev][job]

    def mean_utilization_estimate(self):
        """Grober Belastungsgrad: (Summe Servicezeit + n * mittlere Leerfahrt) / (Fahrzeuge *
        Ankunftsfenster). Nur eine Faustgröße - Wellen und Fristen kann sie nicht abbilden."""
        n = len(self.jobs)
        if n == 0:
            return 0.0
        pairs = [self.approach[i][j] for i in range(n) for j in range(n) if i != j]
        mean_approach = sum(pairs) / len(pairs) if pairs else 0.0
        work = sum(j.service for j in self.jobs) + n * mean_approach
        return work / (self.n_vehicles * max(1, self.arrival_window))


def _travel_minutes(a, b):
    """Hofwege verlaufen rechtwinklig (Manhattan); aufgerundet auf ganze Minuten."""
    return math.ceil((abs(a[0] - b[0]) + abs(a[1] - b[1])) / C.SPEED_M_PER_MIN)


def generate_instance(n_jobs, n_vehicles, arrival_window, peak_pct, buffer, departure_pct,
                      yard_length, n_doors, seed):
    rng = random.Random(seed)

    door_xs = [round(yard_length * (0.08 + 0.84 * i / max(1, n_doors - 1))) for i in range(n_doors)]
    doors = tuple((x, 0, f"Tor {i + 1}") for i, x in enumerate(door_xs))

    n_cols = max(3, yard_length // C.PARK_COL_SPACING)
    zone_cols = {
        "Ankunft": range(0, int(n_cols * 0.3)),
        "Mittelfeld": range(int(n_cols * 0.3), int(n_cols * 0.7)),
        "Abfahrt": range(int(n_cols * 0.7), n_cols),
    }

    def random_slot(zone):
        col = rng.choice(list(zone_cols[zone]))
        row = rng.randrange(len(C.PARK_ROW_YS))
        return (col * C.PARK_COL_SPACING + C.PARK_COL_SPACING // 2, C.PARK_ROW_YS[row]), f"{zone} {row + 1}-{col + 1:02d}"

    depot_xy = (yard_length // 2, C.YARD_WIDTH)

    def draw_release():
        if rng.random() < peak_pct / 100:
            value = rng.gauss(arrival_window / 2, arrival_window / 8)
        else:
            value = rng.uniform(0, arrival_window)
        return int(min(arrival_window, max(0, round(value))))

    p_departure = departure_pct / 100
    p_setup = (1 - p_departure) * 0.6

    jobs = []
    for i in range(n_jobs):
        draw = rng.random()
        if draw < p_departure:
            kind = C.KIND_DEPARTURE
        elif draw < p_departure + p_setup:
            kind = C.KIND_SETUP
        else:
            kind = C.KIND_CLEAR

        door_x, door_y, door_label = rng.choice(doors)
        if kind == C.KIND_SETUP:
            pick_xy, pick_label = random_slot("Ankunft")
            drop_xy, drop_label = (door_x, door_y), door_label
        elif kind == C.KIND_DEPARTURE:
            pick_xy, pick_label = (door_x, door_y), door_label
            drop_xy, drop_label = random_slot("Abfahrt")
        else:
            pick_xy, pick_label = (door_x, door_y), door_label
            drop_xy, drop_label = random_slot("Mittelfeld")

        release = draw_release()
        service = C.COUPLING_MIN + _travel_minutes(pick_xy, drop_xy)
        slack = max(1, round(buffer * C.KIND_SLACK_FACTOR[kind] * rng.uniform(0.5, 1.5)))
        jobs.append(
            Job(
                index=i, name=f"Auftrag {i + 1}", kind=kind, pick_xy=pick_xy, drop_xy=drop_xy,
                pick_label=pick_label, drop_label=drop_label, release=release,
                deadline=release + service + slack, service=service, weight=C.KIND_WEIGHTS[kind],
            )
        )

    approach_from_depot = tuple(_travel_minutes(depot_xy, j.pick_xy) for j in jobs)
    approach = tuple(tuple(_travel_minutes(a.drop_xy, b.pick_xy) for b in jobs) for a in jobs)

    max_approach = max([*approach_from_depot, *(t for row in approach for t in row)], default=0)
    horizon = arrival_window + sum(j.service + max_approach for j in jobs) + 10

    return Instance(
        jobs=tuple(jobs), n_vehicles=n_vehicles, yard_length=yard_length, yard_width=C.YARD_WIDTH,
        depot_xy=depot_xy, doors=doors, arrival_window=arrival_window,
        approach_from_depot=approach_from_depot, approach=approach, horizon=horizon,
    )
