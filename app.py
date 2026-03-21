import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json
import requests
import re

# إعداد الصفحة والتنسيق
st.set_page_config(page_title="أداة شركة أزواد الذكية", layout="wide")

st.markdown("""
    <style>
    .stApp { align-items: center; display: flex; justify-content: center; }
    .main .block-container { max-width: 1100px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.2rem; margin-bottom: 30px; }
    
    /* أزرار الاختيار */
    div[data-testid="stRadio"] div[role="radiogroup"] { justify-content: center !important; gap: 20px !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #ffffff; padding: 15px 25px !important; border-radius: 12px !important;
        border: 2px solid #e5e7eb !important; font-weight: bold !important;
    }
    
    .stButton > button {
        background-color: #ff4b4b !important; color: white !important;
        font-size: 1.3rem !important; padding: 10px !important;
        border-radius: 10px !important; width: 100% !important;
    }
    .stCheckbox { text-align: right; direction: rtl; font-weight: bold; }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">نظام التحليل المخصص والمستقر - حدد خياراتك ثم ابدأ</div>
""", unsafe_allow_html=True)

# دالة ضغط الصور
def compress_image(image_bytes, quality=80):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality)
    return output.getvalue()

# دالة استخراج معرف درايف
def get_drive_file_id(url):
    pattern = r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)"
    match = re.search(pattern, url)
    return match.group(1) if match else None

# إعداد الـ API
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ تأكد من إعداد المفتاح السري في Settings > Secrets")
    st.stop()

# --- نموذج الإدخال (Form) ---
with st.form("azwad_form"):
    selection = st.radio("اختر طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"], horizontal=True)
    
    uploaded_files_raw = None
    camera_raw = None
    drive_raw = ""
    
    if selection == "ارفع ملف / ملفات":
        uploaded_files_raw = st.file_uploader("قم بسحب الملفات هنا", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        camera_raw = st.camera_input("التقط صورة")
    elif selection == "رابط قوقل درايف":
        drive_raw = st.text_input("رابط قوقل درايف:")

    st.markdown("---")
    st.markdown("### ⚙️ اختر الأعمدة التي تريد استخراجها")
    
    all_cols = [
        'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 
        'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 
        'السعر الافرادي', 'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]
    
    default_on = [
        'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 
        'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي'
    ]
    
    selected_cols = []
    c1, c2, c3 = st.columns(3)
    for i, col in enumerate(all_cols):
        target_c = [c1, c2, c3][i % 3]
        if target_c.checkbox(col, value=(col in default_on), key=f"check_{i}"):
            selected_cols.append(col)

    submit = st.form_submit_button("🚀 ابدأ استخراج وتحليل البيانات")

# --- منطق المعالجة ---
if submit:
    files_to_process = []
    if selection == "ارفع ملف / ملفات" and uploaded_files_raw:
        for f in uploaded_files_raw: files_to_process.append({"name": f.name, "content": f.read(), "type": f.type})
    elif selection == "التقاط صورة / صور" and camera_raw:
        files_to_process.append({"name": "camera.jpg", "content": camera_raw.read(), "type": "image/jpeg"})
    elif selection == "رابط قوقل درايف" and drive_raw:
        fid = get_drive_file_id(drive_raw)
        if fid:
            r = requests.get(f"https://docs.google.com/uc?export=download&id={fid}")
            if r.status_code == 200: files_to_process.append({"name": "drive.jpg", "content": r.content, "type": "image/jpeg"})

    if not files_to_process:
        st.warning("⚠️ الرجاء تزويد النظام بملفات للتحليل.")
    else:
        with st.spinner("جاري الاتصال بالمحرك الذكي وتحليل البيانات..."):
            try:
                # --- آلية البحث التلقائي عن الموديل (لتجنب خطأ 404) ---
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target_m = next((m for m in models if "1.5" in m or "flash" in m), models[0])
                model = genai.GenerativeModel(target_m)
                
                final_results = []
                for file_item in files_to_process:
                    if "pdf" in file_item["type"]:
                        pages = pdf2image.convert_from_bytes(file_item["content"])
                        b = io.BytesIO(); pages[0].save(b, format='PNG')
                        payload = b.getvalue()
                    else:
                        payload = compress_image(file_item["content"])

                    prompt = f"استخرج البيانات التالية فقط في قالب JSON (قائمة تحت مفتاح 'الأصناف'): {', '.join(selected_cols)}"
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    clean_txt = response.text.strip().replace('```json', '').replace('```', '')
                    parsed = json.loads(clean_txt)
                    items = parsed if isinstance(parsed, list) else parsed.get('الأصناف', [])
                    final_results.extend(items)

                if final_results:
                    df = pd.DataFrame(final_results)
                    # ضمان ترتيب الأعمدة المختار
                    df = df[[c for c in selected_cols if c in df.columns]]
                    
                    st.success("✅ اكتمل التحليل بنجاح!")
                    st.dataframe(df, use_container_width=True)
                    
                    # تصدير إكسل
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد')
                        wr.sheets['أزواد'].right_to_left()
                    st.download_button("⬇️ تحميل ملف الإكسل", out.getvalue(), "Azwad_Report.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ تقني: {e}")
