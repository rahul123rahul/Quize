from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import qrcode
import os

def register_fonts():
    """Attempts to register custom stylish fonts. Falls back to standard if not found."""
    fonts = {
        "Cursive": "GreatVibes-Regular.ttf",  # Heading
        "Serif": "PlayfairDisplay-Bold.ttf", # Name
        "Sans": "Montserrat-Regular.ttf"     # Body
    }
    
    registered = {}
    for name, filename in fonts.items():
        try:
            if os.path.exists(filename):
                pdfmetrics.registerFont(TTFont(name, filename))
                registered[name] = name
            else:
                # Fallbacks
                if name == "Cursive": registered[name] = "Times-Italic"
                elif name == "Serif": registered[name] = "Times-Bold"
                else: registered[name] = "Helvetica"
        except:
            registered[name] = "Helvetica"
    return registered

def draw_modern_border(c, width, height):
    """Draws a sophisticated side-accent modern border."""
    # 1. Main Background Stroke
    c.setStrokeColor(colors.HexColor('#2C3E50'))
    c.setLineWidth(3)
    c.rect(20, 20, width-40, height-40)

    # 2. Side Accents (Thick Gold/Blue Bars)
    # Left Bar
    c.setFillColor(colors.HexColor('#2C3E50')) # Dark Navy
    c.rect(20, 20, 30, height-40, fill=1, stroke=0)
    
    # Right Bar
    c.setFillColor(colors.HexColor('#2C3E50'))
    c.rect(width-50, 20, 30, height-40, fill=1, stroke=0)

    # 3. Inner Gold Accent Line
    c.setStrokeColor(colors.HexColor('#F39C12')) # Gold
    c.setLineWidth(2)
    c.line(55, 30, 55, height-30) # Left inner
    c.line(width-55, 30, width-55, height-30) # Right inner

    # 4. Corner Flourishes (Modern Squares)
    c.setFillColor(colors.HexColor('#F39C12'))
    c.rect(15, 15, 10, 10, fill=1, stroke=0) # Bottom Left
    c.rect(width-25, 15, 10, 10, fill=1, stroke=0) # Bottom Right
    c.rect(15, height-25, 10, 10, fill=1, stroke=0) # Top Left
    c.rect(width-25, height-25, 10, 10, fill=1, stroke=0) # Top Right

def generate_certificate_pdf(student_name, course_name, score, date, attempt_id, cert_type="Completion"):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)
    
    # Register Fonts
    fonts = register_fonts()
    
    # --- DESIGN ---
    draw_modern_border(c, width, height)
    
    # --- HEADER ---
    if cert_type == "Participation":
        title_text = "Certificate of Participation"
        sub_text = "THIS CERTIFICATE IS PROUDLY PRESENTED TO"
    else:
        title_text = "Certificate of Achievement"
        sub_text = "THIS CERTIFICATE IS AWARDED TO"

    # Cursive Heading
    c.setFont(fonts["Cursive"], 55)
    c.setFillColor(colors.HexColor('#2C3E50')) # Dark Navy
    c.drawCentredString(width/2, height - 120, title_text)
    
    # Sub-heading
    c.setFont(fonts["Sans"], 10)
    c.setFillColor(colors.HexColor('#7F8C8D')) # Gray
    c.drawCentredString(width/2, height - 160, sub_text)

    # --- STUDENT NAME ---
    # Draw a line under the name
    c.setStrokeColor(colors.HexColor('#F39C12')) # Gold
    c.setLineWidth(1)
    c.line(width/2 - 200, height - 230, width/2 + 200, height - 230)
    
    # Name
    c.setFont(fonts["Serif"], 42)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height - 220, str(student_name).title())

    # --- BODY TEXT ---
    c.setFont(fonts["Sans"], 14)
    c.setFillColor(colors.HexColor('#34495E'))
    
    if cert_type == "Participation":
        body_1 = "For their active and enthusiastic participation in"
        body_2 = str(course_name)
        score_text = ""
    else:
        body_1 = "For successfully completing the comprehensive assessment for"
        body_2 = str(course_name)
        score_text = f"with an outstanding score of {score}%"

    c.drawCentredString(width/2, height - 280, body_1)
    
    c.setFont(fonts["Serif"], 22) # Course Name larger
    c.setFillColor(colors.HexColor('#2C3E50'))
    c.drawCentredString(width/2, height - 315, body_2)
    
    c.setFont(fonts["Sans"], 14)
    c.setFillColor(colors.HexColor('#34495E'))
    c.drawCentredString(width/2, height - 345, score_text)

    # --- FOOTER (Signatures & Date) ---
    footer_y = 100
    
    # Date Area
    c.setFont(fonts["Sans"], 12)
    c.drawString(100, footer_y + 10, "Date Issued:")
    c.setFont(fonts["Serif"], 14)
    c.drawString(100, footer_y - 10, str(date))
    
    # Signature Area
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.line(width-300, footer_y, width-100, footer_y) # Signature Line
    
    c.setFont(fonts["Sans"], 12)
    c.drawCentredString(width-200, footer_y - 20, "Authorized Signature")
    
    # --- IMAGES (Signature, Stamp, QR) ---
    try:
        if os.path.exists("signature.png"):
            # Adjusted position to sit on the line
            c.drawImage("signature.png", width-280, footer_y, width=160, height=60, mask='auto')
            
        if os.path.exists("stamp.png"):
            # Stamp centered at bottom
            c.drawImage("stamp.png", width/2 - 50, 40, width=100, height=100, mask='auto')
            
        # QR Code (Verification)
        verify_url = f"http://127.0.0.1:5000/verify/{attempt_id}"
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(verify_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#2C3E50", back_color="white")
        
        # Draw QR in bottom left corner
        c.drawImage(ImageReader(img._img), 70, 40, 60, 60)
        c.setFont(fonts["Sans"], 8)
        c.drawString(70, 30, "Scan to Verify")
        
    except Exception as e:
        print(f"Image Error: {e}")
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer