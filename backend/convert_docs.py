import os
import pypandoc
from docx2pdf import convert

MD_FILE = r"C:\Users\wisnu\.gemini\antigravity-ide\brain\b0138080-ecff-4eb2-9e84-2c92ff831753\manual_book.md"
DOCX_FILE = r"d:\Programer\Uang Pengiriman\Manual_Book_Uang_Pengiriman.docx"
PDF_FILE = r"d:\Programer\Uang Pengiriman\Manual_Book_Uang_Pengiriman.pdf"

with open(MD_FILE, "r", encoding="utf-8") as f:
    text = f.read()

print("Generating DOCX...")
# Generate DOCX
pypandoc.convert_text(text, "docx", format="md", outputfile=DOCX_FILE)
print("Generated DOCX at:", DOCX_FILE)

print("Generating PDF from DOCX...")
try:
    convert(DOCX_FILE, PDF_FILE)
    print("Generated PDF at:", PDF_FILE)
except Exception as e:
    print(f"Failed to generate PDF (Word might not be installed): {e}")
