# -*- coding: utf-8 -*-
"""
Generate cybersecurity PDF test documents
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUTPUT_DIR = 'test_documents'
os.makedirs(OUTPUT_DIR, exist_ok=True)

try:
    pdfmetrics.registerFont(TTFont('SimHei', 'C:/Windows/Fonts/simhei.ttf'))
    FONT_NAME = 'SimHei'
except:
    FONT_NAME = 'Helvetica'

def create_styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontName=FONT_NAME, fontSize=24, textColor=HexColor('#10b981'), spaceAfter=30)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading1'], fontName=FONT_NAME, fontSize=16, textColor=HexColor('#303133'), spaceBefore=20, spaceAfter=12)
    body_style = ParagraphStyle('CustomBody', parent=styles['Normal'], fontName=FONT_NAME, fontSize=11, leading=18, spaceAfter=12)
    return title_style, heading_style, body_style

def make_pdf(filename, title, sections):
    title_style, heading_style, body_style = create_styles()
    doc = SimpleDocTemplate(os.path.join(OUTPUT_DIR, filename), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    content = [Paragraph(title, title_style), Spacer(1, 0.5*cm)]
    for section in sections:
        if isinstance(section, tuple):
            content.append(Paragraph(section[0], heading_style))
            content.append(Paragraph(section[1], body_style))
        else:
            content.append(Paragraph(section, body_style))
    doc.build(content)
    print('Created:', OUTPUT_DIR + '/' + filename)

def main():
    # SQL Injection PDF
    make_pdf('SQL Injection Guide.pdf', 'SQL Injection Protection Guide', [
        ('Overview', 'SQL Injection is a code injection technique where attackers insert malicious SQL statements into application inputs to manipulate the database. It is one of the most common and dangerous web security vulnerabilities.'),
        ('Common Types', 'Error-based SQL injection, Union query injection, Boolean-based blind injection, Time-based blind injection, Stacked queries injection.'),
        ('Protection Measures', '1. Use parameterized queries 2. Use ORM frameworks 3. Input validation 4. Least privilege principle 5. Proper error handling'),
        ('Python Example', 'Wrong: query = f"SELECT * FROM users WHERE name = "{name}"\nCorrect: cursor.execute("SELECT * FROM users WHERE name = %s", (name,))'),
    ])

    # XSS PDF
    make_pdf('XSS Attack Guide.pdf', 'XSS Cross-Site Scripting Guide', [
        ('What is XSS', 'Cross-Site Scripting (XSS) is a code injection attack where attackers inject malicious scripts into web pages. When users view the page, the embedded code executes in their browser.'),
        ('Types', 'Stored XSS: malicious code stored permanently on server. Reflected XSS: code in request parameters. DOM-based XSS: executes entirely on client side.'),
        ('Protection', '1. Input validation 2. Output encoding 3. HttpOnly and Secure flags 4. Content Security Policy (CSP) 5. Use modern frameworks'),
    ])

    # CSRF PDF
    make_pdf('CSRF Attack Guide.pdf', 'CSRF Attack and Protection', [
        ('Concept', 'Cross-Site Request Forgery (CSRF) forces authenticated users to perform unintended actions. Attackers exploit the user\'s authenticated session without their knowledge.'),
        ('Protection', '1. CSRF Token 2. SameSite Cookie 3. Referer validation 4. Double submit cookie 5. CAPTCHA for sensitive operations'),
    ])

    # Cryptography PDF
    make_pdf('Cryptography Basics.pdf', 'Cryptography Basics and Applications', [
        ('Symmetric Encryption', 'Uses same key for encryption and decryption. Common algorithms: AES (most widely used), DES (insecure), 3DES. AES features 128-bit block size with key lengths of 128/192/256 bits.'),
        ('Asymmetric Encryption', 'Uses public key and private key. RSA: based on integer factorization, typically 2048+ bits. ECC: elliptic curve cryptography with shorter keys.'),
        ('Hash Functions', 'Maps arbitrary length data to fixed-length hash. Common: SHA-256, SHA-384, SHA-512. MD5 and SHA-1 are insecure.'),
    ])

    # WebShell PDF
    make_pdf('WebShell Guide.pdf', 'WebShell Detection and Prevention', [
        ('What is WebShell', 'Malicious script uploaded to server through web vulnerabilities, giving attackers remote control capability. Common formats: ASP, ASPX, PHP, JSP, CGI.'),
        ('Detection', '1. File content signature scanning 2. Access behavior analysis 3. Network traffic monitoring 4. System call monitoring 5. Regular security scanning'),
        ('Prevention', '1. Strict file upload validation 2. Disable script execution in upload directories 3. Regular security scanning 4. Deploy WAF 5. Keep software updated'),
    ])

    print('\nAll PDF documents generated successfully!')

if __name__ == '__main__':
    main()
