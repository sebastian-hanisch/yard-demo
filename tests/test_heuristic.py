import time

import pytest

import yard_constants as C
from tests.helpers import make_instance, make_job
from yard_evaluation import check_feasible, evaluate, objective_value, sequence_cost
from yard_heuristic import (
    dispatch_atc,
    dispatch_edd,
    dispatch_fifo,
    improve_plan,
    iterated_local_search,
    local_search,
)
from yard_scenario import generate_instance

RULES = [dispatch_fifo, dispatch_edd, dispatch_atc]
CONFIGS = [
    dict(n_jobs=12, n_vehicles=2, arrival_window=60, peak_pct=70, buffer=10, departure_pct=45, yard_length=450, n_doors=8),
    dict(n_jobs=30, n_vehicles=3, arrival_window=120, peak_pct=70, buffer=15, departure_pct=45, yard_length=450, n_doors=10),
    dict(n_jobs=20, n_vehicles=6, arrival_window=90, peak_pct=0, buffer=30, departure_pct=10, yard_length=800, n_doors=14),
    dict(n_jobs=25, n_vehicles=1, arrival_window=200, peak_pct=100, buffer=5, departure_pct=70, yard_length=300, n_doors=4),
]


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("cfg", CONFIGS)
def test_every_online_rule_produces_a_feasible_plan(rule, cfg):
    for seed in (1, 2, 3):
        inst = generate_instance(seed=seed, **cfg)
        plan, sequences = rule(inst)
        ok, violations = check_feasible(inst, plan)
        assert ok, violations
        assert sorted(j for seq in sequences for j in seq) == list(range(cfg["n_jobs"]))


@pytest.mark.parametrize("rule", RULES)
def test_online_rules_never_use_information_from_the_future(rule):
    """Ein Online-Plan darf ein Fahrzeug erst losschicken, wenn der Auftrag freigegeben ist: Beginn
    frühestens Freigabe + Anfahrt. (Die Vorausplanung darf davon abweichen - das ist gerade das
    Vorpositionieren.)"""
    inst = generate_instance(seed=4, **CONFIGS[1])
    plan, sequences = rule(inst)
    result = evaluate(inst, plan)
    for idx, info in result["plan"].items():
        assert info["start"] >= inst.jobs[idx].release + info["approach"]


def test_fifo_serves_the_oldest_released_job_first():
    jobs = [make_job(0, release=5), make_job(1, release=1), make_job(2, release=3)]
    _, sequences = dispatch_fifo(make_instance(jobs))
    assert sequences[0] == [1, 2, 0]


def test_edd_serves_the_earliest_deadline_first_among_released_jobs():
    jobs = [make_job(0, deadline=90), make_job(1, deadline=30), make_job(2, deadline=60)]
    _, sequences = dispatch_edd(make_instance(jobs))
    assert sequences[0] == [1, 2, 0]


def test_atc_takes_the_heavy_job_when_deadlines_are_comparable():
    heavy = make_job(0, kind=C.KIND_DEPARTURE, deadline=40)
    light = make_job(1, kind=C.KIND_CLEAR, deadline=40)
    _, sequences = dispatch_atc(make_instance([heavy, light]))
    assert sequences[0][0] == 0


def test_atc_lets_a_loose_deadline_wait_for_an_urgent_one():
    """Job 0 hat sehr viel Puffer, Job 1 ist dringend und gleich schwer: ATC muss 1 vorziehen -
    FIFO (Auftrag 0 kommt zuerst in der Liste, gleiche Freigabe) täte es nicht."""
    loose = make_job(0, kind=C.KIND_SETUP, service=10, deadline=500)
    urgent = make_job(1, kind=C.KIND_SETUP, service=10, deadline=16)
    _, seq_atc = dispatch_atc(make_instance([loose, urgent]))
    assert seq_atc[0][0] == 1


def test_online_rule_waits_for_release_and_does_not_start_early():
    jobs = [make_job(0, release=40, deadline=500)]
    plan, _ = dispatch_fifo(make_instance(jobs))
    assert plan[0] == (0, 40 + 3)  # Fahrzeug fährt erst bei Freigabe los: + 3 min Anfahrt vom Depot


