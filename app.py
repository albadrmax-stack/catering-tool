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

# دالة استخراج معرف ملف درايف
def get_drive_file_id(url):
    pattern = r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)"
    match = re.search(pattern, url)
    return match.group(1) if match else None

# إعداد الصفحة والتنسيق البصري
st.set_page_config(page_title="أداة شركة أزواد الذكية", layout="wide")

st.markdown("""
    <style>
    .stApp { align-items: center; display: flex; justify-content: center; }
    .main .block-container { max-width: 1100px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.2rem; margin-bottom: 30px; }
    
    div[data-testid="stRadio"] div[role="radiogroup"] { justify-content: center !important; gap: 20px !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #ffffff; padding: 15px 25px !important; border-radius: 12px !important;
        border: 2px solid #e5e7eb !important; font-weight: bold !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(1) { border-color: #ff4b4b !important; color: #ff4b4b !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(2) { border-color: #1a2a40 !important; color: #1a2a40 !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(3) { border-color: #34a853 !important; color: #34a853 !important; }

    [data-testid="stFileUploadDropzone"] div div::before { content: "اسحب وأفلت الفواتير هنا" !important; font-weight: bold; }
    [data-testid="baseButton-secondary"]::after { content: "تصفح الملفات" !important; visibility: visible; display: block; }
    [data-testid="baseButton-secondary"] span { visibility: hidden; }
    
    .stCheckbox { text-align: right; direction: rtl; font-weight: bold; }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">تحليل شامل لجميع بيانات الفاتورة مع تحكم كامل في الأعمدة</div>
""", unsafe_allow_html=True)

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ تأكد من إعداد المفتاح السري في Secrets")
    st.stop()

selection = st.radio("طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"], horizontal=True, label_visibility="collapsed")

files_to_process = []
if selection == "ارفع ملف / ملفات":
    uploads = st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    if uploads:
        for f in uploads: files_to_process.append({"name": f.name, "content": f.read(), "type": f.type})
elif selection == "التقاط صورة / صور":
    camera_file = st.camera_input("")
    if camera_file: files_to_process.append({"name": "صورة_كاميرا.jpg", "content": camera_file.read(), "type": "image/jpeg"})
elif selection == "رابط قوقل درايف":
    drive_url = st.text_input("أدخل رابط قوقل درايف المباشر:")
    if drive_url:
        fid = get_drive_file_id(drive_url)
        if fid:
            d_url = f"https://docs.google.com/uc?export=download&id={fid}"
            with st.spinner("جاري جلب الملف..."):
                try:
                    res = requests.get(d_url)
                    if res.status_code == 200:
                        files_to_process.append({"name": "درايف_ملف.jpg", "content": res.content, "type": "image/jpeg"})
                except: st.error("تعذر الوصول")

if files_to_process:
    with st.spinner("جاري استخراج كافة بيانات الفاتورة..."):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in available_models if "1.5" in m or "flash" in m), available_models[0])
            model = genai.GenerativeModel(target_model)
            
            all_extracted_data = []
            for f_data in files_to_process:
                if "pdf" in f_data.get("type", ""):
                    imgs = pdf2image.convert_from_bytes(f_data["content"])
                    buf = io.BytesIO(); imgs[0].save(buf, format='PNG')
                    payload = buf.getvalue()
                else: payload = compress_image(f_data["content"])

                # طلب استخراج شامل لكل الأعمدة الممكنة
                prompt = """
                تحليل مالي شامل: استخرج كل البيانات المتاحة في الفاتورة في JSON يحتوي على قائمة 'الأصناف'.
                أريد استخراج البيانات التالية بدقة:
                1. اسم المورد
                2. رقم الصنف (كما ورد)
                3. المادة/اسم المنتج (اسم المنتج فقط بدون إضافات)
                4. البيان الأصلي (الوصف الكامل كما ورد في الفاتورة)
                5. التصنيف الذكي (غذائية، منظفات، إلخ)
                6. الوحدة الصغيرة (مثل جرام، كيلو)
                7. الكمية (بالوحدة الصغيرة)
                8. الوحدة الكبيرة (مثل كرتون، كيس)
                9. معامل التحويل (مثل حبة/كرتون)
                10. الكمية بالوحدة الكبيرة
                11. السعر الافرادي
                12. الضريبة
                13. الإجمالي الصافي
                """
                
                response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                data = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                items = data if isinstance(data, list) else data.get('الأصناف', [])
                all_extracted_data.extend(items)

            if all_extracted_data:
                df_full = pd.DataFrame(all_extracted_data)
                
                # توحيد مسميات الأعمدة لسهولة العرض والاختيار
                col_names = {
                    'اسم المورد': 'اسم المورد', 'رقم الصنف': 'رقم الصنف', 'المادة/اسم المنتج': 'المادة/اسم المنتج',
                    'البيان الأصلي': 'البيان (كما ورد)', 'التصنيف الذكي': 'التصنيف الذكي',
                    'الوحدة الصغيرة': 'الوحدة الصغيرة', 'الكمية': 'الكمية', 'الوحدة الكبيرة': 'الوحدة الكبيرة',
                    'معامل التحويل': 'معامل التحويل', 'الكمية بالوحدة الكبيرة': 'الكمية بالوحدة الكبيرة',
                    'السعر الافرادي': 'السعر الافرادي', 'الضريبة': 'الضريبة', 'الإجمالي الصافي': 'الإجمالي الصافي'
                }
                # محاولة مطابقة الأسماء المستخرجة مع القائمة المطلوبة
                df_full.columns = [col_names.get(c, c) for c in df_full.columns]

                st.markdown("---")
                st.markdown("### ⚙️ تخصيص أعمدة التصدير (الأعمدة الافتراضية مختارة ✅)")
                
                # هذه هي الأعمدة التسعة التي طلبتها في الصورة لتكون الافتراضية
                default_cols = [
                    'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 
                    'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي'
                ]
                
                all_cols = list(df_full.columns)
                cols_to_show = []
                check_cols_container = st.columns(3)
                
                for i, col in enumerate(all_cols):
                    is_checked = col in default_cols
                    if check_cols_container[i % 3].checkbox(col, value=is_checked, key=f"chk_{col}"):
                        cols_to_show.append(col)

                if cols_to_show:
                    # ترتيب الأعمدة المختارة ليكون الترتيب الأساسي كما في الصورة
                    final_order = [c for c in default_cols if c in cols_to_show] + [c for c in cols_to_show if c not in default_cols]
                    df_final = df_full[final_order]
                    
                    st.markdown("### 📊 معاينة الجدول النهائي")
                    st.dataframe(df_final, use_container_width=True)

                    excel_io = io.BytesIO()
                    with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False, sheet_name='أزواد')
                        writer.sheets['أزواد'].right_to_left()
                    
                    st.download_button(label="تحميل اكسل ⬇️", data=excel_io.getvalue(), file_name="AZWAD_FULL_REPORT.xlsx")
        except Exception as e:
            st.error(f"تنبيه: {e}")
