"""Selbst implementierte Verfahren für die Hoffahrzeug-Disposition (Yard Management).

Zwei Klassen, bewusst getrennt, weil sie unterschiedlich viel WISSEN haben:

ONLINE-REGELN (`dispatch_fifo`, `dispatch_edd`, `dispatch_atc`) entscheiden erst in dem Moment,
in dem ein Hoffahrzeug frei wird - und sehen dabei nur Aufträge, die bereits eingegangen sind
(Freigabe <= jetzt). Das ist der Alltag eines Disponenten. Die Zeiten dieser Pläne sind die
tatsächlich gefahrenen: das Fahrzeug startet die Anfahrt frühestens, wenn der Auftrag
freigegeben ist.

  - FIFO: ältester eingegangener Auftrag zuerst, dem nächstgelegenen freien Fahrzeug.
  - Frist zuerst (EDD): Auftrag mit der nächsten Frist zuerst, ohne Rücksicht auf Gewicht/Weg.
  - ATC (Apparent Tardiness Cost, Vepsäläinen & Morton 1987, hier mit Anfahrtszeit wie ATCS bei
    Lee/Bhaskaram/Pinedo 1997): dynamischer Prioritätsindex je (Fahrzeug, Auftrag)-Paar
        I = (w / (p + tau)) * exp(-max(0, Restpuffer) / (K * p_mittel))
    mit Gewicht w, Servicezeit p, Anfahrtszeit tau. Ist der Restpuffer (Frist minus voraus-
    sichtliches Ende bei sofortigem Start) groß, zählt fast nur Gewicht pro Aufwand (WSPT); wird
    er knapp oder negativ, springt der Index hoch bzw. bleibt bei w/(p+tau). Dringlichkeit und
    Gewicht werden also LAUFEND gegeneinander abgewogen - "dynamische Priorisierung".

VORAUSPLANUNG (`improve_plan`) kennt alle Aufträge des Fensters im Voraus (z. B. durch
Avisierung/Tor-Slots) und darf deshalb Fahrzeuge vorpositionieren: es startet bei den
Reihenfolgen der Online-Regeln, wertet sie aber mit den frühestmöglichen Zeiten aus und
verbessert per Umhängen (Auftrag in andere Position/anderes Fahrzeug) und Tauschen. Die lokale
Suche akzeptiert nur echte Verbesserungen, kann ihr Startergebnis also nie verschlechtern; danach
schärft Iterated Local Search (zufälliges Umhängen von drei Aufträgen + erneutes Polieren, nur
nicht-schlechtere Ergebnisse werden übernommen) die beste Lösung nach. Im Gegensatz zu manchen
anderen Demos dieses Portfolios (dock-demo: ILS/Tabu/3-opt verworfen) zahlt sich das hier messbar
aus: gegen den exakten Löser bei 12 Aufträgen 2/10 -> 10/10 Optimum-Treffer, bei 30 Aufträgen im
Mittel 15,8 -> 12,7 (exakt bzw. beste gefundene: 12,2) gewichtete Verspätung, siehe README.

Alle Pläne haben die Form `job_index -> (vehicle, start)` (siehe yard_evaluation.py)."""

import math
import random

import yard_constants as C
from yard_evaluation import sequence_cost, sequences_to_plan


def _dispatch(instance, choose):
    """Gemeinsame Ereignisschleife der Online-Regeln. `choose(t, idle, avail, loc)` liefert das
    (Fahrzeug, Auftrag)-Paar, das jetzt gestartet wird. Nicht-verzögernd: ein freies Fahrzeug
    wartet nur, wenn gerade kein freigegebener Auftrag offen ist."""
    jobs = instance.jobs
    m = instance.n_vehicles
    free_at = [0] * m
    loc = [None] * m  # Index des zuletzt bedienten Auftrags, None = noch am Depot
    sequences = [[] for _ in range(m)]
    plan = {}
    unassigned = set(range(len(jobs)))
    t = 0

    while unassigned:
        idle = [v for v in range(m) if free_at[v] <= t]
        avail = sorted(j for j in unassigned if jobs[j].release <= t)
        if idle and avail:
            v, j = choose(t, idle, avail, loc)
            start = t + instance.approach_time(loc[v], j)
            plan[j] = (v, start)
            free_at[v] = start + jobs[j].service
            loc[v] = j
            sequences[v].append(j)
            unassigned.remove(j)
        else:
            future = [free_at[v] for v in range(m) if free_at[v] > t]
            future += [jobs[j].release for j in unassigned if jobs[j].release > t]
            t = min(future)
    return plan, sequences


def _nearest_idle(instance, idle, loc, j):
    return min(idle, key=lambda v: (instance.approach_time(loc[v], j), v))


def dispatch_fifo(instance):
    def choose(t, idle, avail, loc):
        j = min(avail, key=lambda a: (instance.jobs[a].release, a))
        return _nearest_idle(instance, idle, loc, j), j

    return _dispatch(instance, choose)


def dispatch_edd(instance):
    def choose(t, idle, avail, loc):
        j = min(avail, key=lambda a: (instance.jobs[a].deadline, a))
        return _nearest_idle(instance, idle, loc, j), j

    return _dispatch(instance, choose)


def dispatch_atc(instance, k=C.ATC_K):
    jobs = instance.jobs
    mean_service = sum(j.service for j in jobs) / len(jobs)

    def choose(t, idle, avail, loc):
        best, best_key = None, None
        for j in avail:
            job = jobs[j]
            for v in idle:
                tau = instance.approach_time(loc[v], j)
                slack = job.deadline - (t + tau + job.service)
                index = job.weight / (job.service + tau) * math.exp(-max(0, slack) / (k * mean_service))
                key = (-index, j, v)
                if best_key is None or key < best_key:
                    best, best_key = (v, j), key
        return best

    return _dispatch(instance, choose)


