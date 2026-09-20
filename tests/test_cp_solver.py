import itertools

import yard_constants as C
from tests.helpers import make_instance, make_job
from yard_cp_solver import solve_exact
from yard_evaluation import check_feasible, evaluate, objective_value, sequence_cost
from yard_heuristic import improve_plan
from yard_scenario import generate_instance


def brute_force_optimum(instance):
    """Alle Zuordnungen und Reihenfolgen: jede Permutation aller Aufträge, an m-1 Stellen in
    aufeinanderfolgende Teile für die m Fahrzeuge geschnitten (leere Teile erlaubt)."""
    n, m = len(instance.jobs), instance.n_vehicles
    best = None
    for perm in itertools.permutations(range(n)):
        for cuts in itertools.combinations_with_replacement(range(n + 1), m - 1):
            bounds = (0, *cuts, n)
            seqs = [list(perm[bounds[i]:bounds[i + 1]]) for i in range(m)]
            cost = sum(sequence_cost(instance, s) for s in seqs)
            if best is None or cost < best:
                best = cost
    return best


def test_exact_matches_brute_force_on_tiny_instances():
    for seed in range(1, 7):
        inst = generate_instance(
            n_jobs=5, n_vehicles=2, arrival_window=20, peak_pct=60, buffer=5, departure_pct=50,
            yard_length=450, n_doors=6, seed=seed,
        )
        res = solve_exact(inst, time_limit_seconds=10)
        assert res.feasible and res.optimal
        ok, violations = check_feasible(inst, res.plan)
        assert ok, violations
        assert objective_value(evaluate(inst, res.plan)) == brute_force_optimum(inst), seed


def test_exact_matches_brute_force_with_three_vehicles():
    inst = generate_instance(
        n_jobs=5, n_vehicles=3, arrival_window=15, peak_pct=80, buffer=4, departure_pct=60,
        yard_length=600, n_doors=6, seed=2,
    )
    res = solve_exact(inst, time_limit_seconds=10)
    assert res.optimal
    assert objective_value(evaluate(inst, res.plan)) == brute_force_optimum(inst)


def test_exact_is_never_worse_than_the_foresight_heuristic():
    for seed in range(1, 6):
        inst = generate_instance(
            n_jobs=10, n_vehicles=3, arrival_window=60, peak_pct=60, buffer=12, departure_pct=40,
            yard_length=500, n_doors=8, seed=seed,
        )
        plan, seqs = improve_plan(inst)
        res = solve_exact(inst, time_limit_seconds=10, hint_sequences=seqs)
        assert res.feasible
        assert check_feasible(inst, res.plan)[0]
        if res.optimal:
            assert objective_value(evaluate(inst, res.plan)) <= objective_value(evaluate(inst, plan))


def test_exact_puts_the_heavy_job_first_when_only_one_can_be_on_time():
    heavy = make_job(0, kind=C.KIND_DEPARTURE, release=0, service=10, deadline=13)
    light = make_job(1, kind=C.KIND_CLEAR, release=0, service=10, deadline=13)
    res = solve_exact(make_instance([heavy, light]), time_limit_seconds=5)
    assert res.optimal
    assert res.sequences[0][0] == 0  # der schwere Auftrag fährt zuerst


def test_exact_uses_second_vehicle_when_it_removes_all_tardiness():
    jobs = [make_job(0, release=0, service=10, deadline=13), make_job(1, release=0, service=10, deadline=13)]
    res = solve_exact(make_instance(jobs, n_vehicles=2), time_limit_seconds=5)
    assert res.optimal
    assert evaluate(make_instance(jobs, n_vehicles=2), res.plan)["total_weighted_tardiness"] == 0
    assert sorted(len(s) for s in res.sequences) == [1, 1]


def test_exact_prefers_fewer_empty_minutes_among_equally_punctual_plans():
    """Lexikografisches Tie-Breaking: ohne Verspätung wählt der Solver die Reihenfolge mit der
    kürzeren Gesamt-Leerfahrt (hier: 0 -> 1 kostet 1 min, 1 -> 0 kostet 9 min)."""
    jobs = [make_job(0, deadline=500), make_job(1, deadline=500)]
    approach = ((0, 1), (9, 0))
    inst = make_instance(jobs, approach=approach, approach_from_depot=(3, 3))
    res = solve_exact(inst, time_limit_seconds=5)
    assert res.sequences[0] == [0, 1]
    assert evaluate(inst, res.plan)["empty_minutes"] == 3 + 1


def test_exact_respects_time_limit_and_returns_feasible_plan_on_large_instance():
    inst = generate_instance(
        n_jobs=40, n_vehicles=3, arrival_window=100, peak_pct=70, buffer=10, departure_pct=45,
        yard_length=600, n_doors=10, seed=3,
    )
    plan, seqs = improve_plan(inst)
    res = solve_exact(inst, time_limit_seconds=3, hint_sequences=seqs)
    assert res.feasible
    assert res.wall_time_ms < 15_000
    assert check_feasible(inst, res.plan)[0]
    # mit Hint darf die beste gefundene Lösung nie schlechter sein als die Vorausplanung
    assert objective_value(evaluate(inst, res.plan)) <= objective_value(evaluate(inst, plan))
