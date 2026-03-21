import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image

st.set_page_config(page_title="مستخرج فواتير الإعاشة الذكي", layout="wide")
st.title("🤖 مستخرج الفواتير المطور (بذكاء Gemini)")

# جلب المفتاح السري من الإعدادات
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("❌ لم يتم العثور على المفتاح السري في إعدادات Secrets.")
    st.stop()

uploaded_files = st.file_uploader("ارفع فواتيرك (PDF أو صور)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    # استخدام الإصدار المستقر (stable) لضمان عدم حدوث خطأ 404
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    for uploaded_file in uploaded_files:
        with st.spinner(f'جاري تحليل {uploaded_file.name}...'):
            try:
                if uploaded_file.type == "application/pdf":
                    images = pdf2image.convert_from_bytes(uploaded_file.read())
                    img = images[0]
                else:
                    img = Image.open(uploaded_file)

                # طلب استخراج البيانات بوضوح
                prompt = """
                أنت خبير في قراءة الفواتير العربية. 
                حلل هذه الصورة واستخرج جدولاً يحتوي على الأعمدة التالية فقط:
                (رقم الصنف، البيان، الوحدة، الكمية، السعر).
                أريد النتيجة كجدول Markdown نصي فقط.
                """
                
                # إرسال الصورة للموديل
                response = model.generate_content([prompt, img])
                
                st.markdown(f"### بيانات الفاتورة: {uploaded_file.name}")
                if response.text:
                    st.markdown(response.text)
                else:
                    st.warning("⚠️ لم يستطع الذكاء الاصطناعي قراءة بيانات واضحة من هذه الصفحة.")
                
            except Exception as e:
                # هذا الجزء سيوضح لنا لو كان هناك مشكلة في المفتاح نفسه
                if "API_KEY_INVALID" in str(e):
                    st.error("❌ المفتاح السري (API Key) غير صحيح. تأكد من نسخه كاملاً في الإعدادات.")
                else:
                    st.error(f"⚠️ حدث خطأ أثناء المعالجة: {str(e)}")

    st.success("✅ تم الانتهاء.")
