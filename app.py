"""
Hof-Disposition (Yard Management) – interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Welches Hoffahrzeug fährt welche Wechselbrücke wann von A nach B, damit Abfahrts- und
Tor-Fristen gehalten werden? Siehe README für die Modell-Abgrenzung zu dock-demo (Tor-Zuordnung)
und truck-appointment-demo (Ankunftstermine).

Lauffähig mit: streamlit run app.py
"""

import streamlit as st

import yard_constants as C
from yard_cp_solver import solve_exact
from yard_evaluation import comparison_table, evaluate, objective_value, sequences_to_plan
from yard_heuristic import dispatch_atc, dispatch_edd, dispatch_fifo, improve_plan
from yard_pdf_export import generate_yard_plan_pdf
from yard_presets import (
    apply_preset,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sync_query_params,
)
from yard_scenario import generate_instance
from yard_ui_panel import render_yard_panel
from yard_visualization import (
    build_comparison_chart,
    build_gantt_chart,
    build_kind_tardiness_chart,
    build_yard_map,
)

st.set_page_config(page_title="Hof-Disposition – Sebastian Hanisch", layout="wide")

SCENARIO_KEYS = [
    "n_jobs_slider", "n_vehicles_slider", "arrival_window_slider", "peak_slider", "buffer_slider",
    "departure_slider", "yard_length_slider", "n_doors_slider", "seed_input",
]

LABEL_FIFO = "FIFO (Eingangsreihenfolge)"
LABEL_EDD = "Frist zuerst (EDD)"
LABEL_ATC = "ATC (dynamische Priorität)"
LABEL_OFFLINE = "Vorausplanung (kennt alle Aufträge)"
LABEL_PREPOSITIONED = "Beste Online-Reihenfolge, vorpositioniert"


@st.cache_data(show_spinner=False)
def _compute_heuristics(scenario_key):
    instance = generate_instance(*scenario_key)

    online = []
    for label, rule in ((LABEL_FIFO, dispatch_fifo), (LABEL_EDD, dispatch_edd), (LABEL_ATC, dispatch_atc)):
        plan, sequences = rule(instance)
        online.append((evaluate(instance, plan, label=label), sequences))

    best_online, best_online_sequences = min(online, key=lambda pair: objective_value(pair[0]))
    prepositioned = evaluate(
        instance, sequences_to_plan(instance, best_online_sequences), label=LABEL_PREPOSITIONED
    )

    offline_plan, offline_sequences = improve_plan(instance)
    offline = evaluate(instance, offline_plan, label=LABEL_OFFLINE)

    results = [r for r, _ in online] + [offline]
    return instance, results, best_online, prepositioned, offline_sequences


@st.cache_data(show_spinner=False)
def _compute_exact(scenario_key, hint_sequences):
    """Getrennt von `_compute_heuristics`, damit der exakte Löser nicht automatisch bei jeder
    Regler-Änderung mitläuft (kann bei größeren Szenarien mehrere Sekunden dauern) - nur auf
    Klick. `hint_sequences` (die Vorausplanung) gibt CP-SAT sofort einen gültigen Startpunkt."""
    instance = generate_instance(*scenario_key)
    solve = solve_exact(instance, time_limit_seconds=C.EXACT_SOLVE_TIME_LIMIT_SECONDS, hint_sequences=hint_sequences)
    if not solve.feasible:
        return None
    label = "Exakt (OR-Tools)" if solve.optimal else "Exakt (OR-Tools, Zeitlimit)"
    return {"eval": evaluate(instance, solve.plan, label=label), "optimal": solve.optimal, "wall_time_ms": solve.wall_time_ms}


