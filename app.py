import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image

# إعداد واجهة البرنامج
st.set_page_config(page_title="مستخرج فواتير الإعاشة الذكي", layout="wide")
st.title("🤖 مستخرج الفواتير المطور (بذكاء Gemini)")

# جلب المفتاح السري من الخزنة
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("❌ لم يتم العثور على المفتاح السري في الإعدادات.")
    st.stop()

uploaded_files = st.file_uploader("ارفع فواتيرك (PDF أو صور)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    for uploaded_file in uploaded_files:
        with st.spinner(f'جاري تحليل {uploaded_file.name} باستخدام الذكاء الاصطناعي...'):
            # تحويل الملف إلى صورة ليفهمها Gemini
            if uploaded_file.type == "application/pdf":
                images = pdf2image.convert_from_bytes(uploaded_file.read())
                img = images[0] # نأخذ الصفحة الأولى
            else:
                img = Image.open(uploaded_file)

            # الطلب من الذكاء الاصطناعي
            prompt = """
            حلل صورة الفاتورة هذه واستخرج الأصناف في جدول يحتوي على الأعمدة التالية بالترتيب:
            (رقم الصنف، البيان، الوحدة، الكمية، السعر).
            أريد النتيجة كجدول نصي فقط (Markdown Table).
            """
            
            response = model.generate_content([prompt, img])
            
            # عرض النتيجة
            st.markdown(f"### بيانات الفاتورة: {uploaded_file.name}")
            st.markdown(response.text)

    st.success("✅ تمت العملية بنجاح!")
    st.info("💡 يمكنك الآن نسخ الجدول مباشرة إلى ملف الإكسل الخاص بك.")
