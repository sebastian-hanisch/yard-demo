"""Plotly-Visualisierungen: Einsatzplan je Hoffahrzeug (Gantt, Kernvisual), Hofplan mit den
Wegen der Wechselbrücken und Methodenvergleich."""

import yard_constants as C

# Legende am unteren Rand des Containers statt über der Zeichenfläche: relativ zur Zeichenfläche
# (`yref="paper"`, y=1.02) landete sie im Browser mitten im Diagramm und verdeckte Balken und Tore.
LEGEND_BOTTOM = dict(orientation="h", yref="container", yanchor="bottom", y=0.0, x=0)


def build_gantt_chart(instance, result, title=""):
    import plotly.graph_objects as go

    fig = go.Figure()
    plan = result["plan"]
    vehicle_names = [f"Fahrzeug {v + 1}" for v in range(instance.n_vehicles)]
    bar_height = 0.55

    approach_x, approach_base, approach_y, approach_hover = [], [], [], []
    for idx, info in plan.items():
        if info["approach"] > 0:
            approach_x.append(info["approach"])
            approach_base.append(info["start"] - info["approach"])
            approach_y.append(info["vehicle"])
            approach_hover.append(f"Leerfahrt zu Auftrag {idx + 1}: {info['approach']} min")
    fig.add_trace(
        go.Bar(
            x=approach_x, base=approach_base, y=approach_y, orientation="h", name="Leerfahrt", width=bar_height,
            marker=dict(color="rgba(150,150,150,0.35)", line=dict(width=0)),
            hovertext=approach_hover, hoverinfo="text",
        )
    )

    for kind in C.KINDS:
        idxs = [i for i, info in plan.items() if instance.jobs[i].kind == kind]
        if not idxs:
            continue
        fig.add_trace(
            go.Bar(
                x=[instance.jobs[i].service for i in idxs],
                base=[plan[i]["start"] for i in idxs],
                y=[plan[i]["vehicle"] for i in idxs],
                orientation="h", name=kind, width=bar_height,
                text=[str(i + 1) for i in idxs], textposition="inside", insidetextanchor="middle",
                textfont=dict(color="white", size=11),
                marker=dict(
                    color=C.KIND_COLORS[kind],
                    line=dict(
                        color=["#ff9800" if plan[i]["tardiness"] > 0 else "white" for i in idxs],
                        width=[3 if plan[i]["tardiness"] > 0 else 1 for i in idxs],
                    ),
                ),
                hovertext=[_job_hover(instance, i, plan[i]) for i in idxs], hoverinfo="text",
            )
        )

    fig.add_trace(
        go.Scatter(
            x=[instance.jobs[i].deadline for i in plan],
            y=[plan[i]["vehicle"] + bar_height / 2 + 0.12 for i in plan],
            mode="markers", name="Frist",
            marker=dict(
                symbol="triangle-up", size=9,
                color=["#ff9800" if plan[i]["tardiness"] > 0 else "#222" for i in plan],
            ),
            hovertext=[f"Auftrag {i + 1}: Frist {instance.jobs[i].deadline} min" for i in plan], hoverinfo="text",
        )
    )
    if any(info["tardiness"] > 0 for info in plan.values()):
        fig.add_trace(
            go.Scatter(
                x=[None], y=[None], mode="markers", name="Verspätet (oranger Rand, orange Frist)",
                marker=dict(size=14, symbol="square-open", line=dict(color="#ff9800", width=3), color="rgba(0,0,0,0)"),
            )
        )

    x_max = max(result["makespan"], max((j.deadline for j in instance.jobs), default=1), 1)
    fig.update_layout(
        title=title, barmode="overlay", template="plotly_white",
        height=190 + 75 * instance.n_vehicles,
        xaxis_title="Minuten ab Schichtbeginn", yaxis_title=None,
        legend=LEGEND_BOTTOM, margin=dict(t=50, b=110),
    )
    fig.update_yaxes(
        tickmode="array", tickvals=list(range(instance.n_vehicles)), ticktext=vehicle_names,
        range=[instance.n_vehicles - 0.4, -0.55], fixedrange=True, showgrid=False,
    )
    fig.update_xaxes(range=[0, x_max * 1.02], fixedrange=True)
    return fig


def _job_hover(instance, idx, info):
    job = instance.jobs[idx]
    late = f"<br><b>Verspätung: {info['tardiness']} min</b>" if info["tardiness"] > 0 else "<br>pünktlich"
    return (
        f"<b>Auftrag {idx + 1}</b> ({job.kind}, Gewicht {job.weight})<br>"
        f"{job.pick_label} → {job.drop_label}<br>"
        f"Freigabe {job.release} min | Start {info['start']} min | Ende {info['end']} min | Frist {job.deadline} min"
        f"<br>Wartezeit der Brücke: {info['wait']} min{late}"
    )