def test_more_vehicles_than_jobs_is_fine():
    inst = generate_instance(seed=1, **dict(CONFIGS[0], n_jobs=8, n_vehicles=6))
    for rule in RULES:
        ok, violations = check_feasible(inst, rule(inst)[0])
        assert ok, violations
    plan, seqs = improve_plan(inst)
    assert check_feasible(inst, plan)[0]


@pytest.mark.parametrize("cfg", CONFIGS)
def test_local_search_never_worsens_and_stays_feasible(cfg):
    for seed in (1, 2, 3):
        inst = generate_instance(seed=seed, **cfg)
        start = dispatch_atc(inst)[1]
        polished = local_search(inst, start)
        assert sum(sequence_cost(inst, s) for s in polished) <= sum(sequence_cost(inst, s) for s in start)
        assert sorted(j for s in polished for j in s) == list(range(cfg["n_jobs"]))


def test_ils_never_worsens_the_local_search_result():
    inst = generate_instance(seed=7, **CONFIGS[1])
    polished = local_search(inst, dispatch_atc(inst)[1])
    ils = iterated_local_search(inst, polished, iterations=15)
    assert sum(sequence_cost(inst, s) for s in ils) <= sum(sequence_cost(inst, s) for s in polished)


def test_ils_is_deterministic():
    inst = generate_instance(seed=7, **CONFIGS[1])
    start = local_search(inst, dispatch_atc(inst)[1])
    assert iterated_local_search(inst, start, iterations=10) == iterated_local_search(inst, start, iterations=10)


@pytest.mark.parametrize("cfg", CONFIGS)
def test_foresight_is_never_worse_than_any_online_rule(cfg):
    """Die Vorausplanung startet bei den Online-Reihenfolgen, darf aber vorpositionieren (frühere
    Startzeiten, gleiche Leerfahrten) und verbessert nur - sie kann also nie schlechter sein."""
    for seed in (1, 2, 3, 4):
        inst = generate_instance(seed=seed, **cfg)
        offline_plan = improve_plan(inst)[0]
        assert check_feasible(inst, offline_plan)[0]
        offline = evaluate(inst, offline_plan)
        for rule in RULES:
            online = evaluate(inst, rule(inst)[0])
            assert objective_value(offline) <= objective_value(online)


def test_foresight_measurably_beats_online_rules_on_a_rush_scenario():
    """Regressionstest gegen die dokumentierte Kernaussage (README): auf dem Preset
    'Abfahrts-Stoßzeit' (Seed 9) ist die beste Online-Regel deutlich schlechter als die
    Vorausplanung."""
    p = dict(C.PRESETS["Abfahrts-Stoßzeit"])
    inst = generate_instance(**p)
    best_online = min(objective_value(evaluate(inst, rule(inst)[0])) for rule in RULES)
    offline = objective_value(evaluate(inst, improve_plan(inst)[0]))
    assert best_online > 0
    assert offline < best_online * 0.6


def test_fifo_is_clearly_worst_on_a_contended_preset():
    inst = generate_instance(**C.PRESETS["Zu wenig Hoffahrzeuge"])
    scores = {rule.__name__: evaluate(inst, rule(inst)[0])["total_weighted_tardiness"] for rule in RULES}
    assert scores["dispatch_fifo"] > 2 * scores["dispatch_edd"]
    assert scores["dispatch_fifo"] > 2 * scores["dispatch_atc"]


def test_quiet_preset_has_no_tardiness_for_any_method():
    inst = generate_instance(**C.PRESETS["Ruhiger Vormittag"])
    for rule in RULES:
        assert evaluate(inst, rule(inst)[0])["total_weighted_tardiness"] == 0


def test_improve_plan_worst_case_completes_within_budget():
    """Größte mögliche Instanz (40 Aufträge) mit nur einem Fahrzeug = längste Reihenfolge: die
    Vorausplanung wird bei jedem Reglerzug neu berechnet und darf nicht zum Warten zwingen.
    Gemessen ca. 2,6 s."""
    inst = generate_instance(seed=5, n_jobs=40, n_vehicles=1, arrival_window=60, peak_pct=100, buffer=5,
                             departure_pct=70, yard_length=900, n_doors=16)
    t0 = time.perf_counter()
    improve_plan(inst)
    assert time.perf_counter() - t0 < 12
