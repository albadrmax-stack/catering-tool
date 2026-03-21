import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json

st.set_page_config(page_title="أداة أزواد الذكية لمسح المستندات والصور وتحويلها اكسل", layout="wide")
st.title("أداة أزواد الذكية لمسح المستندات والصور وتحويلها اكسل")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("❌ لم يتم العثور على المفتاح السري.")
    st.stop()

uploaded_files = st.file_uploader("ارفع فواتيرك (PDF أو صور)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    with st.spinner("جاري الاتصال بجوجل وفحص المحركات... 🔍"):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = None
            for m in available_models:
                if "1.5" in m or "vision" in m:
                    target_model = m
                    break
            if not target_model and available_models:
                target_model = available_models[0]
        except Exception as e:
            st.error(f"حدث خطأ أثناء الاتصال بجوجل: {e}")
            st.stop()

    if target_model:
        model = genai.GenerativeModel(target_model)
        
        all_invoices_data = []
        
        for uploaded_file in uploaded_files:
            with st.spinner(f'جاري قراءة وتحليل فاتورة: {uploaded_file.name}...'):
                try:
                    if uploaded_file.type == "application/pdf":
                        images = pdf2image.convert_from_bytes(uploaded_file.read())
                        img = images[0]
                    else:
                        img = Image.open(uploaded_file)

                    # تم تعديل الطلب لفصل (الوحدة) عن (الرقم) بذكاء
                    prompt = """
                    أنت خبير في قراءة وتحليل فواتير الإعاشة العربية.
                    حلل صورة الفاتورة بدقة، واستخرج 'اسم المورد' (اسم الشركة البائعة من أعلى الفاتورة).
                    استخرج الأصناف في تنسيق JSON دقيق يحتوي على قائمة 'الأصناف'، وكل صنف يجب أن يحتوي على الحقول التالية:
                    'اسم_المورد' (اكتب اسم الشركة التي استخرجتها هنا ليتكرر مع كل صنف)
                    'رقم_الصنف'
                    'المادة' (اسم المنتج، مثلاً 'ورق عنب')
                    'الوحدة_الصغيرة' (استخرج النص فقط: مثلاً 'كيلو'، 'جرام'، 'لتر'، 'حبة')
                    'وزن_الحبة' (استخرج الرقم فقط: مثلاً '2'، '125'، '2500')
                    'معامل_التحويل_في_الكرتون' (مثلاً '6')
                    'الوحدة_الرئيسية' (مثلاً 'كرتون' أو 'كيس')
                    'الكمية_بالفاتورة'
                    'السعر'

                    أر
