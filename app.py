import streamlit as st
import pandas as pd
import pdfplumber
import io
from paddleocr import PaddleOCR
import numpy as np
from PIL import Image

# إعداد محرك القراءة للصور
ocr = PaddleOCR(use_angle_cls=True, lang='ar')

st.set_page_config(page_title="نظام جرد الإعاشة المطور", layout="wide")
st.title("📂 مستخرج بيانات الفواتير الذكي")

uploaded_files = st.file_uploader("ارفع فواتيرك (PDF أو صور)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for uploaded_file in uploaded_files:
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                # محاولة 1: استخراج كجدول إلكتروني
                table = page.extract_table()
                if table:
                    df = pd.DataFrame(table)
                    all_data.append(df)
                else:
                    # محاولة 2: إذا لم يجد جدول (يعني صورة)، نستخدم الذكاء الاصطناعي
                    st.info(f"جاري تحليل الصفحة كصورة في: {uploaded_file.name}...")
                    img = page.to_image(resolution=300).original
                    result = ocr.ocr(np.array(img), cls=True)
                    if result and result[0]:
                        texts = [line[1][0] for line in result[0]]
                        all_data.append(pd.DataFrame(texts))

    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        st.success("✅ اكتمل التحليل!")
        st.dataframe(final_df)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False)
        st.download_button("📥 تحميل ملف الإكسل الموحد", output.getvalue(), "Invoices_Data.xlsx")