# ------------------------------------------------------------------ Vorausplanung / lokale Suche

def _relocate_pass(instance, seqs, costs):
    improved = False
    for v1 in range(len(seqs)):
        pos1 = 0
        while pos1 < len(seqs[v1]):
            j = seqs[v1][pos1]
            removed = seqs[v1][:pos1] + seqs[v1][pos1 + 1:]
            cost_removed = sequence_cost(instance, removed)
            gain_base = costs[v1]

            best_delta, best_move = 0, None
            for v2 in range(len(seqs)):
                target = removed if v2 == v1 else seqs[v2]
                old_v2 = 0 if v2 == v1 else costs[v2]
                for pos2 in range(len(target) + 1):
                    if v2 == v1 and pos2 == pos1:
                        continue
                    candidate = target[:pos2] + [j] + target[pos2:]
                    new_cost = sequence_cost(instance, candidate)
                    if v2 == v1:
                        delta = new_cost - gain_base
                    else:
                        delta = (cost_removed + new_cost) - (gain_base + old_v2)
                    if delta < best_delta:
                        best_delta, best_move = delta, (v2, pos2, candidate, new_cost)

            if best_move is not None:
                v2, _, candidate, new_cost = best_move
                if v2 == v1:
                    seqs[v1], costs[v1] = candidate, new_cost
                else:
                    seqs[v1], costs[v1] = removed, cost_removed
                    seqs[v2], costs[v2] = candidate, new_cost
                improved = True
            else:
                pos1 += 1
    return improved


def _swap_pass(instance, seqs, costs):
    improved = False
    m = len(seqs)
    for v1 in range(m):
        for i in range(len(seqs[v1])):
            for v2 in range(v1, m):
                start_k = i + 1 if v2 == v1 else 0
                for k in range(start_k, len(seqs[v2])):
                    if i >= len(seqs[v1]) or k >= len(seqs[v2]):
                        continue
                    if v1 == v2:
                        cand = list(seqs[v1])
                        cand[i], cand[k] = cand[k], cand[i]
                        new_cost = sequence_cost(instance, cand)
                        if new_cost < costs[v1]:
                            seqs[v1], costs[v1] = cand, new_cost
                            improved = True
                    else:
                        cand1, cand2 = list(seqs[v1]), list(seqs[v2])
                        cand1[i], cand2[k] = cand2[k], cand1[i]
                        c1, c2 = sequence_cost(instance, cand1), sequence_cost(instance, cand2)
                        if c1 + c2 < costs[v1] + costs[v2]:
                            seqs[v1], seqs[v2] = cand1, cand2
                            costs[v1], costs[v2] = c1, c2
                            improved = True
    return improved


def local_search(instance, sequences, max_passes=30):
    """Umhängen + Tauschen, bis kein Zug mehr verbessert (oder `max_passes` erreicht ist)."""
    seqs = [list(s) for s in sequences]
    costs = [sequence_cost(instance, s) for s in seqs]
    for _ in range(max_passes):
        a = _relocate_pass(instance, seqs, costs)
        b = _swap_pass(instance, seqs, costs)
        if not (a or b):
            break
    return seqs


def iterated_local_search(instance, sequences, iterations=C.ILS_ITERATIONS, seed=0):
    """Iterated Local Search: verschiebt zufällig 3 Aufträge (Störung), poliert per lokaler Suche
    nach und übernimmt das Ergebnis, wenn es nicht schlechter ist. Zufall ist über `seed`
    festgelegt - dieselbe Instanz liefert immer denselben Plan."""
    rng = random.Random(seed)
    current = [list(s) for s in sequences]
    current_cost = sum(sequence_cost(instance, s) for s in current)
    best, best_cost = current, current_cost
    for _ in range(iterations):
        candidate = [list(s) for s in current]
        for _ in range(3):
            filled = [v for v in range(len(candidate)) if candidate[v]]
            v = rng.choice(filled)
            job = candidate[v].pop(rng.randrange(len(candidate[v])))
            target = rng.randrange(len(candidate))
            candidate[target].insert(rng.randint(0, len(candidate[target])), job)
        candidate = local_search(instance, candidate)
        cost = sum(sequence_cost(instance, s) for s in candidate)
        if cost <= current_cost:
            current, current_cost = candidate, cost
            if cost < best_cost:
                best, best_cost = candidate, cost
    return best


def improve_plan(instance, iterations=C.ILS_ITERATIONS, start_sequences=None):
    """Vorausplanung: startet von den Reihenfolgen aller drei Online-Regeln (die Zeiten werden
    frühestmöglich neu berechnet - das ist bereits die Vorpositionierung), verbessert jede per
    lokaler Suche und schärft die beste Endlösung mit Iterated Local Search nach.

    `start_sequences` erlaubt es Aufrufern, die Online-Reihenfolgen wiederzuverwenden, falls sie
    ohnehin schon berechnet wurden (siehe app.py), statt sie hier erneut zu bestimmen."""
    if start_sequences is None:
        start_sequences = [dispatch_atc(instance)[1], dispatch_edd(instance)[1], dispatch_fifo(instance)[1]]
    best_seqs, best_cost = None, None
    for seqs in start_sequences:
        polished = local_search(instance, seqs)
        cost = sum(sequence_cost(instance, s) for s in polished)
        if best_cost is None or cost < best_cost:
            best_seqs, best_cost = polished, cost
    best_seqs = iterated_local_search(instance, best_seqs, iterations=iterations)
    return sequences_to_plan(instance, best_seqs), best_seqs
