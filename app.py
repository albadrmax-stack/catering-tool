import streamlit as st
import pandas as pd
import pdfplumber
import io
import re

st.set_page_config(page_title="نظام جرد الإعاشة المطور", layout="wide")
st.title("📂 مستخرج فواتير الإعاشة (النسخة الذكية)")

uploaded_files = st.file_uploader("(PDF) ارفع فواتيرك", type="pdf", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    debug_text = ""
    
    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                raw_text = page.extract_text() or ""
                # تخزين النص الخام لاكتشاف الأخطاء إن وجدت
                debug_text += raw_text + "\n\n---\n\n"
                
                # دمج كل الأسطر في سطر واحد لتجاوز مشكلة الفراغات المخفية في الفاتورة
                flat_text = raw_text.replace('\n', '  ')
                
                # البحث بالاتجاهين (لتغطية كل طرق قراءة الـ PDF العربية)
                # النمط 1: السعر ثم الكمية ثم الوحدة ثم البيان ثم رقم الصنف
                pattern1 = re.findall(r'([\d\.,]+)\s+(\d+)\s+(كرتون|كيلو|تلك|حبة|باكيت|مليح|جرام)\s+(.*?)\s+(00\d{3})', flat_text)
                
                # النمط 2: رقم الصنف ثم البيان ثم الوحدة ثم الكمية ثم السعر
                pattern2 = re.findall(r'(00\d{3})\s+(.*?)\s+(كرتون|كيلو|تلك|حبة|باكيت|مليح|جرام)\s+(\d+)\s+([\d\.,]+)', flat_text)
                
                if pattern1:
                    for p in pattern1:
                        all_data.append({"رقم الصنف": p[4], "البيان": p[3].strip(), "الوحدة": p[2], "الكمية": p[1], "السعر": p[0]})
                elif pattern2:
                    for p in pattern2:
                        all_data.append({"رقم الصنف": p[0], "البيان": p[1].strip(), "الوحدة": p[2], "الكمية": p[3], "السعر": p[4]})

    if all_data:
        df = pd.DataFrame(all_data)
        st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
        st.dataframe(df, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 تحميل الإكسل", output.getvalue(), "Invoices.xlsx")
    else:
        st.error("❌ لا يزال هناك اختلاف في تنسيق الفاتورة المخفي.")
        # كشاف الأعطال
        with st.expander("🔍 اضغط هنا لكشف المشكلة (أرسل لي صورة لهذه الشاشة)"):
            st.write("هذا النص هو ما يراه البرنامج داخل ملفك فعلياً. صوره لي لأكتب الكود بناءً على هذا النص:")
            st.text_area("", debug_text, height=300)
