import yard_constants as C
from tests.helpers import make_instance, make_job
from yard_evaluation import check_feasible, evaluate, objective_value, sequence_cost, sequences_to_plan


def test_sequences_to_plan_uses_earliest_times_including_prepositioning():
    # Auftrag 0 wird erst bei 50 frei; das Fahrzeug steht ab 3 min am Abholort bereit und wartet.
    jobs = [make_job(0, release=50, service=10, deadline=200), make_job(1, release=0, service=10, deadline=200)]
    inst = make_instance(jobs)
    plan = sequences_to_plan(inst, [[0, 1]])
    assert plan[0] == (0, 50)
    assert plan[1] == (0, 50 + 10 + 2)  # Ende von Auftrag 0 + 2 min Anfahrt


def test_evaluate_computes_tardiness_and_weighted_score():
    jobs = [
        make_job(0, kind=C.KIND_DEPARTURE, release=0, service=10, deadline=10),  # Gewicht 4
        make_job(1, kind=C.KIND_CLEAR, release=0, service=10, deadline=15),  # Gewicht 1
    ]
    inst = make_instance(jobs)
    result = evaluate(inst, sequences_to_plan(inst, [[0, 1]]))
    # Auftrag 0: Start 3 (Anfahrt vom Depot), Ende 13, 3 min verspätet -> 4 * 3
    # Auftrag 1: Start 13 + 2 = 15, Ende 25, 10 min verspätet -> 1 * 10
    assert result["plan"][0]["tardiness"] == 3
    assert result["plan"][1]["tardiness"] == 10
    assert result["total_weighted_tardiness"] == 4 * 3 + 1 * 10
    assert result["n_late"] == 2
    assert result["empty_minutes"] == 3 + 2
    assert result["makespan"] == 25


def test_on_time_job_has_zero_tardiness_not_negative():
    inst = make_instance([make_job(0, service=10, deadline=500)])
    result = evaluate(inst, sequences_to_plan(inst, [[0]]))
    assert result["total_weighted_tardiness"] == 0 and result["n_late"] == 0


def test_check_feasible_accepts_earliest_plan():
    jobs = [make_job(i, release=i * 5) for i in range(4)]
    inst = make_instance(jobs, n_vehicles=2)
    ok, violations = check_feasible(inst, sequences_to_plan(inst, [[0, 2], [1, 3]]))
    assert ok, violations


def test_check_feasible_rejects_start_before_release():
    inst = make_instance([make_job(0, release=20)])
    ok, violations = check_feasible(inst, {0: (0, 10)})
    assert not ok and any("Freigabe" in v for v in violations)


def test_check_feasible_rejects_overlap_on_same_vehicle():
    inst = make_instance([make_job(0, service=10), make_job(1, service=10)])
    ok, violations = check_feasible(inst, {0: (0, 3), 1: (0, 8)})  # Auftrag 2 startet vor Ende + Anfahrt
    assert not ok and any("Fahrzeug 1" in v for v in violations)


def test_check_feasible_rejects_start_before_depot_travel():
    inst = make_instance([make_job(0)])
    ok, _ = check_feasible(inst, {0: (0, 2)})  # Anfahrt vom Depot dauert 3 min
    assert not ok


def test_check_feasible_rejects_missing_or_unknown_vehicle():
    inst = make_instance([make_job(0), make_job(1)])
    assert not check_feasible(inst, {0: (0, 3)})[0]
    assert not check_feasible(inst, {0: (5, 3), 1: (0, 20)})[0]


def test_sequence_cost_matches_objective_of_evaluated_plan():
    jobs = [make_job(i, kind=C.KINDS[i % 3], release=i * 3, service=8, deadline=20 + i * 4) for i in range(6)]
    inst = make_instance(jobs, n_vehicles=2)
    seqs = [[0, 2, 4], [1, 3, 5]]
    total = sum(sequence_cost(inst, s) for s in seqs)
    assert total == objective_value(evaluate(inst, sequences_to_plan(inst, seqs)))


def test_utilization_is_busy_share_of_fleet_time():
    inst = make_instance([make_job(0, service=10, deadline=500)], n_vehicles=2)
    result = evaluate(inst, sequences_to_plan(inst, [[0], []]))
    assert result["busy_minutes"] == 3 + 10
    assert abs(result["utilization"] - 13 / (2 * 13)) < 1e-9
