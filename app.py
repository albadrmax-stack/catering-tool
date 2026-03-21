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
    st.error("❌ لم يتم العثور على المفتاح السري.")
    st.stop()

uploaded_files = st.file_uploader("ارفع فواتيرك (PDF أو صور)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    with st.spinner("جاري الاتصال بجوجل لفحص المحركات المتاحة لمفتاحك... 🔍"):
        try:
            # الكود يسأل جوجل عن الموديلات المتاحة أوتوماتيكياً
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            # يبحث عن أفضل موديل يدعم الصور
            target_model = None
            for m in available_models:
                if "1.5" in m or "vision" in m:
                    target_model = m
                    break
            
            # إذا لم يجد، يختار أول موديل متاح
            if not target_model and available_models:
                target_model = available_models[0]
                
        except Exception as e:
            st.error(f"حدث خطأ أثناء الاتصال بجوجل: {e}")
            st.stop()

    if target_model:
        st.success(f"✅ تم الاتصال! يتم الآن استخدام المحرك السري: {target_model}")
        model = genai.GenerativeModel(target_model)
        
        for uploaded_file in uploaded_files:
            with st.spinner(f'جاري قراءة وتحليل {uploaded_file.name} بدقة عالية...'):
                try:
                    if uploaded_file.type == "application/pdf":
                        images = pdf2image.convert_from_bytes(uploaded_file.read())
                        img = images[0]
                    else:
                        img = Image.open(uploaded_file)

                    prompt = """
                    أنت خبير في قراءة الفواتير العربية. 
                    حلل هذه الصورة واستخرج جدولاً يحتوي على الأعمدة التالية فقط:
                    (رقم الصنف، البيان، الوحدة، الكمية، السعر).
                    أريد النتيجة كجدول Markdown نصي فقط.
                    """
                    
                    response = model.generate_content([prompt, img])
                    
                    st.markdown(f"### بيانات الفاتورة: {uploaded_file.name}")
                    st.markdown(response.text)
                    
                except Exception as e:
                    st.error(f"⚠️ حدث خطأ أثناء قراءة الصورة: {str(e)}")
                    # كشاف لكشف الموديلات لو حدث خطأ
                    with st.expander("🔍 اضغط هنا لكشف تفاصيل حسابك في جوجل"):
                        st.write("الموديلات التي منحتها جوجل لمفتاحك هي:")
                        st.write(available_models)
    else:
        st.error("❌ لم نتمكن من العثور على محرك مناسب في حسابك.")
