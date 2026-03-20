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
            
            # تحديد اسم المورد من الفاتورة
            vendor = "شركة الخامة الأولية" if "الخامة" in text_full else "مورد غير معروف"

            for page in pdf.pages:
                lines = page.extract_text().split('\n')
                for line in lines:
                    # البحث عن نمط: (رقم صنف 5 أرقام) ثم (نص) ثم (وحدة) ثم (كمية)
                    # هذا النمط مرن جداً ليتناسب مع فاتورة "سوسن" و "باذنجان"
                    match = re.search(r'(\d{5})\s+(.*?)\s+(كرتون|كيلو|تلك|حبة|باكيت|مليح)\s+(\d+)', line)
                    if match:
                        # محاولة العثور على السعر في نهاية السطر
                        price_match = re.findall(r'[\d\.,]+', line)
                        price = price_match[-2] if len(price_match) >= 2 else "0"
                        
                        all_data.append({
                            "المورد": vendor,
                            "رقم الصنف": match.group(1),
                            "البيان": match.group(2),
                            "الوحدة": match.group(3),
                            "الكمية": match.group(4),
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
