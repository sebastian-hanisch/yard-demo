"""PDF-Export des Einsatzplans (fpdf2, Helvetica-Kernfont).

Umlaute (ä/ö/ü/ß) sind in den Kernfonts unproblematisch; Gedankenstrich und Euro-Zeichen
dagegen nicht (siehe [[feedback_fpdf2_umlauts_are_fine]]) - daher hier durchgehend "-"."""

import time


def generate_yard_plan_pdf(label, instance, result):
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Einsatzplan Hoffahrzeuge", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Methode: {label}  -  Erstellt: {time.strftime('%d.%m.%Y %H:%M')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Zusammenfassung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    summary_rows = [
        ("Anzahl Aufträge", str(result["n_jobs"])),
        ("Anzahl Hoffahrzeuge", str(instance.n_vehicles)),
        ("Gewichtete Verspätung (Score)", str(result["total_weighted_tardiness"])),
        ("Verspätete Aufträge", f"{result['n_late']} von {result['n_jobs']}"),
        ("Leerfahrten gesamt", f"{result['empty_minutes']} min"),
        ("Alle Aufträge erledigt um", f"{result['makespan']} min"),
    ]
    for label_text, value_text in summary_rows:
        pdf.cell(80, 7, label_text, border=0)
        pdf.cell(0, 7, value_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    headers = ["Auftrag", "Art", "Von", "Nach", "Start", "Ende", "Frist", "Verspätung"]
    widths = [20, 28, 30, 30, 16, 16, 16, 24]
    for vehicle, sequence in enumerate(result["sequences"]):
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"Fahrzeug {vehicle + 1}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if not sequence:
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 6, "kein Einsatz", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
            continue
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(230, 230, 230)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, header, border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 9)
        for idx in sequence:
            job = instance.jobs[idx]
            info = result["plan"][idx]
            row = [
                str(idx + 1), job.kind, job.pick_label, job.drop_label, f"{info['start']}", f"{info['end']}",
                f"{job.deadline}", f"{info['tardiness']} min" if info["tardiness"] else "-",
            ]
            for value, width in zip(row, widths):
                pdf.cell(width, 7, value, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.ln(7)
        pdf.ln(3)

    return bytes(pdf.output())
