from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
import io

def generate_certificate_pdf(student_name, course_name, score, date):
    """
    Generates a PDF certificate in memory and returns the bytes.
    """
    buffer = io.BytesIO()
    
    # Create Canvas (Landscape Mode)
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)
    
    # 1. Draw Border
    c.setStrokeColor(colors.darkblue)
    c.setLineWidth(5)
    c.rect(30, 30, width-60, height-60)
    
    c.setStrokeColor(colors.gold)
    c.setLineWidth(2)
    c.rect(35, 35, width-70, height-70)

    # 2. Header
    c.setFont("Helvetica-Bold", 40)
    c.setFillColor(colors.darkblue)
    c.drawCentredString(width/2, height - 120, "CERTIFICATE")
    
    c.setFont("Helvetica", 20)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height - 150, "OF COMPLETION")

    # 3. Student Name
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height - 200, "This is to certify that")
    
    c.setFont("Helvetica-Bold", 30)
    c.setFillColor(colors.darkred)
    c.drawCentredString(width/2, height - 240, student_name)

    # 4. Course & Score
    c.setFont("Helvetica", 16)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height - 280, f"Has successfully completed the quiz: {course_name}")
    
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height - 310, f"With a Score of {score}%")

    # 5. Date & Signature
    c.setFont("Helvetica", 12)
    c.drawString(100, 100, f"Date: {date}")
    
    c.line(width-250, 110, width-50, 110)
    c.drawString(width-200, 90, "Authorized Signature")

    # Finalize
    c.showPage()
    c.save()
    
    buffer.seek(0)
    return buffer