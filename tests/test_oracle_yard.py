"""Unabhängige Orakel (anderer Rechenweg als der Code unter Test):

* Brute Force über ALLE Fahrzeugzuordnungen x Reihenfolgen mit einer eigenen, rekursionsfreien
  Kostenfunktion -> Optimum von CP-SAT und Untergrenze für die Vorausplanung.
* Minuten-Taktsimulation der drei Online-Regeln (statt Ereignisschleife).
* Nachrechnen der Kennzahlen aus dem Plan.
Die große Fassung (260 + 1200 + 600 Instanzen) lief im Scratchpad; hier eine schnelle Stichprobe."""

import itertools
import math
import random

import yard_constants as C
from yard_cp_solver import solve_exact
from yard_evaluation import check_feasible, evaluate
from yard_heuristic import dispatch_atc, dispatch_edd, dispatch_fifo, improve_plan
from yard_scenario import Instance, Job, generate_instance


def _approach(inst, prev, j):
    return inst.approach_from_depot[j] if prev is None else inst.approach[prev][j]


def _cost(inst, seqs):
    weighted = empty = 0
    for seq in seqs:
        t, prev = 0, None
        for j in seq:
            job = inst.jobs[j]
            a = _approach(inst, prev, j)
            end = max(job.release, t + a) + job.service
            weighted += job.weight * max(0, end - job.deadline)
            empty += a
            t, prev = end, j
    return weighted, empty


def _brute_force(inst):
    n, m = len(inst.jobs), inst.n_vehicles
    best = None
    for assign in itertools.product(range(m), repeat=n):
        groups = [[j for j in range(n) if assign[j] == v] for v in range(m)]
        for perms in itertools.product(*[itertools.permutations(g) for g in groups]):
            key = _cost(inst, perms)
            if best is None or key < best:
                best = key
    return best


def _manual_instance(rng, n, m):
    """Gleichstände und Nullwege absichtlich häufig."""
    jobs = []
    for i in range(n):
        kind = rng.choice(C.KINDS)
        rel, sv = rng.choice([0, 0, 3, 8]), rng.choice([1, 5, 5, 10])
        jobs.append(Job(i, f"J{i}", kind, (0, 0), (0, 0), "a", "b", rel, rel + sv + rng.choice([0, 1, 3, 6]), sv,
                        C.KIND_WEIGHTS[kind]))
    approach = tuple(tuple(0 if i == j else rng.choice([0, 1, 2, 2, 5]) for j in range(n)) for i in range(n))
    depot = tuple(rng.choice([0, 2, 3]) for _ in range(n))
    return Instance(tuple(jobs), m, 400, 170, (200, 170), (), 100, depot, approach, 1000)


def _simulate_by_minute(inst, rule):
    jobs, m, n = inst.jobs, inst.n_vehicles, len(inst.jobs)
    free, last, seqs, plan, done = [0] * m, [None] * m, [[] for _ in range(m)], {}, set()
    mean_p = sum(j.service for j in jobs) / n
    t = 0
    while len(done) < n:
        while True:
            idle = [v for v in range(m) if free[v] <= t]
            avail = [j for j in range(n) if j not in done and jobs[j].release <= t]
            if not idle or not avail:
                break
            if rule == "atc":
                best = None
                for j in avail:
                    for v in idle:
                        tau = _approach(inst, last[v], j)
                        slack = jobs[j].deadline - (t + tau + jobs[j].service)
                        idx = jobs[j].weight / (jobs[j].service + tau) * math.exp(-max(0, slack) / mean_p)
                        if best is None or idx > best[0] or (idx == best[0] and (j, v) < best[1:]):
                            best = (idx, j, v)
                _, j, v = best
            else:
                key = (lambda a: (jobs[a].release, a)) if rule == "fifo" else (lambda a: (jobs[a].deadline, a))
                j = min(avail, key=key)
                v = min(idle, key=lambda v: (_approach(inst, last[v], j), v))
            start = t + _approach(inst, last[v], j)
            plan[j] = (v, start)
            free[v], last[v] = start + jobs[j].service, j
            seqs[v].append(j)
            done.add(j)
        t += 1
    return plan, seqs


def test_cpsat_and_foresight_vs_brute_force():
    rng = random.Random(2024)
    for it in range(14):
        n, m = rng.choice([3, 4, 5]), rng.choice([1, 2, 3])
        if it % 2:
            inst = _manual_instance(rng, n, m)
        else:
            inst = generate_instance(n, m, rng.choice([10, 20, 40]), rng.choice([0, 50, 100]), rng.choice([2, 5, 10]),
                                     rng.choice([0, 30, 70]), rng.choice([200, 450]), rng.choice([4, 8]),
                                     rng.randrange(10**6))
        opt = _brute_force(inst)
        res = solve_exact(inst, time_limit_seconds=10)
        assert res.optimal and check_feasible(inst, res.plan)[0]
        ev = evaluate(inst, res.plan)
        assert (ev["total_weighted_tardiness"], ev["empty_minutes"]) == opt
        plan, _ = improve_plan(inst)
        ev2 = evaluate(inst, plan)
        assert (ev2["total_weighted_tardiness"], ev2["empty_minutes"]) >= opt  # nie besser als das Optimum


def test_online_rules_match_minute_by_minute_simulation():
    rng = random.Random(7)
    rules = (("fifo", dispatch_fifo), ("edd", dispatch_edd), ("atc", dispatch_atc))
    for it in range(12):
        n, m = rng.choice([3, 8, 20]), rng.choice([1, 2, 3, 6])
        inst = _manual_instance(rng, n, m) if it % 3 == 0 else generate_instance(
            n, m, rng.choice([20, 60]), rng.choice([0, 100]), rng.choice([2, 10]), rng.choice([0, 70]),
            rng.choice([200, 900]), 8, rng.randrange(10**6))
        for name, rule in rules:
            assert rule(inst) == _simulate_by_minute(inst, name), (it, name)


def test_evaluate_matches_independent_recomputation():
    rng = random.Random(3)
    for it in range(10):
        inst = _manual_instance(rng, rng.choice([4, 6]), rng.choice([1, 2, 3]))
        plan, _ = improve_plan(inst, iterations=3)
        ev = evaluate(inst, plan)
        weighted = empty = late = makespan = busy = 0
        for v in range(inst.n_vehicles):
            prev = None
            for start, j in sorted((s, j) for j, (vv, s) in plan.items() if vv == v):
                job, a = inst.jobs[j], _approach(inst, prev, j)
                tard = max(0, start + job.service - job.deadline)
                weighted += job.weight * tard
                late += tard > 0
                empty += a
                busy += a + job.service
                makespan = max(makespan, start + job.service)
                prev = j
        assert (ev["total_weighted_tardiness"], ev["empty_minutes"], ev["n_late"], ev["makespan"]) == (
            weighted, empty, late, makespan)
        assert abs(ev["utilization"] - busy / (inst.n_vehicles * makespan)) < 1e-12
