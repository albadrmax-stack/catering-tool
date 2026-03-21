import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json
import requests
import re

# دالة ضغط الصور
def compress_image(image_bytes, quality=80):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality)
    return output.getvalue()

# إعداد الصفحة
st.set_page_config(page_title="أداة شركة أزواد الذكية", layout="wide")

st.markdown("""
    <style>
    .title-red { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; text-align: center; }
    .subtitle-gray { color: #6b7280; font-size: 1.2rem; text-align: center; margin-bottom: 20px; }
    [data-testid="stFileUploadDropzone"] div div::before { content: "اسحب ملفات الفواتير هنا للتحليل الشامل" !important; font-weight: bold; }
    div[data-testid="stRadio"] div[role="radiogroup"] { justify-content: center !important; }
    .stCheckbox { text-align: right; direction: rtl; }
    </style>
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">نظام تحليل الفواتير المجمع - التحكم الكامل في التصدير</div>
""", unsafe_allow_html=True)

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ خطأ في المفتاح السري.")
    st.stop()

selection = st.radio("", ["ارفع ملف / ملفات", "التقاط صورة / صور"], horizontal=True, label_visibility="collapsed")

uploaded_files = []
if selection == "ارفع ملف / ملفات":
    files = st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    if files: uploaded_files = files
else:
    cam = st.camera_input("")
    if cam: uploaded_files = [cam]

if uploaded_files:
    # --- المعالجة الذكية فور الرفع ---
    with st.spinner("جاري قراءة الفاتورة الأصلية وتوليد البيانات الذكية..."):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in available_models if "1.5" in m or "flash" in m), available_models[0])
            model = genai.GenerativeModel(target_model)
            
            all_extracted_data = []
            
            for f in uploaded_files:
                f_content = f.read()
                if f.type == "application/pdf":
                    pdf_imgs = pdf2image.convert_from_bytes(f_content)
                    buf = io.BytesIO(); pdf_imgs[0].save(buf, format='PNG')
                    payload = buf.getvalue()
                else:
                    payload = compress_image(f_content)

                prompt = """
                أنت خبير تدقيق مالي. حلل الصورة واستخرج البيانات في JSON يحتوي على قائمة 'الأصناف'.
                أريد البيانات التالية لكل صنف:
                1. 'المورد': اسم الشركة.
                2. 'رقم_الصنف_الأصلي': كما هو في الفاتورة.
                3. 'البيان_الأصلي': الوصف الكامل كما ورد.
                4. 'المادة_صافي': اسم المنتج بدون أرقام أو أوزان.
                5. 'التصنيف': (غذائية، منظفات، بلاستيك، إلخ).
                6. 'الوحدة_الأصلية': (كرتون، كيس، كيلو).
                7. 'الوحدة_الصغيرة': (جرام، لتر، حبة).
                8. 'وزن_الحبة': رقم فقط.
                9. 'معامل_التحويل': كم حبة في الكرتون.
                10. 'الكمية_الأصلية': الكمية المكتوبة.
                11. 'السعر_الإفرادي': قبل الضريبة.
                12. 'الضريبة': قيمة الضريبة إن وجدت.
                13. 'الإجمالي_الصافي': السعر الكلي قبل الضريبة.
                """
                
                response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                data = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                items = data if isinstance(data, list) else data.get('الأصناف', [])
                all_extracted_data.extend(items)

            if all_extracted_data:
                df_full = pd.DataFrame(all_extracted_data)
                
                # تعريب أسماء الأعمدة للعرض والاختيار
                col_translation = {
                    'المورد': 'اسم المورد', 'رقم_الصنف_الأصلي': 'رقم الصنف', 'البيان_الأصلي': 'البيان (كما ورد)',
                    'المادة_صافي': 'المادة (صافي)', 'التصنيف': 'التصنيف الذكي', 'الوحدة_الأصلية': 'الوحدة الكبيرة',
                    'الوحدة_الصغيرة': 'الوحدة الصغيرة', 'وزن_الحبة': 'وزن الحبة', 'معامل_التحويل': 'معامل التحويل',
                    'الكمية_الأصلية': 'الكمية', 'السعر_الإفرادي': 'السعر الإفرادي', 'الضريبة': 'الضريبة',
                    'الإجمالي_الصافي': 'الإجمالي الصافي'
                }
                df_full.rename(columns=col_translation, inplace=True)

                # --- لوحة التحكم في الأعمدة ---
                st.markdown("---")
                st.markdown("### ⚙️ تخصيص أعمدة ملف الإكسل")
                st.info("قم باختيار الأعمدة التي تريد تضمينها في الملف النهائي:")
                
                all_cols = list(df_full.columns)
                # الأعمدة المختارة افتراضياً
                default_cols = ['اسم المورد', 'رقم الصنف', 'المادة (صافي)', 'التصنيف الذكي', 'الكمية', 'السعر الإفرادي', 'الإجمالي الصافي']
                
                cols_to_show = []
                # عرض مربعات الاختيار في 4 أعمدة لتوفير المساحة
                check_cols = st.columns(4)
                for i, col in enumerate(all_cols):
                    is_default = col in default_cols
                    if check_cols[i % 4].checkbox(col, value=is_default, key=col):
                        cols_to_show.append(col)

                if cols_to_show:
                    df_final = df_full[cols_to_show]
                    st.markdown("### 📊 معاينة الكشف المخصص")
                    st.dataframe(df_final, use_container_width=True)

                    # تصدير الإكسل المخصص
                    excel_io = io.BytesIO()
                    with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False, sheet_name='أزواد الذكية')
                        writer.sheets['أزواد الذكية'].right_to_left()
                    
                    st.download_button(
                        label="📥 تحميل الإكسل بالأعمدة المختارة",
                        data=excel_io.getvalue(),
                        file_name="AZWAD_CUSTOM_REPORT.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                else:
                    st.warning("⚠️ الرجاء اختيار عمود واحد على الأقل للتصدير.")
                    
        except Exception as e:
            st.error(f"حدث خطأ أثناء المعالجة: {e}")
