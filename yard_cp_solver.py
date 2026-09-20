"""Exakter Referenzlöser (Google OR-Tools CP-SAT) für die Hoffahrzeug-Disposition.

Modell: klassisches Routing mit Zeitbezug. Jeder Auftrag ist ein Knoten, Knoten 0 das Depot, in
dem alle (identischen) Hoffahrzeuge um Minute 0 stehen. `AddMultipleCircuit` erzwingt, dass jeder
Auftrag genau einmal bedient wird; die Zahl der Touren (= genutzte Fahrzeuge) wird über die
Anzahl der Depot-Ausgangsbögen auf `n_vehicles` begrenzt. Da alle Fahrzeuge gleich sind, braucht
das Modell keinen Fahrzeugindex - und damit auch keine Symmetriebrechung.

Zeitvariablen: Start `S_j >= Freigabe_j`. Bogen Depot -> j erzwingt `S_j >= Anfahrt_Depot_j`,
Bogen i -> j erzwingt `S_j >= S_i + Service_i + Anfahrt_ij`. Verspätung `T_j >= S_j + Service_j -
Frist_j`, `T_j >= 0`.

Minimiert wird primär die gewichtete Verspätung, als lexikografisches Tie-Breaking-Ziel
zusätzlich die Leerfahrtzeit (Summe der Anfahrten der gewählten Bögen) - ohne das zweite Ziel
wählt der Solver unter gleich guten Lösungen eine mit unnötigen Umwegen (siehe
[[feedback_cp_sat_lexicographic_tiebreak]]). Wie in der Heuristik ist OBJ_BIG so groß, dass
Leerfahrt nie eine Verspätung aufwiegen kann.

Die Startzeiten, die der Solver frei wählen darf, sind nicht zwingend die frühestmöglichen (er
darf ohne Kosten später starten, wenn nichts verspätet). Daher wird aus den Bögen nur die
REIHENFOLGE je Fahrzeug übernommen und mit `sequences_to_plan` frühestmöglich neu ausgerollt -
das ergibt denselben oder einen besseren Plan und verhindert Leerlauf-Lücken in der Anzeige."""

import os
import time
from dataclasses import dataclass

from ortools.sat.python import cp_model

import yard_constants as C
from yard_evaluation import sequences_to_plan

NUM_SEARCH_WORKERS = min(8, os.cpu_count() or 1)


@dataclass
class ExactResult:
    feasible: bool
    optimal: bool
    plan: dict
    sequences: list
    wall_time_ms: float


def solve_exact(instance, time_limit_seconds=10, hint_sequences=None):
    t0 = time.perf_counter()
    jobs = instance.jobs
    n = len(jobs)
    model = cp_model.CpModel()

    start = [model.NewIntVar(j.release, instance.horizon, f"s_{j.index}") for j in jobs]
    late = [model.NewIntVar(0, instance.horizon, f"t_{j.index}") for j in jobs]
    for j in jobs:
        model.Add(late[j.index] >= start[j.index] + j.service - j.deadline)

    arcs = []
    lit = {}
    empty_terms = []
    # Knoten k = Auftrag k - 1, Knoten 0 = Depot
    for j in jobs:
        a = model.NewBoolVar(f"from_depot_{j.index}")
        lit[(None, j.index)] = a
        arcs.append((0, j.index + 1, a))
        model.Add(start[j.index] >= instance.approach_from_depot[j.index]).OnlyEnforceIf(a)
        empty_terms.append(instance.approach_from_depot[j.index] * a)

        b = model.NewBoolVar(f"to_depot_{j.index}")
        lit[(j.index, None)] = b
        arcs.append((j.index + 1, 0, b))

    for i in jobs:
        for j in jobs:
            if i.index == j.index:
                continue
            a = model.NewBoolVar(f"arc_{i.index}_{j.index}")
            lit[(i.index, j.index)] = a
            arcs.append((i.index + 1, j.index + 1, a))
            model.Add(
                start[j.index] >= start[i.index] + i.service + instance.approach[i.index][j.index]
            ).OnlyEnforceIf(a)
            empty_terms.append(instance.approach[i.index][j.index] * a)

    model.AddMultipleCircuit(arcs)
    model.Add(sum(lit[(None, j.index)] for j in jobs) <= instance.n_vehicles)

    weighted = sum(j.weight * late[j.index] for j in jobs)
    model.Minimize(weighted * C.OBJ_BIG + sum(empty_terms))

    if hint_sequences:
        used = set()
        for seq in hint_sequences:
            prev = None
            for j in seq:
                used.add((prev, j))
                prev = j
            if prev is not None:
                used.add((prev, None))
        for key, var in lit.items():
            model.AddHint(var, 1 if key in used else 0)
        hint_plan = sequences_to_plan(instance, hint_sequences)
        for j in jobs:
            model.AddHint(start[j.index], hint_plan[j.index][1])

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = NUM_SEARCH_WORKERS
    status = solver.Solve(model)
    wall_time_ms = (time.perf_counter() - t0) * 1000

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ExactResult(False, False, {}, [], wall_time_ms)

    successor = {}
    firsts = []
    for (i, j), var in lit.items():
        if solver.Value(var):
            if i is None:
                firsts.append(j)
            elif j is not None:
                successor[i] = j
    sequences = []
    for first in sorted(firsts, key=lambda j: solver.Value(start[j])):
        seq, cur = [], first
        while cur is not None:
            seq.append(cur)
            cur = successor.get(cur)
        sequences.append(seq)
    sequences += [[] for _ in range(instance.n_vehicles - len(sequences))]

    return ExactResult(
        feasible=True, optimal=status == cp_model.OPTIMAL,
        plan=sequences_to_plan(instance, sequences), sequences=sequences, wall_time_ms=wall_time_ms,
    )
