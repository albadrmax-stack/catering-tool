import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image

st.set_page_config(page_title="مستخرج فواتير الإعاشة الذكي", layout="wide")
st.title("🤖 مستخرج الفواتير المطور (بذكاء Gemini)")

# جلب المفتاح السري
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("❌ لم يتم العثور على المفتاح السري في الإعدادات.")
    st.stop()

uploaded_files = st.file_uploader("ارفع فواتيرك (PDF أو صور)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    # تم استخدام المسمى الأكثر استقراراً هنا
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    for uploaded_file in uploaded_files:
        with st.spinner(f'جاري تحليل {uploaded_file.name} بدقة عالية...'):
            try:
                if uploaded_file.type == "application/pdf":
                    images = pdf2image.convert_from_bytes(uploaded_file.read())
                    img = images[0]
                else:
                    img = Image.open(uploaded_file)

                # تعليمات دقيقة جداً للذكاء الاصطناعي
                prompt = """
                أنت خبير في قراءة فواتير الإعاشة السعودية. 
                استخرج جدولاً دقيقاً يحتوي على:
                (رقم الصنف، البيان، الوحدة، الكمية، السعر).
                اجعل النتيجة كجدول Markdown فقط، بدون كلام جانبي.
                """
                
                response = model.generate_content([prompt, img])
                
                st.markdown(f"### بيانات الفاتورة: {uploaded_file.name}")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"⚠️ حدث تنبيه أثناء المعالجة: {str(e)}")
                st.info("تأكد من أن المفتاح السري (API Key) مفعل وصحيح في إعدادات Secrets.")

    st.success("✅ اكتملت العملية!")
