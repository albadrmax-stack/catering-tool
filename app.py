import streamlit as st
import pandas as pd
import pdfplumber
import io

st.set_page_config(page_title="نظام جرد الإعاشة الموحد", layout="wide")
st.title("📂 مستخرج بيانات فواتير الإعاشة الموحد")

uploaded_files = st.file_uploader("(PDF الأصلي) ارفع فواتيرك", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for uploaded_file in uploaded_files:
        with pdfplumber.open(uploaded_file) as pdf:
            # محاولة قراءة النص
            first_page_text = pdf.pages[0].extract_text()
            vendor = "مورد غير معروف"
            if first_page_text:
                vendor = first_page_text.split('\n')[0]
            
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    df_page = pd.DataFrame(table)
                    df_page.dropna(how='all', inplace=True)
                    for index, row in df_page.iterrows():
                        if any(row):
                            all_data.append([vendor] + list(row))

    if all_data:
        final_df = pd.DataFrame(all_data)
        st.success("✅ تم استخراج البيانات!")
        st.dataframe(final_df)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, header=False)
        st.download_button("📥 تحميل ملف الإكسل", output.getvalue(), "Invoices.xlsx")
    else:
        st.warning("⚠️ لم يتم العثور على جداول. تأكد أن الملف أصلي وليس صورة.")