st.title("🚛 Hof-Disposition (Yard Management)")
st.markdown(
    """
Auf einem Betriebshof stehen **Wechselbrücken** an den Toren, in den Stellplatzfeldern und im
Abfahrtsbereich - und **Hoffahrzeuge** setzen sie um: zum Tor, wenn entladen werden soll, vom Tor
zur Abfahrt, sobald beladen ist, oder leer ins Mittelfeld. Jeder **Fahrauftrag** wird zu einer
bestimmten Zeit frei und hat eine **Frist** (Beginn des Tor-Slots, Abfahrt der Linie) - und nicht
jede Frist ist gleich teuer: eine verpasste Abfahrt wiegt mehr als eine spät geräumte Leerbrücke.
Gesucht: wer fährt was in welcher Reihenfolge, damit die **gewichtete Verspätung** minimal wird.
Wie das Modell und die Verfahren funktionieren, steht im Expander "Wie funktioniert diese Demo?"
weiter unten, die formale Herleitung im Expander "📐 Mathematische Formulierung".
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
PRESET_HELP = {
    "Ruhiger Vormittag": "Wenige Aufträge, viel Puffer - kein Auftrag kommt zu spät, die Regeln unterscheiden sich "
    "praktisch nur in den Leerfahrten.",
    "Abfahrts-Stoßzeit": "Viele Abfahrts-Aufträge mit knappen Fristen treffen in einer Welle ein - hier zeigt sich, "
    "was dynamische Priorisierung und Vorwissen wirklich bringen.",
    "Zu wenig Hoffahrzeuge": "Zwei Fahrzeuge für einen vollen Hof: Die Auslastung liegt nahe 100 %, und die Frage ist, "
    "wessen Frist geopfert wird.",
    "Weitläufiger Hof": "Sehr langer Hof mit vielen Toren: Wege dominieren, Leerfahrten und Vorpositionieren "
    "werden zum entscheidenden Hebel.",
}
preset_cols = st.columns(len(C.PRESETS))
for i, name in enumerate(C.PRESETS.keys()):
    with preset_cols[i]:
        st.button(name, use_container_width=True, on_click=apply_preset, args=(name,), help=PRESET_HELP[name])

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    n_jobs = st.slider("Anzahl Fahraufträge", *bounds("n_jobs_slider"), key="n_jobs_slider")
    n_vehicles = st.slider("Anzahl Hoffahrzeuge", *bounds("n_vehicles_slider"), key="n_vehicles_slider")
    seed = st.number_input("Zufalls-Seed", *bounds("seed_input"), key="seed_input", step=1)

    st.markdown("**Hof**")
    yard_length = st.slider(
        "Länge des Hofs (m)", *bounds("yard_length_slider"), step=10, key="yard_length_slider",
        help="Je länger der Hof, desto weiter liegen Ankunfts-, Mittel- und Abfahrtsfeld sowie die Tore "
        "auseinander - Fahrzeiten und Leerfahrten wachsen.",
    )
    n_doors = st.slider("Anzahl Tore", *bounds("n_doors_slider"), key="n_doors_slider")

    st.markdown("**Aufträge**")
    arrival_window = st.slider(
        "Zeitfenster der Freigaben (min)", *bounds("arrival_window_slider"), step=10, key="arrival_window_slider",
        help="Über welchen Zeitraum die Aufträge freigegeben werden - klein = alles drängt gleichzeitig, "
        "groß = entzerrt.",
    )
    peak = st.slider(
        "Anteil Aufträge in der Stoßzeit", *bounds("peak_slider"), step=5, format="%d%%", key="peak_slider",
        help="Wie viele Aufträge sich in einer Welle um die Mitte des Zeitfensters häufen (0 % = gleichmäßig verteilt).",
    )
    departure = st.slider(
        "Anteil Abfahrts-Aufträge", *bounds("departure_slider"), step=5, format="%d%%", key="departure_slider",
        help="Beladene Brücken zur Abfahrt (Gewicht 4, knappe Frist). Der Rest verteilt sich auf Bereitstellungen "
        "(Gewicht 2) und Abräum-Fahrten (Gewicht 1, großzügige Frist).",
    )

    st.markdown("**Fristen**")
    buffer = st.slider(
        "Ø Fristpuffer (min)", *bounds("buffer_slider"), key="buffer_slider",
        help="Zeit zwischen frühestmöglichem Ende und Frist. Klein = jede Verzögerung schlägt durch. "
        "Abfahrts-Aufträge haben davon nur 60 %, Abräum-Fahrten 250 %.",
    )

    st.button(
        "🎲 Neue Aufträge generieren", use_container_width=True, on_click=randomize_seed,
        help="Würfelt einen neuen Zufalls-Seed für die Auftragslage.",
    )

current_values = {key: st.session_state[key] for key in SCENARIO_KEYS}
sync_query_params(current_values)

scenario_key = (
    int(n_jobs), int(n_vehicles), int(arrival_window), int(peak), int(buffer), int(departure),
    int(yard_length), int(n_doors), int(seed),
)

with st.spinner("Berechne Einsatzpläne..."):
    instance, results, best_online, prepositioned, offline_sequences = _compute_heuristics(scenario_key)

# Bei Gleichstand gewinnt die spätere (aufwändigere) Methode.
best = min(reversed(results), key=objective_value)
baseline = max(results, key=lambda r: r["total_weighted_tardiness"])
score_saved = baseline["total_weighted_tardiness"] - best["total_weighted_tardiness"]
pct_saved = (score_saved / baseline["total_weighted_tardiness"] * 100) if baseline["total_weighted_tardiness"] > 0 else 0.0

st.markdown("## 🎯 Ihr bester Einsatzplan")
st.caption(f"Methode: **{best['label']}** - wird bei jedem Lauf neu anhand der gewichteten Verspätung bestimmt.")

m1, m2, m3 = st.columns(3)
m1.metric(
    "Gewichtete Verspätung (Score)", f"{best['total_weighted_tardiness']}",
    delta=f"{best['total_weighted_tardiness'] - baseline['total_weighted_tardiness']} ggü. {baseline['label']}"
    if score_saved > 0 else None,
    delta_color="inverse",
)
m2.metric("Verspätete Aufträge", f"{best['n_late']} von {best['n_jobs']}")
m3.metric("Leerfahrten", f"{best['empty_minutes']} min")

if score_saved > 0:
    st.success(
        f"⏱️ **{best['label']}** spart hier **{score_saved} Punkte** gewichtete Verspätung "
        f"({pct_saved:.0f} %) gegenüber '{baseline['label']}'."
    )

st.plotly_chart(build_gantt_chart(instance, best, title=best["label"]), use_container_width=True, key="primary_gantt_chart")
st.caption(
    "Balken = Auftrag (Nummer im Balken), graue Balken = Leerfahrt zur Brücke, schwarzer Strich = Frist, "
    "oranger Rand = verspätet."
)

st.markdown("#### 🗺️ Hofplan")
st.plotly_chart(build_yard_map(instance, best, title=""), use_container_width=True, key="primary_yard_map")
st.caption(
    "Wege der Wechselbrücken (Kreis = Abholort, Pfeil = Abstellort), Farbe = Auftragsart. Gerechnet wird mit "
    "rechtwinkligen Hofwegen bei ca. 9 km/h."
)

st.download_button(
    "📄 Einsatzplan als PDF herunterladen", data=generate_yard_plan_pdf(best["label"], instance, best),
    file_name="einsatzplan_optimiert.pdf", mime="application/pdf", key="primary_pdf_download",
)

st.caption(
    "Ermittelt mit der besten von vier eigenen Verfahren für dieses Szenario. Die Vorausplanung setzt voraus, "
    "dass die Aufträge vorab bekannt sind (z. B. durch Avisierung); die beste reine Online-Regel steht im "
    "Abschnitt darunter. Details zu allen Verfahren und dem Vergleich mit Google OR-Tools unten."
)

st.markdown("---")

st.subheader("📐 Was ist Vorwissen über kommende Aufträge wert?")
st.markdown(
    """
Kernfrage dieser Demo: Ein Disponent, der erst reagiert, wenn ein Fahrzeug frei wird, sieht nur
**bereits eingegangene** Aufträge (**Online-Regeln**). Wer die Aufträge schon vorab kennt - etwa durch
Avisierung und Tor-Slots -, kann zweierlei tun: **Fahrzeuge vorpositionieren**, statt erst nach der
Freigabe loszufahren, und die **Reihenfolge neu planen**. Hier live für Ihre aktuelle Konfiguration
gemessen, nicht nur behauptet - beide Effekte getrennt.
"""
)

rho = instance.mean_utilization_estimate()
online_score = best_online["total_weighted_tardiness"]
pre_score = prepositioned["total_weighted_tardiness"]
off_score = results[3]["total_weighted_tardiness"]
pre_delta = pre_score - online_score
off_delta = off_score - online_score

c1, c2, c3, c4 = st.columns(4)
c1.metric("Belastungsgrad (Näherung)", f"{rho * 100:.0f} %", help="(Servicezeit + typische Leerfahrt) aller Aufträge / (Fahrzeuge × Zeitfenster) - eine Faustgröße, Wellen und Fristen bildet sie nicht ab.")
c2.metric(f"Beste Online-Regel: {best_online['label'].split(' (')[0]}", f"{online_score}")
c3.metric(
    "Gleiche Reihenfolge, vorpositioniert", f"{pre_score}",
    delta=f"{pre_delta} ggü. Online" if pre_delta != 0 else None, delta_color="inverse",
)
c4.metric(
    "Vorausplanung (neu geplant)", f"{off_score}",
    delta=f"{off_delta} ggü. Online" if off_delta != 0 else None, delta_color="inverse",
)

online_line = " · ".join(f"{r['label'].split(' (')[0]}: {r['total_weighted_tardiness']}" for r in results[:3])
st.caption(f"Online-Regeln im Vergleich (Score): {online_line}")

if online_score == 0:
    st.info(
        f"ℹ️ Bei diesem Belastungsgrad (≈ {rho * 100:.0f} %) kommt mit den Online-Regeln kein Auftrag zu spät - "
        f"Vorwissen kann hier keine Verspätung mehr sparen, nur Leerfahrten: {best_online['empty_minutes']} min "
        f"(Online) gegenüber {results[3]['empty_minutes']} min (Vorausplanung)."
    )
elif off_delta < 0:
    share_pre = -pre_delta / online_score * 100
    share_total = -off_delta / online_score * 100
    st.success(
        f"✅ Vorwissen wirkt hier klar: **Vorpositionieren allein** spart {share_pre:.0f} % der gewichteten Verspätung, "
        f"mit **zusätzlichem Umplanen** sind es insgesamt {share_total:.0f} % (von {online_score} auf {off_score} Punkte)."
    )
else:
    st.warning(
        "⚠️ Vorwissen bringt bei dieser Konfiguration keine Verbesserung - die Online-Reihenfolge ist bereits "
        "so gut wie die Vorausplanung (z. B. bei extremer Überlast, wo ohnehin jede Frist reißt)."
    )

st.markdown("---")

with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich"):
    prefixes = ["fifo", "edd", "atc", "offline"]
    tab_labels = [r["label"] for r in results] + ["🧮 Exakt (OR-Tools)", "📊 Vergleich"]
    tabs = st.tabs(tab_labels)

    for tab, r, prefix in zip(tabs[: len(results)], results, prefixes):
        with tab:
            render_yard_panel(prefix, r["label"], instance, r)

    tab_exact, tab_compare = tabs[len(results)], tabs[len(results) + 1]

    exact_eval = None
    with tab_exact:
        st.caption(
            "Löst dasselbe Modell exakt statt mit unseren eigenen Verfahren - dient als Cross-Check für die "
            f"Vorausplanung. Auf {C.EXACT_SOLVE_TIME_LIMIT_SECONDS}s begrenzt (bei vielen Aufträgen manchmal "
            "nur die beste gefundene, nicht bewiesen optimale Lösung - wird dann so gekennzeichnet)."
        )
        solve_clicked = st.button("🧮 Mit OR-Tools lösen", key="exact_solve_btn")
        if solve_clicked:
            st.session_state["exact_scenario_key"] = scenario_key

        if st.session_state.get("exact_scenario_key") == scenario_key:
            hint = tuple(tuple(seq) for seq in offline_sequences)
            with st.spinner(f"Berechne exakte Lösung (OR-Tools CP-SAT, bis zu {C.EXACT_SOLVE_TIME_LIMIT_SECONDS}s)..."):
                exact_result = _compute_exact(scenario_key, hint)

            if exact_result is None:
                st.error("🚫 OR-Tools hat innerhalb des Zeitlimits keine gültige Lösung gefunden.")
            else:
                exact_eval = exact_result["eval"]
                ref = results[3]
                gap = ref["total_weighted_tardiness"] - exact_eval["total_weighted_tardiness"]
                gap_pct = (gap / exact_eval["total_weighted_tardiness"] * 100) if exact_eval["total_weighted_tardiness"] > 0 else 0.0
                same_score = gap == 0
                ms = f"{exact_result['wall_time_ms']:.0f} ms"

                if exact_result["optimal"]:
                    if same_score:
                        st.info(
                            f"✅ Optimal gelöst ({ms}): **{ref['label']}** erreicht bereits die optimale "
                            f"gewichtete Verspätung ({exact_eval['total_weighted_tardiness']})."
                        )
                    else:
                        st.info(
                            f"📐 Optimal gelöst ({ms}): Optimum liegt bei {exact_eval['total_weighted_tardiness']} - "
                            f"Lücke der Vorausplanung: {gap} Punkte ({gap_pct:.0f} %)."
                        )
                else:
                    if gap <= 0:
                        st.warning(
                            f"⏱️ Zeitlimit erreicht, kein Optimalitätsbeweis ({ms}): **{ref['label']}** "
                            f"({ref['total_weighted_tardiness']}) erreicht oder unterbietet sogar die beste vom "
                            f"Solver gefundene Lösung ({exact_eval['total_weighted_tardiness']})."
                        )
                    else:
                        st.warning(
                            f"⏱️ Zeitlimit erreicht, kein Optimalitätsbeweis ({ms}): beste bislang gefundene Lösung "
                            f"liegt bei {exact_eval['total_weighted_tardiness']} - {gap} Punkte ({gap_pct:.0f} %) unter "
                            "der Vorausplanung, aber ohne Optimalitätsgarantie."
                        )
                render_yard_panel("exact", exact_eval["label"], instance, exact_eval)
        elif "exact_scenario_key" in st.session_state:
            st.info(
                "ℹ️ Die zuletzt berechnete exakte Lösung bezog sich auf ein anderes Szenario - "
                "Einstellungen geändert? Erneut auf '🧮 Mit OR-Tools lösen' klicken."
            )
        else:
            st.info("Noch keine Lösung berechnet – auf den Button oben klicken.")

    with tab_compare:
        all_results = list(results) + ([exact_eval] if exact_eval is not None else [])
        st.dataframe(comparison_table(all_results), use_container_width=True, hide_index=True)
        st.plotly_chart(build_comparison_chart(all_results), use_container_width=True, key="comparison_chart")
        st.plotly_chart(build_kind_tardiness_chart(all_results), use_container_width=True, key="kind_tardiness_chart")

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
Der Hof hat **Tore** an der Hallenwand und dahinter drei Stellplatzfelder: **Ankunftsfeld** (hier
stehen frisch angelieferte Wechselbrücken), **Mittelfeld** und **Abfahrtsfeld** (hier warten
beladene Brücken auf die Abholung). **Hoffahrzeuge** starten am Depot und setzen jeweils eine
Brücke um; ein Auftrag besteht aus Anfahrt (Leerfahrt), An- und Abkuppeln (fest 4 min) und der
beladenen Fahrt.

Es gibt drei **Auftragsarten** mit unterschiedlichem Gewicht der Verspätung:

- **Abfahrt** (Gewicht 4): beladene Brücke vom Tor zum Abfahrtsfeld - Frist ist die Abfahrt der Linie.
- **Bereitstellung** (Gewicht 2): Brücke vom Ankunftsfeld ans Tor - Frist ist der Beginn des Tor-Slots.
- **Abräumen** (Gewicht 1): leere Brücke vom Tor ins Mittelfeld - großzügige Frist.

Zielgröße ist die **gewichtete Verspätung**: Verspätung je Auftrag (Ende minus Frist, mindestens 0)
mal Gewicht, aufsummiert. Bei Gleichstand entscheiden die **Leerfahrten**.

Das Problem ist mit der **Tourenplanung (VRP)** verwandt - genauer ein VRP mit Zeitfenstern und
Abhol-/Zustell-Aufträgen (jeder Auftrag ist eine feste Fahrt von A nach B, das Fahrzeug fährt
dazwischen leer weiter) - unterscheidet sich aber in drei Punkten: Ziel ist nicht die kürzeste
Strecke, sondern die **gewichtete Verspätung** gegen Fristen (die Strecke zählt nur als
Tie-Breaker), es gibt weder Rückkehr zum Depot noch Kapazitätsgrenzen, und ein Disponent sieht
nur **bereits freigegebene** Aufträge (Online-Betrieb). Gleichwertig lässt es sich als
Scheduling-Problem auf parallelen Maschinen lesen, bei dem die Anfahrt die reihenfolgeabhängige
Rüstzeit ist.

Vier Verfahren stehen zur Auswahl (im Expander "Wie wir das erreichen" alle nebeneinander),
zusätzlich eine **exakte Referenzlösung** (Google OR-Tools CP-SAT):

- **FIFO**: ältester eingegangener Auftrag zuerst, dem nächsten freien Fahrzeug - Referenzpunkt.
- **Frist zuerst (EDD)**: der Auftrag mit der nächsten Frist zuerst, ohne Rücksicht auf Gewicht und Weg.
- **ATC (dynamische Priorität)**: wägt bei jeder Entscheidung Gewicht, Aufwand (inkl. Anfahrt) und
  verbleibenden Puffer gegeneinander ab. Ein Auftrag mit reichlich Puffer wartet, ein dringender
  wird vorgezogen - und wenn ohnehin alles brennt, gewinnt das Gewicht pro Aufwand.
- **Vorausplanung**: kennt alle Aufträge im Voraus, darf Fahrzeuge vorpositionieren und verbessert
  die Online-Reihenfolgen durch Umhängen und Tauschen von Aufträgen (lokale Suche plus Iterated
  Local Search).

Die drei **Online-Regeln** sehen nur, was schon freigegeben ist - so arbeitet ein Disponent im
Alltag. Die **Vorausplanung** ist kein Gegenkandidat auf gleicher Datenbasis, sondern zeigt, was
Avisierung und Tor-Slots wert sind (siehe Abschnitt "Was ist Vorwissen ... wert?").

Die Primäransicht zeigt **dynamisch** die bei den aktuellen Einstellungen tatsächlich beste
Methode. Der **Einsatzplan** zeigt je Fahrzeug die Aufträge in zeitlicher Reihenfolge, der
**Hofplan** die Wege der Brücken.
        """
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Fahrauftrags-Disposition auf dem Hof** als Scheduling-Problem auf parallelen Maschinen mit
Freigabezeiten und reihenfolgeabhängigen Rüstzeiten (hier: Anfahrten), in der Notation von Graham
et al. $Pm \mid r_j,\, s_{ij} \mid \sum_j w_j T_j$. Schon der Spezialfall mit einer Maschine ohne
Rüstzeiten, $1 \,\|\, \sum_j w_j T_j$, ist stark NP-schwer (Lenstra, Rinnooy Kan & Brucker 1977).

Gegeben Aufträge $j = 1, \dots, n$ mit Freigabe $r_j$, Servicezeit $p_j$ (An-/Abkuppeln plus
beladene Fahrt), Frist $d_j$ und Gewicht $w_j$, Anfahrtszeiten $\tau_{ij}$ (leer vom Abstellort von
$i$ zum Abholort von $j$; $\tau_{0j}$ ab dem Depot) und $m$ identische Hoffahrzeuge, die zur Zeit 0 am
Depot stehen.

Entscheidungsvariablen: $x_{ij} \in \{0,1\}$ (ein Fahrzeug bedient $j$ direkt nach $i$; Knoten $0$ =
Depot), Startzeit $S_j \ge r_j$ (Fahrzeug steht am Abholort und kuppelt an) und Verspätung $T_j$.

$$
\sum_{i \ne j} x_{ij} = 1 \;\; \forall j, \qquad \sum_{j \ne i} x_{ij} = 1 \;\; \forall i \ge 1, \qquad \sum_{j} x_{0j} \le m
$$

$$
x_{0j} = 1 \Rightarrow S_j \ge \tau_{0j}, \qquad x_{ij} = 1 \Rightarrow S_j \ge S_i + p_i + \tau_{ij}, \qquad T_j \ge S_j + p_j - d_j, \;\; T_j \ge 0
$$

Zielfunktion: minimiere primär die gewichtete Verspätung, als lexikografisches
Tie-Breaking-Ziel die gesamte Leerfahrtzeit (verhindert Umwege bei gleich guter Verspätung):

$$
\min \; \Big(\sum_j w_j T_j\Big) \cdot W \;+\; \sum_{i,j} \tau_{ij}\, x_{ij}
$$

mit $W$ so groß, dass Leerfahrt nie eine Verspätung aufwiegen kann.

**ATC-Index** (Vepsäläinen & Morton 1987, mit Anfahrtszeit wie ATCS bei Lee, Bhaskaram & Pinedo 1997).
Wird ein Fahrzeug zur Zeit $t$ frei, ist für jedes Paar aus wartendem Auftrag $j$ und freiem Fahrzeug
mit Anfahrt $\tau$

$$
I_{j} \;=\; \frac{w_j}{p_j + \tau}\,\exp\!\Big(-\frac{\max\{0,\; d_j - (t + \tau + p_j)\}}{K\,\bar p}\Big)
$$

mit mittlerer Servicezeit $\bar p$ und Lookahead-Parameter $K$ (hier $K = KVALUE$). Es wird das Paar mit
dem größten Index gestartet. Ist der Restpuffer groß, zählt praktisch nur $w_j/(p_j+\tau)$ (kurze,
wichtige Aufträge zuerst); wird er knapp oder negativ, ist der Exponentialterm 1 - Dringlichkeit
und Gewicht sind laufend gegeneinander abgewogen.

Gelöst in `yard_cp_solver.py` mit Google OR-Tools CP-SAT (`AddMultipleCircuit`
über die Bögen $x_{ij}$, ein Fahrzeugindex ist wegen identischer Fahrzeuge nicht nötig), auf
LIMIT_PLACEHOLDERs Rechenzeit begrenzt - bei kleineren Instanzen das bewiesene Optimum, bei vielen
Aufträgen manchmal nur die beste innerhalb des Zeitlimits gefundene Lösung (dann klar als
"Zeitlimit erreicht" gekennzeichnet).
        """.replace("LIMIT_PLACEHOLDER", str(C.EXACT_SOLVE_TIME_LIMIT_SECONDS)).replace("KVALUE", f"{C.ATC_K:g}")
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
