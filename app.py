import streamlit as st
import pandas as pd
import pdfplumber
import io

st.set_page_config(page_title="نظام جرد الإعاشة الذكي", layout="wide")
st.title("📂 مستخرج بيانات فواتير الإعاشة المطور")

uploaded_files = st.file_uploader("ارفع فواتيرك (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_rows = []
    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                # هذا المحرك سيحاول استخراج النص حتى من الصور بجودة عالية
                text = page.extract_text(layout=True)
                if text:
                    lines = text.split('\n')
                    for line in lines:
                        # البحث عن الأنماط التي ظهرت في فاتورتك (رقم 5 خانات + نص + سعر)
                        import re
                        match = re.search(r'(\d{5})\s+(.*?)\s+(كرتون|كيلو|تلك|حبة)\s+(\d+)\s+([\d\.]+)', line)
                        if match:
                            all_rows.append({
                                "رقم الصنف": match.group(1),
                                "البيان": match.group(2),
                                "الوحدة": match.group(3),
                                "الكمية": match.group(4),
                                "السعر": match.group(5)
                            })

    if all_rows:
        df = pd.DataFrame(all_rows)
        st.success("✅ تم استخراج البيانات بنجاح!")
        st.dataframe(df, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 تحميل ملف إكسل الموحد", output.getvalue(), "Invoices_Data.xlsx")
    else:
        st.error("❌ لم نتمكن من قراءة البيانات. تأكد أن الملف ليس 'صورة باهتة' جداً.")
