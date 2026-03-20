import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

# إعداد واجهة البرنامج
st.set_page_config(page_title="نظام جرد الإعاشة", layout="wide")
st.title("📂 مستخرج بيانات فواتير الإعاشة الموحد")

def parse_item_description(desc):
    # البحث عن نمط الضرب مثل 2*6 أو 2x6
    match = re.search(r'(\d+)\s*[\*xX×]\s*(\d+)', desc)
    qty_in_unit = "1"
    pack_size = "1"
    clean_name = desc
    
    if match:
        qty_in_unit = match.group(1)
        pack_size = match.group(2)
        clean_name = desc.split(match.group(0))[0].strip()
    return clean_name, qty_in_unit, pack_size

# رفع الملفات
uploaded_files = st.file_uploader("ارفع فواتيرك (PDF الأصلي)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_rows = []
    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            # استخراج اسم المورد من أول سطر
            first_page = pdf.pages[0].extract_text()
            vendor = first_page.split('\n')[0] if first_page else "مورد غير معروف"
            
            # استخراج الجداول
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    for row in table[1:]: # تخطي العنوان
                        if len(row) > 6 and row[6]: # التأكد أن سطر الصنف موجود
                            name, unit_q, pack = parse_item_description(row[6])
                            all_rows.append({
                                "اسم المورد": vendor,
                                "المادة": name,
                                "الوحدة": row[5],
                                "الكمية": row[4],
                                "سعر الوحدة": row[3],
                                "معامل التعبئة": pack,
                                "الوزن/العدد الداخلي": unit_q,
                                "الإجمالي": row[0]
                            })
    
    if all_rows:
        df = pd.DataFrame(all_rows)
        st.write("### البيانات المجمعة:")
        st.dataframe(df)
        
        # تحويل لإكسل
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        
        st.download_button("📥 تحميل ملف الإكسل الموحد", output.getvalue(), "Catering_Data.xlsx")