"""Machbarkeitsprüfung und Kennzahlen - unabhängig davon, ob der Einsatzplan von einer Regel, der
lokalen Suche oder dem CP-SAT-Löser stammt (`yard_heuristic.py` / `yard_cp_solver.py` nutzen
BEIDE ausschließlich diese Funktionen zur Prüfung, damit Konstruktion und Prüfung nie
auseinanderlaufen können).

Ein Einsatzplan ist ein dict `job_index -> (vehicle, start)`: `start` ist der Zeitpunkt (Minuten),
zu dem das Hoffahrzeug am Abholort steht und ankuppelt. Die Anfahrt davor (Leerfahrt) dauert
`instance.approach_time(...)` Minuten, danach folgen `job.service` Minuten bis zum Abstellen."""

from collections import defaultdict

import yard_constants as C


def sequences_to_plan(instance, sequences):
    """Frühestmögliche Zeiten für feste Reihenfolgen je Fahrzeug (`sequences[v]` = Liste von
    Auftragsindizes): das Fahrzeug fährt IMMER sofort los und wartet ggf. am Abholort auf die
    Freigabe - es darf also vorpositionieren, wenn es den Auftrag schon kennt (Vorwissen).
    Gilt nur für Vorausplanung; die Online-Regeln liefern ihre tatsächlichen Startzeiten selbst."""
    plan = {}
    for v, seq in enumerate(sequences):
        t, prev = 0, None
        for j in seq:
            job = instance.jobs[j]
            start = max(job.release, t + instance.approach_time(prev, j))
            plan[j] = (v, start)
            t, prev = start + job.service, j
    return plan


def sequence_cost(instance, seq):
    """Zielfunktionsbeitrag EINES Fahrzeugs (frühestmögliche Zeiten): gewichtete Verspätung *
    OBJ_BIG + Leerfahrtminuten. Ganzzahlig, damit die lokale Suche exakt vergleichen kann."""
    t, prev = 0, None
    weighted, empty = 0, 0
    for j in seq:
        job = instance.jobs[j]
        approach = instance.approach_time(prev, j)
        start = max(job.release, t + approach)
        end = start + job.service
        if end > job.deadline:
            weighted += job.weight * (end - job.deadline)
        empty += approach
        t, prev = end, j
    return weighted * C.OBJ_BIG + empty


def check_feasible(instance, plan):
    violations = []
    jobs = instance.jobs

    if set(plan.keys()) != {j.index for j in jobs}:
        violations.append("Nicht jeder Auftrag genau einmal eingeplant.")
        return False, violations

    by_vehicle = defaultdict(list)
    for idx, (vehicle, start) in plan.items():
        if not 0 <= vehicle < instance.n_vehicles:
            violations.append(f"{jobs[idx].name}: unbekanntes Fahrzeug {vehicle}.")
            continue
        if start < jobs[idx].release:
            violations.append(f"{jobs[idx].name}: Start {start} min liegt vor der Freigabe {jobs[idx].release} min.")
        by_vehicle[vehicle].append((start, idx))

    for vehicle, entries in by_vehicle.items():
        entries.sort()
        free_at, prev = 0, None
        for start, idx in entries:
            approach = instance.approach_time(prev, idx)
            if start < free_at + approach:
                violations.append(
                    f"Fahrzeug {vehicle + 1}: {jobs[idx].name} beginnt bei {start} min, das Fahrzeug kann "
                    f"frühestens bei {free_at + approach} min (frei ab {free_at} min + {approach} min Anfahrt) dort sein."
                )
            free_at, prev = start + jobs[idx].service, idx
    return len(violations) == 0, violations


def evaluate(instance, plan, label=""):
    per_job = {}
    by_kind = defaultdict(list)
    by_vehicle = defaultdict(list)
    for idx, (vehicle, start) in plan.items():
        by_vehicle[vehicle].append((start, idx))

    weighted_tardiness = 0
    total_tardiness = 0
    n_late = 0
    empty_minutes = 0
    busy_minutes = 0
    makespan = 0
    total_wait = 0
    vehicle_sequences = [[] for _ in range(instance.n_vehicles)]

    for vehicle, entries in by_vehicle.items():
        entries.sort()
        prev = None
        for start, idx in entries:
            job = instance.jobs[idx]
            approach = instance.approach_time(prev, idx)
            end = start + job.service
            tardiness = max(0, end - job.deadline)
            wait = start - job.release
            per_job[idx] = {
                "vehicle": vehicle, "start": start, "end": end, "approach": approach,
                "tardiness": tardiness, "wait": wait,
            }
            by_kind[job.kind].append(tardiness)
            weighted_tardiness += job.weight * tardiness
            total_tardiness += tardiness
            n_late += tardiness > 0
            empty_minutes += approach
            busy_minutes += approach + job.service
            total_wait += wait
            makespan = max(makespan, end)
            vehicle_sequences[vehicle].append(idx)
            prev = idx

    n_veh = max(1, instance.n_vehicles)
    return {
        "label": label,
        "plan": per_job,
        "sequences": vehicle_sequences,
        "total_weighted_tardiness": weighted_tardiness,
        "total_tardiness": total_tardiness,
        "n_late": n_late,
        "n_jobs": len(plan),
        "empty_minutes": empty_minutes,
        "busy_minutes": busy_minutes,
        "utilization": busy_minutes / (n_veh * makespan) if makespan > 0 else 0.0,
        "makespan": makespan,
        "total_wait": total_wait,
        "avg_tardiness_by_kind": {k: (sum(v) / len(v) if v else 0.0) for k, v in by_kind.items()},
        "n_late_by_kind": {k: sum(1 for x in v if x > 0) for k, v in by_kind.items()},
    }


def objective_value(result):
    """Skalare Zielgröße derselben Form wie in `sequence_cost` und im CP-SAT-Modell."""
    return result["total_weighted_tardiness"] * C.OBJ_BIG + result["empty_minutes"]


def comparison_table(results):
    import pandas as pd

    rows = []
    for r in results:
        row = {
            "Methode": r["label"],
            "Gewichtete Verspätung (Score)": r["total_weighted_tardiness"],
            "Verspätete Aufträge": f"{r['n_late']} von {r['n_jobs']}",
            "Verspätung gesamt (min)": r["total_tardiness"],
            "Leerfahrten (min)": r["empty_minutes"],
            "Fertig um (min)": r["makespan"],
        }
        for kind in C.KINDS:
            row[f"Ø Verspätung {kind} (min)"] = round(r["avg_tardiness_by_kind"].get(kind, 0.0), 1)
        rows.append(row)
    return pd.DataFrame(rows)
