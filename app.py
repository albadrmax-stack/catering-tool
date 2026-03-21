import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
from pdf2image import convert_from_bytes
import pytesseract

st.set_page_config(page_title="نظام جرد الإعاشة المطور", layout="wide")
st.title("📂 مستخرج فواتير الإعاشة (محرك قراءة الصور OCR)")

uploaded_files = st.file_uploader("(PDF) ارفع فواتيرك هنا", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    debug_text = ""
    
    for file in uploaded_files:
        file_bytes = file.read()
        
        # الخطوة 1: محاولة القراءة كملف إلكتروني أولاً
        text_full = ""
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text_full += page.extract_text() or ""
        
        # الخطوة 2: إذا كان النص فارغاً (يعني الملف صورة/سكانر)، نشغل محرك الذكاء الاصطناعي
        if not text_full.strip():
            st.info("⚠️ يبدو أن الملف عبارة عن 'صورة'. جاري تشغيل محرك قراءة الصور (OCR)، قد يستغرق ثواني...")
            try:
                # تحويل الـ PDF إلى صور
                images = convert_from_bytes(file_bytes)
                for img in images:
                    # استخراج النص العربي من الصورة
                    text = pytesseract.image_to_string(img, lang='ara')
                    text_full += text + "\n"
            except Exception as e:
                st.error("حدث خطأ في محرك الصور. تأكد من اكتمال التحديثات.")
        
        debug_text += text_full
        flat_text = text_full.replace('\n', '  ')
        vendor = "شركة الخامة الأولية" if "الخامة" in text_full else "مورد غير معروف"
        
        # البحث عن الأنماط داخل النص (سواء كان إلكتروني أو مستخرج من الصورة)
        pattern1 = re.findall(r'([\d\.,]+)\s+(\d+)\s+(كرتون|كيلو|تلك|حبة|باكيت|مليح|جرام)\s+(.*?)\s+(00\d{3})', flat_text)
        pattern2 = re.findall(r'(00\d{3})\s+(.*?)\s+(كرتون|كيلو|تلك|حبة|باكيت|مليح|جرام)\s+(\d+)\s+([\d\.,]+)', flat_text)
        
        if pattern1:
            for p in pattern1:
                all_data.append({"المورد": vendor, "رقم الصنف": p[4], "البيان": p[3].strip(), "الوحدة": p[2], "الكمية": p[1], "السعر": p[0]})
        elif pattern2:
            for p in pattern2:
                all_data.append({"المورد": vendor, "رقم الصنف": p[0], "البيان": p[1].strip(), "الوحدة": p[2], "الكمية": p[3], "السعر": p[4]})

    if all_data:
        df = pd.DataFrame(all_data)
        st.success(f"✅ نجاح! تم استخراج {len(df)} صنف.")
        st.dataframe(df, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 تحميل الإكسل", output.getvalue(), "Invoices_OCR.xlsx")
    else:
        st.error("❌ لم نتمكن من استخراج الأصناف. (تأكد من وضوح الصورة)")
        with st.expander("🔍 كشاف الأعطال (اضغط هنا وصور لي النتيجة)"):
            st.text_area("ما قرأه محرك الذكاء الاصطناعي من الصورة:", debug_text, height=300)
