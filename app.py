import streamlit as st
import pandas as pd
import pdfplumber
import io
import re

st.set_page_config(page_title="نظام جرد الإعاشة المطور", layout="wide")
st.title("📂 مستخرج بيانات فواتير الإعاشة المطور")

uploaded_files = st.file_uploader("(PDF) ارفع فواتيرك", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for uploaded_file in uploaded_files:
        with pdfplumber.open(uploaded_file) as pdf:
            text_full = ""
            for p in pdf.pages:
                text_full += p.extract_text() or ""
            
            # تحديد اسم المورد
            vendor = "شركة الخامة الأولية" if "الخامة" in text_full else "مورد غير معروف"

            for page in pdf.pages:
                lines = page.extract_text().split('\n')
                for line in lines:
                    # البحث عن (رقم الصنف + البيان + الوحدة + الكمية + السعر)
                    match = re.search(r'(\d{5})\s+(.*?)\s+(كرتون|كيلو|تلك|حبة|باكيت)\s+(\d+)\s+([\d\.,]+)', line)
                    if match:
                        all_data.append({
                            "المورد": vendor,
                            "رقم الصنف": match.group(1),
                            "البيان": match.group(2),
                            "الوحدة": match.group(3),
                            "الكمية": match.group(4),
                            "السعر": match.group(5)
                        })

    if all_data:
        df = pd.DataFrame(all_data)
        st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
        st.dataframe(df, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 تحميل ملف الإكسل الموحد", output.getvalue(), "Invoices.xlsx")
    else:
        st.error("❌ لم نتمكن من قراءة البيانات. تأكد أن الملف أصلي وليس 'صورة باهتة' جداً.")
