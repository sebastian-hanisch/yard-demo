import math

import yard_constants as C
from yard_scenario import generate_instance

DEFAULTS = dict(
    n_jobs=20, n_vehicles=3, arrival_window=120, peak_pct=50, buffer=20, departure_pct=40,
    yard_length=450, n_doors=10, seed=5,
)


def test_same_seed_gives_identical_instance():
    assert generate_instance(**DEFAULTS) == generate_instance(**DEFAULTS)


def test_different_seed_gives_different_instance():
    other = dict(DEFAULTS, seed=6)
    assert generate_instance(**DEFAULTS).jobs != generate_instance(**other).jobs


def test_all_times_are_true_integers():
    inst = generate_instance(**DEFAULTS)
    for job in inst.jobs:
        assert all(isinstance(v, int) for v in (job.release, job.deadline, job.service, job.weight))
    assert all(isinstance(t, int) for t in inst.approach_from_depot)
    assert all(isinstance(t, int) for row in inst.approach for t in row)


def test_travel_times_are_rounded_up_manhattan_distances():
    inst = generate_instance(**DEFAULTS)
    a, b = inst.jobs[0], inst.jobs[1]
    manhattan = abs(a.drop_xy[0] - b.pick_xy[0]) + abs(a.drop_xy[1] - b.pick_xy[1])
    assert inst.approach[0][1] == math.ceil(manhattan / C.SPEED_M_PER_MIN)


def test_service_includes_coupling_time_and_loaded_trip():
    inst = generate_instance(**DEFAULTS)
    for job in inst.jobs:
        loaded = math.ceil(
            (abs(job.pick_xy[0] - job.drop_xy[0]) + abs(job.pick_xy[1] - job.drop_xy[1])) / C.SPEED_M_PER_MIN
        )
        assert job.service == C.COUPLING_MIN + loaded


def test_every_job_has_positive_slack_and_kind_weight():
    inst = generate_instance(**DEFAULTS)
    for job in inst.jobs:
        assert job.deadline >= job.release + job.service + 1
        assert job.weight == C.KIND_WEIGHTS[job.kind]
        assert 0 <= job.release <= DEFAULTS["arrival_window"]


def test_departure_share_extremes():
    none = generate_instance(**dict(DEFAULTS, departure_pct=0, n_jobs=40))
    assert all(j.kind != C.KIND_DEPARTURE for j in none.jobs)
    many = generate_instance(**dict(DEFAULTS, departure_pct=70, n_jobs=40))
    assert sum(j.kind == C.KIND_DEPARTURE for j in many.jobs) >= 20


def test_job_geometry_matches_kind():
    inst = generate_instance(**dict(DEFAULTS, n_jobs=40))
    door_xy = {(x, y) for x, y, _ in inst.doors}
    for job in inst.jobs:
        if job.kind == C.KIND_SETUP:
            assert job.drop_xy in door_xy and job.pick_xy[1] > 0
        else:
            assert job.pick_xy in door_xy and job.drop_xy[1] > 0


def test_horizon_is_a_safe_upper_bound_for_a_single_vehicle():
    """Selbst ein einziges Fahrzeug, das alle Aufträge nacheinander (schlimmstenfalls mit dem
    größten Anfahrtsweg je Auftrag) bedient, muss innerhalb des Horizonts fertig werden."""
    inst = generate_instance(**dict(DEFAULTS, n_jobs=40, n_vehicles=1))
    worst_end = inst.arrival_window + sum(j.service + max(max(r) for r in inst.approach) for j in inst.jobs)
    assert worst_end <= inst.horizon


def test_utilization_estimate_grows_with_fewer_vehicles():
    few = generate_instance(**dict(DEFAULTS, n_vehicles=1)).mean_utilization_estimate()
    many = generate_instance(**dict(DEFAULTS, n_vehicles=5)).mean_utilization_estimate()
    assert few > many > 0
