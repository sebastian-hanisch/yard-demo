# Hof-Disposition (Yard Management) – Streamlit-Demo

Interaktive Fall-Demo zur **Disposition von Hoffahrzeugen auf einem Betriebshof**: welches
Hoffahrzeug setzt welche Wechselbrücke wann von A nach B um, damit Abfahrts- und Tor-Fristen
gehalten werden? Teil des Portfolios für die Website "Sebastian Hanisch – Operations Research
und Machine Learning". Vorlage ist der Projekt-Eintrag "Hof-Scheduling" auf `projekte.html`
(Fahraufträge für Wechselbrücken steuern und priorisieren, Be- und Entladung); die Demo ist ein
bewusst vereinfachtes, frei erfundenes Modell - keine Kundendaten.

## Das Problem

Ein Hof hat **Tore** an der Hallenwand und dahinter drei Stellplatzfelder (**Ankunft**,
**Mittelfeld**, **Abfahrt**). Jeder **Fahrauftrag** verschiebt eine Wechselbrücke, wird zu einer
bestimmten Zeit frei und hat eine Frist. Drei Auftragsarten mit unterschiedlichem Gewicht der
Verspätung: **Abfahrt** (Gewicht 4, Tor → Abfahrtsfeld, Frist = Abfahrt der Linie),
**Bereitstellung** (Gewicht 2, Ankunftsfeld → Tor) und **Abräumen** (Gewicht 1, Tor →
Mittelfeld, großzügige Frist). Ziel: minimale **gewichtete Verspätung**, bei Gleichstand
minimale **Leerfahrtzeit**.

Als Scheduling-Problem: $Pm \mid r_j, s_{ij} \mid \sum w_j T_j$ – parallele Maschinen mit
Freigabezeiten und reihenfolgeabhängigen Rüstzeiten (die Anfahrt zur nächsten Brücke).
Schon $1 \| \sum w_j T_j$ ist stark NP-schwer.

**Abgrenzung im Portfolio:** `dock-demo` entscheidet, welche Relation an welchem Tor bearbeitet
wird (QAP, räumlich, ohne Zeit). `truck-appointment-demo` vergibt Ankunftstermine an anliefernde
LKW. Diese Demo betrifft die Fahrzeuge DAZWISCHEN: das Umsetzen der Brücken auf dem Hof.

## Methodik – vier Verfahren, zwei Wissensstände

**Online-Regeln** entscheiden erst, wenn ein Fahrzeug frei wird, und sehen nur bereits
freigegebene Aufträge:

- **FIFO** – ältester Auftrag zuerst, dem nächsten freien Fahrzeug (Baseline).
- **Frist zuerst (EDD)** – nächste Frist zuerst.
- **ATC** (Apparent Tardiness Cost, Vepsäläinen & Morton 1987, mit Anfahrtszeit wie ATCS bei Lee,
  Bhaskaram & Pinedo 1997) – dynamischer Index je (Fahrzeug, Auftrag)-Paar
  $I = \frac{w}{p+\tau}\exp\!\big(-\max\{0,\text{Restpuffer}\}/(K\bar p)\big)$; $K = 1$.

**Vorausplanung** kennt alle Aufträge des Fensters im Voraus (Avisierung, Tor-Slots) und darf
Fahrzeuge **vorpositionieren**: sie startet bei den Reihenfolgen der drei Online-Regeln,
wertet sie mit frühestmöglichen Zeiten aus und verbessert per Umhängen/Tauschen (lokale Suche)
plus Iterated Local Search (40 Iterationen, fester Seed – deterministisch).

**Exakt** (OR-Tools CP-SAT, `AddMultipleCircuit`, 10 s Limit) als Cross-Check auf Klick.

Die Primäransicht zeigt **dynamisch** die bei den aktuellen Reglern beste Methode. Die
Kernfrage-Sektion trennt den Wert von Vorwissen in zwei Effekte: *Vorpositionieren allein*
(dieselbe Reihenfolge wie die beste Online-Regel, aber frühestmögliche Zeiten) und *zusätzliches
Umplanen*.

## Gemessene Befunde (vor Auslieferung per Sweep geprüft)

**Vorwissen ist der größte Hebel** (20 Seeds je Konfiguration, gewichtete Verspätung, Mittel):

| Konfiguration | beste Online-Regel | gleiche Reihenfolge, vorpositioniert | Vorausplanung |
|---|---:|---:|---:|
| Abfahrts-Stoßzeit (30 Aufträge, 3 Fzg.) | 70,2 | 51,5 | 31,1 |
| Zu wenig Hoffahrzeuge (32, 2 Fzg.) | 170,6 | 138,9 | 80,7 |
| Weitläufiger Hof (30, 4 Fzg., 850 m) | 59,8 | 35,1 | 14,2 |

**FIFO ist deutlich am schlechtesten**, ATC senkt im Mittel gegenüber EDD (40 Seeds:
Stoßzeit 92 → 82, Zu wenig Fahrzeuge 215 → 172, Weitläufiger Hof 83 → 72) – **aber nicht auf
jedem Seed**: ATC ist besser auf 13/40, 25/40 bzw. 15/40 Seeds; bei mäßiger Last gewinnt EDD
öfter, ATC gewinnt bei Überlast und im Mittel. Die Presets zeigen bewusst Seeds mit sichtbarem
Verlauf FIFO > EDD > ATC > Vorausplanung; die App wählt die beste Online-Regel je Szenario neu.
Der K-Parameter ist flach: K = 0,3 … 3 liegt im Mittel innerhalb von ca. 10 %, gewählt K = 1.

