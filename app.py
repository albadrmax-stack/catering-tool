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
            
            # تحديد اسم المورد [cite: 1]
            vendor = "شركة الخامة الأولية" if "الخامة" in text_full else "مورد غير معروف"

            for page in pdf.pages:
                lines = page.extract_text().split('\n')
                for line in lines:
                    # البحث عن أي سطر يبدأ برقم صنف (مثل 00098) 
                    parts = line.split()
                    if len(parts) >= 4 and parts[0].isdigit() and len(parts[0]) >= 3:
                        # استخراج البيانات بناءً على موقعها في السطر
                        item_no = parts[0] # رقم الصنف 
                        qty = parts[-2] if parts[-2].replace('.', '').isdigit() else "0" # الكمية 
                        price = parts[-1] if parts[-1].replace('.', '').isdigit() else "0" # السعر 
                        
                        # تجميع اسم الصنف من الكلمات الموجودة في الوسط
                        desc = " ".join(parts[1:-3]) if len(parts) > 4 else "صنف غير معروف"
                        unit = parts[-3] if len(parts) > 3 else "وحدة" # الوحدة 
                        
                        all_data.append({
                            "المورد": vendor,
                            "رقم الصنف": item_no,
                            "البيان": desc,
                            "الوحدة": unit,
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
        st.download_button("📥 تحميل ملف الإكسل الموحد", output.getvalue(), "Invoices.xlsx")
    else:
        st.error("❌ لم نتمكن من العثور على بيانات. تأكد أن الملف أصلي وليس 'صورة باهتة'.")
