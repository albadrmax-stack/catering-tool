import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json

# دالة لتصغير حجم الصورة مع الحفاظ على الجودة
def compress_image(image_bytes, quality=70):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality)
    return output.getvalue()

st.set_page_config(page_title="أداة أزواد الذكية لمسح المستندات والصور وتحويلها اكسل", layout="wide")
st.title("أداة أزواد الذكية لمسح المستندات والصور وتحويلها اكسل")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("❌ لم يتم العثور على المفتاح السري.")
    st.stop()

# --- تنسيق الأزرار العربية الملونة عبر CSS ---
st.markdown("""
<style>
    div[data-testid="stRadio"] > label {
        font-size: 1.5rem !important;
        font-weight: bold !important;
        margin-bottom: 15px !important;
    }
    /* تنسيق الخيارات لتشبه الأزرار الكبيرة */
    div[data-testid="stRadio"] div[role="radiogroup"] {
        flex-direction: row !important;
        gap: 20px !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #f0f2f6;
        padding: 20px 40px !important;
        border-radius: 15px !important;
        border: 2px solid #d1d5db !important;
        cursor: pointer !important;
        transition: 0.3s !important;
    }
    /* اللون الأحمر لخيار الرفع */
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(1) {
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
    }
    /* اللون الكحلي لخيار الالتقاط */
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(2) {
        border-color: #1a2a40 !important;
        color: #1a2a40 !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("### ✨ خيارات الرفع (اختر واحداً للبدء):")

# استخدام الراديو بدلاً من pills لضمان التوافق
selection = st.radio(
    "اختر طريقة الرفع:",
    ["ارفع الملف / الملفات", "التقاط صورة / صور"],
    horizontal=True,
    label_visibility="collapsed"
)

uploaded_files = []

if selection == "ارفع الملف / الملفات":
    file_uploads = st.file_uploader("قم بسحب الملفات هنا", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    if file_uploads:
        uploaded_files.extend(file_uploads)

elif selection == "التقاط صورة / صور":
    # الكاميرا لا تعمل تلقائياً، تظهر فقط عند اختيار هذا الخيار
    camera_captures = st.camera_input("وجه الكاميرا نحو الفاتورة والتقط الصورة")
    if camera_captures:
        uploaded_files.append(camera_captures)

if uploaded_files:
    with st.spinner("جاري الاتصال بجوجل وفحص المحركات... 🔍"):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in available_models if "1.5" in m or "vision" in m), available_models[0])
            model = genai.GenerativeModel(target_model)
        except Exception as e:
            st.error(f"حدث خطأ أثناء الاتصال بجوجل: {e}")
            st.stop()

        all_invoices_data = []
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name if hasattr(uploaded_file, 'name') else "صورة_ملتقطة.jpg"
            with st.spinner(f'جاري معالجة وتحليل فاتورة: {file_name}...'):
                try:
                    file_content = uploaded_file.read()
                    if uploaded_file.type == "application/pdf":
                        images = pdf2image.convert_from_bytes(file_content)
                        img_bytes = io.BytesIO()
                        images[0].save(img_bytes, format='PNG')
                        img_to_send = img_bytes.getvalue()
                    else:
                        st.info(f"تنبيه: حجم الملف: {len(file_content)/1024/1024:.2f} ميجا. جاري التصغير...")
                        img_to_send = compress_image(file_content)

                    prompt = """
                    أنت خبير في قراءة وتحليل فواتير الإعاشة العربية.
                    حلل صورة الفاتورة بدقة، واستخرج 'اسم المورد'.
                    استخرج الأصناف في تنسيق JSON يحتوي على قائمة 'الأصناف'، وكل صنف يحتوي على الحقول:
                    'اسم_المورد'، 'رقم_الصنف'، 'المادة'، 'الوحدة_الصغيرة' (مثلاً كيلو)، 'وزن_الحبة' (رقم فقط)، 
                    'معامل_التحويل_في_الكرتون'، 'الوحدة_الرئيسية'، 'الكمية_بالفاتورة'، 'السعر'.
                    أريد JSON خام فقط بدون مقدمات.
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_to_send}])
                    cleaned_json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
                    data_json = json.loads(cleaned_json_text)
                    
                    if 'الأصناف' in data_json:
                        all_invoices_data.extend(data_json['الأصناف'])
                    
                except Exception as e:
                    st.error(f"⚠️ خطأ في معالجة {file_name}: {str(e)}")

        if all_invoices_data:
            df = pd.DataFrame(all_invoices_data)
            excel_columns_map = {
                'اسم_المورد': 'اسم المورد', 'رقم_الصنف': 'رقم الصنف', 'المادة': 'المادة/اسم المنتج',
                'الوحدة_الصغيرة': 'الوحدة', 'وزن_الحبة': 'وزن الحبة', 'معامل_التحويل_في_الكرتون': 'معامل التحويل (حبة/كرتون)',
                'الوحدة_الرئيسية': 'الوحدة الكبيرة', 'الكمية_بالفاتورة': 'الكمية (بالكرتون)', 'السعر': 'السعر الإجمالي'
            }
            df.rename(columns=excel_columns_map, inplace=True)
            cols_order = ['اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة', 'وزن الحبة', 'معامل التحويل (حبة/كرتون)', 'الوحدة الكبيرة', 'الكمية (بالكرتون)', 'السعر الإجمالي']
            df = df[[c for c in cols_order if c in df.columns]]
            
            st.dataframe(df, use_container_width=True)
            
            excel_io = io.BytesIO()
            with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='فواتير_أزواد')
                writer.sheets['فواتير_أزواد'].right_to_left()
            
            st.download_button(label="تحميل اكسل", data=excel_io.getvalue(), file_name="فواتير_أزواد_المجمعة.xlsx", mime="application/vnd.ms-excel")
