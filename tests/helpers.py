"""Gemeinsame Test-Bausteine: kleine, von Hand gebaute Instanzen mit exakt nachrechenbaren Zeiten."""

import yard_constants as C
from yard_scenario import Instance, Job


def make_job(index, kind=C.KIND_SETUP, release=0, service=10, deadline=100, weight=None):
    return Job(
        index=index, name=f"Auftrag {index + 1}", kind=kind, pick_xy=(0, 0), drop_xy=(0, 0),
        pick_label="A", drop_label="B", release=release, deadline=deadline, service=service,
        weight=C.KIND_WEIGHTS[kind] if weight is None else weight,
    )


def make_instance(jobs, n_vehicles=1, approach=None, approach_from_depot=None):
    """Feste Anfahrtszeiten: standardmäßig 2 min zwischen je zwei verschiedenen Aufträgen und
    3 min vom Depot."""
    n = len(jobs)
    if approach is None:
        approach = tuple(tuple(0 if i == j else 2 for j in range(n)) for i in range(n))
    if approach_from_depot is None:
        approach_from_depot = tuple(3 for _ in range(n))
    return Instance(
        jobs=tuple(jobs), n_vehicles=n_vehicles, yard_length=400, yard_width=C.YARD_WIDTH,
        depot_xy=(200, 170), doors=(), arrival_window=100, approach_from_depot=approach_from_depot,
        approach=approach, horizon=1000,
    )
