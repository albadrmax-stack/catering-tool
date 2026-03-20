import streamlit as st
import pandas as pd
import pdfplumber
import io
import re

st.set_page_config(page_title="مستخرج فواتير الخامة الأولية", layout="wide")
st.title("📂 نظام استخراج بيانات فواتير الإعاشة المطور")

uploaded_files = st.file_uploader("ارفع فواتيرك هنا (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            # استخراج اسم العميل (أزواد مثلاً)
            full_text = ""
            for p in pdf.pages:
                full_text += p.extract_text() or ""
            
            # محاولة العثور على اسم المورد (شركة الخامة الأولية)
            vendor_match = re.search(r"شركة\s+(.+?)\s+للتجارة", full_text)
            vendor = vendor_match.group(0) if vendor_match else "شركة الخامة الأولية"

            for page in pdf.pages:
                rows = page.extract_text().split('\n')
                for row in rows:
                    # نمط للبحث عن الأسطر التي تبدأ برقم صنف وتتبعها بيانات
                    # مثل: 00098 ورق عنب محشي ... كرتون 50 115.0
                    match = re.search(r"(\d{5})\s+(.*?)\s+(كرتون|كيلو|حبة|تلك|ربطة)\s+(\d+)\s+([\d\.]+)", row)
                    if match:
                        item_no = match.group(1)
                        desc = match.group(2)
                        unit = match.group(3)
                        qty = match.group(4)
                        price = match.group(5)
                        all_data.append([vendor, item_no, desc, unit, qty, price])

    if all_data:
        df = pd.DataFrame(all_data, columns=["المورد", "رقم الصنف", "البيان", "الوحدة", "الكمية", "السعر"])
        st.success(f"✅ تم استخراج {len(all_data)} أصناف بنجاح!")
        st.dataframe(df, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 تحميل ملف Excel الموحد", output.getvalue(), "Invoices_Report.xlsx")
    else:
        st.warning("⚠️ لم يتم العثory على بيانات متوافقة. تأكد من جودة ملف الـ PDF.")
