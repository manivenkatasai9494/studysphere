import io
from datetime import datetime
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_quiz_report_pdf(report_data: Dict[str, Any], topic: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=18, spaceAfter=12)
    elements = []

    elements.append(Paragraph("StudySphere AI — Quiz Report", title_style))
    elements.append(Paragraph(f"Topic: {topic}", styles["Normal"]))
    elements.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    score = report_data.get("score", "N/A")
    accuracy = report_data.get("accuracy", "N/A")
    elements.append(Paragraph(f"<b>Score:</b> {score}% | <b>Accuracy:</b> {accuracy}%", styles["Normal"]))
    elements.append(Spacer(1, 12))

    for section, key in [
        ("Concept Understanding", "concept_understanding"),
        ("Strong Areas", "strong_areas"),
        ("Weak Areas", "weak_areas"),
        ("Improvement Suggestions", "improvement_suggestions"),
    ]:
        val = report_data.get(key, "")
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        if val:
            elements.append(Paragraph(f"<b>{section}</b>", styles["Heading2"]))
            elements.append(Paragraph(str(val), styles["Normal"]))
            elements.append(Spacer(1, 8))

    per_q = report_data.get("per_question", [])
    if per_q:
        elements.append(Paragraph("<b>Question Breakdown</b>", styles["Heading2"]))
        table_data = [["#", "Result", "Feedback"]]
        for i, q in enumerate(per_q[:50], 1):
            table_data.append([
                str(i),
                str(q.get("correct", q.get("result", ""))),
                str(q.get("feedback", ""))[:80],
            ])
        t = Table(table_data, colWidths=[30, 60, 400])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        elements.append(t)

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()
