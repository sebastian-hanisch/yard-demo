"""Wiederverwendbares Panel zur Darstellung einer Methode im Methodenvergleich."""

import streamlit as st

from yard_pdf_export import generate_yard_plan_pdf
from yard_visualization import build_gantt_chart


def render_yard_panel(prefix, label, instance, result):
    m1, m2, m3 = st.columns(3)
    m1.metric("Gewichtete Verspätung (Score)", f"{result['total_weighted_tardiness']}")
    m2.metric("Verspätete Aufträge", f"{result['n_late']} von {result['n_jobs']}")
    m3.metric("Leerfahrten", f"{result['empty_minutes']} min")

    fig = build_gantt_chart(instance, result, title=label)
    st.plotly_chart(fig, use_container_width=True, key=f"{prefix}_gantt_chart")

    pdf_bytes = generate_yard_plan_pdf(label, instance, result)
    st.download_button(
        "📄 Einsatzplan als PDF herunterladen",
        data=pdf_bytes,
        file_name=f"einsatzplan_{prefix}.pdf",
        mime="application/pdf",
        key=f"{prefix}_pdf_download",
    )

    return result
