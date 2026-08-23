"""
Helper utility to convert sample text resumes into PDF format using ReportLab.
"""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def create_pdf_from_text(txt_path: Path, pdf_path: Path):
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter

    # Margins
    margin_x = 54
    y = height - 54

    for line in lines:
        text = line.rstrip()
        if not text:
            y -= 12
            continue

        if text.isupper() and len(text) < 40:
            c.setFont("Helvetica-Bold", 12)
            y -= 6
            c.drawString(margin_x, y, text)
            y -= 16
        elif "@" in text and ("Email" in text or "Phone" in text):
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(margin_x, y, text)
            y -= 14
        elif y == height - 54 or (lines.index(line) == 0):
            c.setFont("Helvetica-Bold", 16)
            c.drawString(margin_x, y, text)
            y -= 18
        else:
            c.setFont("Helvetica", 10)
            c.drawString(margin_x, y, text)
            y -= 14

        if y < 54:
            c.showPage()
            y = height - 54

    c.save()
    print(f"Generated PDF: {pdf_path}")

if __name__ == "__main__":
    resumes_dir = Path(__file__).parent / "resumes"
    for txt_file in resumes_dir.glob("*.txt"):
        pdf_file = txt_file.with_suffix(".pdf")
        create_pdf_from_text(txt_file, pdf_file)
