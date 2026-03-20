import streamlit as st
import pandas as pd
import pdfplumber
import io
import re

# OCR
import pytesseract
from PIL import Image
import pdf2image

st.set_page_config(page_title="نظام جرد الإعاشة المطور", layout="wide")
st.title("📂 مستخرج بيانات فواتير الإعاشة المطور")

uploaded_files = st.file_uploader("(PDF) ارفع فواتيرك", type="pdf", accept_multiple_files=True)

def extract_text_with_ocr(file):
    images = pdf2image.convert_from_bytes(file.read())
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img, lang='ara')
    return text

if uploaded_files:
    all_data = []

    for uploaded_file in uploaded_files:

        # أولاً نحاول قراءة النص العادي
        with pdfplumber.open(uploaded_file) as pdf:
            text_full = ""
            for p in pdf.pages:
                page_text = p.extract_text() or ""
                text_full += page_text + "\n"

        # إذا النص فاضي → نستخدم OCR
        if len(text_full.strip()) < 50:
            uploaded_file.seek(0)
            text_full = extract_text_with_ocr(uploaded_file)

        vendor = "شركة الخامة الأولية" if "الخامة" in text_full else "مورد غير معروف"

        lines = text_full.split("\n")

        for line in lines:
            parts = line.split()

            if len(parts) >= 3 and parts[0].isdigit():

                numbers = [x for x in parts if x.replace('.', '', 1).isdigit()]

                if len(numbers) >= 2:
                    item_no = parts[0]
                    qty = numbers[-2]
                    price = numbers[-1]

                    desc = " ".join(parts[1:-2]) if len(parts) > 3 else "صنف غير معروف"

                    all_data.append({
                        "المورد": vendor,
                        "رقم الصنف": item_no,
                        "البيان": desc,
                        "الكمية": qty,
                        "السعر": price
                    })

    if all_data:
        df = pd.DataFrame(all_data)
        st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
        st.dataframe(df, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)

        st.download_button(
            "📥 تحميل ملف الإكسل الموحد",
            output.getvalue(),
            "Invoices.xlsx"
        )
    else:
        st.error("❌ لم نتمكن من قراءة الفاتورة — غالباً تحتاج OCR أو تنسيق مختلف.")