**Bei geringer Last (Belastungsgrad ≈ 20 %) gibt es keine Verspätung** – alle Verfahren
gleich; Vorausplanung spart dann nur Leerfahrten (Preset "Ruhiger Vormittag": 33 → 18 min).

**Lokale Suche allein reichte nicht – ILS schließt die Lücke zum exakten Optimum weitgehend.**
Anders als bei manchen früheren Demos (dock-demo: ILS/Tabu/3-opt verworfen) lohnt sich hier die
Erweiterung: Treffer des exakten Optimums (gewichtete Verspätung + Leerfahrt):

| Aufträge / Fahrzeuge | nur Umhängen + Tauschen | + ILS (40 Iter.) | Laufzeit ILS |
|---|---:|---:|---:|
| 10 / 3 | 8 von 10 | 10 von 10 | 0,02 s |
| 12 / 3 | 2 von 10 (Lücke 4,7 %) | 10 von 10 | 0,03 s |
| 16 / 3 | 2 von 8 (Lücke 6,0 %) | 6 von 8 (Lücke 1,0 %) | 0,06 s |
| 30 / 3 (Exakt: 3 von 6 bewiesen) | 2 von 6 (Ø Verspätung 15,8) | 5 von 6 (12,7; Exakt/beste 12,2) | 0,45 s |

Bei sehr hoher Last bleibt eine Restlücke: Preset "Zu wenig Hoffahrzeuge" 36 (40 Iter.) vs. 31 bei
250 Iterationen und im 10-s-CP-SAT-Lauf (nicht bewiesen optimal) – 250 Iterationen würden im
Worst-Case über 6 s pro Reglerzug kosten. Die App zeigt diese Lücke im Exakt-Tab offen an.

**CP-SAT-Modell gegen Brute-Force geprüft** (alle Permutationen × Fahrzeug-Zuschnitte,
5 Aufträge, 2 und 3 Fahrzeuge): identische Optima. Bis 12 Aufträge < 0,1 s, 22 Aufträge 8/8
bewiesen (0,4 s), 30 Aufträge nur 3/6 innerhalb 10 s – dann als "Zeitlimit erreicht" gekennzeichnet.

## Design-Entscheidungen

- **Reine Ganzzahlen, Fahrzeiten aufgerundet** (`math.ceil`, nie `round`): Heuristik,
  unabhängige Prüfung (`check_feasible`) und CP-SAT lesen dieselbe Anfahrtsmatrix – keine
  Rundungsdifferenz möglich (Lehre aus `quaycrane-demo`).
- **Online-Pläne behalten ihre tatsächlichen Startzeiten.** Sie mit "frühestmöglichen Zeiten"
  neu zu berechnen würde ihnen unfaires Vorwissen schenken (Fahrzeug wäre schon vor der
  Freigabe losgefahren). Ein Test (`test_online_rules_never_use_information_from_the_future`)
  hält das fest.
- **Lexikografisches Tie-Breaking** in CP-SAT und Heuristik (`OBJ_BIG`): Leerfahrt kann nie eine
  Verspätung aufwiegen. Aus dem Solver-Plan wird nur die Reihenfolge übernommen und frühestmöglich
  neu ausgerollt (keine Leerlauf-Lücken im Gantt).
- **Keine Fahrzeug-Symmetrie:** identische Fahrzeuge, alle am Depot – das Modell braucht keinen
  Fahrzeugindex.
- **Bewusste Vereinfachungen:** keine Tor-Belegung/Blockade (ein Tor wird nicht "frei" oder
  "besetzt"), keine Fahrer-Pausen, keine Störungen, kein Rückweg zum Depot, feste Kupplungszeit und
  Hofgeschwindigkeit, Wegzeiten rechtwinklig (Manhattan).

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Hauptablauf (Primäransicht, Kernfrage, Expander) |
| `yard_constants.py` | Defaults, Regler-Grenzen, Farben, Presets |
| `yard_scenario.py` | Instanzerzeugung (Hof, Aufträge, Fahrzeitmatrizen) |
| `yard_evaluation.py` | Prüfung (`check_feasible`), Kennzahlen, Zielwert |
| `yard_heuristic.py` | FIFO / EDD / ATC, lokale Suche, ILS, Vorausplanung |
| `yard_cp_solver.py` | Exakter Referenzlöser (CP-SAT) |
| `yard_visualization.py` | Gantt je Fahrzeug, Hofplan, Vergleichsdiagramme |
| `yard_pdf_export.py` | PDF-Einsatzplan |
| `yard_presets.py` | Presets, Permalink (`SETTING_SPECS`), Seed-Button |
| `yard_ui_panel.py` | wiederverwendbares Methoden-Panel |
| `tests/` | 67 Tests (Szenario, Auswertung, Heuristiken, CP-SAT vs. Brute-Force, AppTest-Smoke) |

## Lokal starten

```bash
pip install -r requirements-dev.txt
streamlit run app.py
python -m pytest tests/ -v
```