def build_yard_map(instance, result, title=""):
    import plotly.graph_objects as go

    fig = go.Figure()
    length, width = instance.yard_length, instance.yard_width
    fields = [
        ("Ankunftsfeld", 0, 0.3, "rgba(31,119,180,0.06)"),
        ("Mittelfeld", 0.3, 0.7, "rgba(127,127,127,0.07)"),
        ("Abfahrtsfeld", 0.7, 1.0, "rgba(214,39,40,0.06)"),
    ]
    for name, lo, hi, color in fields:
        fig.add_shape(
            type="rect", x0=length * lo, x1=length * hi, y0=C.PARK_ROW_YS[0] - 18, y1=C.PARK_ROW_YS[-1] + 18,
            fillcolor=color, line=dict(width=0), layer="below",
        )
        fig.add_annotation(
            x=length * (lo + hi) / 2, y=C.PARK_ROW_YS[-1] + 18, text=name, showarrow=False,
            yanchor="top", font=dict(size=10, color="#777"),
        )
    fig.add_shape(type="rect", x0=0, x1=length, y0=-22, y1=-4, fillcolor="rgba(60,60,60,0.10)", line=dict(width=0), layer="below")
    fig.add_annotation(x=length / 2, y=-13, text="Halle", showarrow=False, font=dict(size=10, color="#777"))

    fig.add_trace(
        go.Scatter(
            x=[d[0] for d in instance.doors], y=[d[1] for d in instance.doors], mode="markers+text",
            text=[d[2].replace("Tor ", "") for d in instance.doors], textposition="top center",
            textfont=dict(size=9, color="#555"),
            marker=dict(symbol="square", size=9, color="#444"), name="Tore",
            hovertext=[d[2] for d in instance.doors], hoverinfo="text",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[instance.depot_xy[0]], y=[instance.depot_xy[1]], mode="markers+text", text=["Depot"],
            textposition="bottom center", marker=dict(symbol="star", size=14, color="#222"), name="Depot",
            hoverinfo="skip",
        )
    )

    plan = result["plan"]
    shown = set()
    for idx in sorted(plan):
        job = instance.jobs[idx]
        (x1, y1), (x2, y2) = job.pick_xy, job.drop_xy
        # Vom Tor weg zuerst senkrecht, zum Tor hin zuerst waagerecht - sonst liegen alle Wege
        # zum Tor auf der Torlinie y=0 übereinander.
        corner = (x1, y2) if y1 == 0 else (x2, y1)
        fig.add_trace(
            go.Scatter(
                x=[x1, corner[0], x2], y=[y1, corner[1], y2], mode="lines+markers",
                line=dict(color=C.KIND_COLORS[job.kind], width=2),
                marker=dict(
                    symbol=["circle", "circle", "arrow"], size=[7, 0, 12], angleref="previous",
                    color=C.KIND_COLORS[job.kind],
                ),
                opacity=0.75, name=job.kind, legendgroup=job.kind, showlegend=job.kind not in shown,
                hovertext=[_job_hover(instance, idx, plan[idx])] * 3, hoverinfo="text",
            )
        )
        shown.add(job.kind)
        fig.add_annotation(
            x=x1, y=y1, text=str(idx + 1), showarrow=False, yshift=-9 if y1 == 0 else 9,
            font=dict(size=8, color=C.KIND_COLORS[job.kind]),
        )

    fig.update_layout(
        title=title, template="plotly_white", height=470,
        legend=LEGEND_BOTTOM, margin=dict(t=20, b=110),
    )
    fig.update_xaxes(range=[-15, length + 15], fixedrange=True, showgrid=False, title="Meter")
    fig.update_yaxes(range=[width + 20, -32], fixedrange=True, showgrid=False, title="Meter", scaleanchor=None)
    return fig


def build_comparison_chart(results):
    import plotly.graph_objects as go

    labels = [r["label"] for r in results]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels, y=[r["total_weighted_tardiness"] for r in results], marker_color="#d62728",
            text=[f"{r['n_late']} verspätet" for r in results], textposition="outside",
            name="Gewichtete Verspätung (Score)",
        )
    )
    fig.update_layout(
        yaxis_title="Gewichtete Verspätung (Gewicht × Minuten)", template="plotly_white", height=380,
        showlegend=False, margin=dict(t=30),
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def build_kind_tardiness_chart(results):
    import plotly.graph_objects as go

    fig = go.Figure()
    for r in results:
        fig.add_trace(
            go.Bar(x=list(C.KINDS), y=[r["avg_tardiness_by_kind"].get(k, 0.0) for k in C.KINDS], name=r["label"])
        )
    fig.update_layout(
        barmode="group", yaxis_title="Ø Verspätung (min)", template="plotly_white", height=400,
        legend=LEGEND_BOTTOM, margin=dict(t=20, b=90),
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig
