import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
import pytesseract
from pdf2image import convert_from_bytes

st.set_page_config(page_title="نظام جرد الإعاشة المطور", layout="wide")
st.title("📂 مستخرج بيانات فواتير الإعاشة المطور")

uploaded_files = st.file_uploader("(PDF) ارفع فواتيرك", type="pdf", accept_multiple_files=True)

def extract_text_normal(uploaded_file):
    text_full = ""
    uploaded_file.seek(0)
    with pdfplumber.open(uploaded_file) as pdf:
        for p in pdf.pages:
            text_full += (p.extract_text() or "") + "\n"
    return text_full

def extract_text_with_ocr(uploaded_file):
    uploaded_file.seek(0)
    images = convert_from_bytes(uploaded_file.read())
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img, lang="eng") + "\n"
    return text

def detect_vendor(text):
    if "الخامة" in text or "Raw Material" in text:
        return "شركة الخامة الأولية"
    return "مورد غير معروف"

def normalize_digits(text):
    arabic_to_english = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    return text.translate(arabic_to_english)

if uploaded_files:
    all_data = []

    for uploaded_file in uploaded_files:
        text_full = extract_text_normal(uploaded_file)

        if len(text_full.strip()) < 30:
            try:
                text_full = extract_text_with_ocr(uploaded_file)
            except Exception as e:
                st.error(f"تعذر تشغيل OCR على الملف {uploaded_file.name}: {e}")
                continue

        text_full = normalize_digits(text_full)
        vendor = detect_vendor(text_full)
        lines = text_full.splitlines()

        for line in lines:
            line = normalize_digits(line.strip())
            parts = line.split()

            if len(parts) < 4:
                continue

            if not parts[0].isdigit():
                continue

            nums = [p for p in parts if re.fullmatch(r"\d+(?:\.\d+)?", p)]

            if len(nums) < 3:
                continue

            item_no = parts[0]
            qty = nums[-2]
            price = nums[-1]
            desc = " ".join(parts[1:-2]).strip()

            all_data.append({
                "المورد": vendor,
                "رقم الصنف": item_no,
                "البيان": desc if desc else "صنف غير معروف",
                "الكمية": qty,
                "السعر": price
            })

    if all_data:
        df = pd.DataFrame(all_data)
        st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
        st.dataframe(df, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)

        st.download_button(
            "📥 تحميل ملف الإكسل الموحد",
            data=output.getvalue(),
            file_name="Invoices.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("❌ لم نتمكن من العثور على بيانات. الملف غالبًا صورة ممسوحة ويحتاج OCR مضبوط.")
