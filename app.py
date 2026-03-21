import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json
import requests
import re

# إعداد الصفحة
st.set_page_config(page_title="أداة شركة أزواد الذكية", layout="wide")

# التنسيق البصري (CSS)
st.markdown("""
    <style>
    .stApp { align-items: center; display: flex; justify-content: center; }
    .main .block-container { max-width: 1100px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.2rem; margin-bottom: 30px; }
    
    /* تنسيق الحاوية (الفورم) */
    .stForm { border: none !important; padding: 0 !important; }
    
    /* أزرار الاختيار */
    div[data-testid="stRadio"] div[role="radiogroup"] { justify-content: center !important; gap: 20px !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #ffffff; padding: 15px 25px !important; border-radius: 12px !important;
        border: 2px solid #e5e7eb !important; font-weight: bold !important;
    }
    
    .stButton > button {
        background-color: #ff4b4b !important; color: white !important;
        font-size: 1.5rem !important; padding: 10px 50px !important;
        border-radius: 15px !important; width: 100% !important; margin-top: 20px;
    }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">حدد خياراتك بدقة ثم ابدأ التحليل بنقرة واحدة</div>
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
    st.error("❌ تأكد من إعداد المفتاح السري")
    st.stop()

# --- بداية نموذج الإدخال (Form) لمنع الدوران المتكرر ---
with st.form("main_form"):
    selection = st.radio("اختر طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"], horizontal=True)
    
    uploads = None
    camera_file = None
    drive_url = ""
    
    if selection == "ارفع ملف / ملفات":
        uploads = st.file_uploader("قم بسحب الملفات هنا", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        camera_file = st.camera_input("التقط صورة الفاتورة")
    elif selection == "رابط قوقل درايف":
        drive_url = st.text_input("أدخل رابط قوقل درايف المباشر:")

    st.markdown("---")
    st.markdown("### ⚙️ اختر الأعمدة التي تريد استخراجها")
    
    # قائمة كافة الأعمدة المتاحة
    all_possible_cols = [
        'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 
        'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 
        'السعر الافرادي', 'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]
    
    # الأعمدة الافتراضية من صورتك
    default_selected = [
        'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 
        'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي'
    ]
    
    selected_cols = []
    col_layout = st.columns(3)
    for i, col_name in enumerate(all_possible_cols):
        is_default = col_name in default_selected
        if col_layout[i % 3].checkbox(col_name, value=is_default):
            selected_cols.append(col_name)

    # زر البدأ (لن يتحرك الكود إلا عند الضغط عليه)
    submit_button = st.form_submit_button("🚀 ابدأ استخراج وتحليل البيانات")

# --- معالجة البيانات بعد الضغط على الزر ---
if submit_button:
    files_to_process = []
    
    # تجميع الملفات بناءً على الاختيار
    if selection == "ارفع ملف / ملفات" and uploads:
        for f in uploads: files_to_process.append({"name": f.name, "content": f.read(), "type": f.type})
    elif selection == "التقاط صورة / صور" and camera_file:
        files_to_process.append({"name": "camera.jpg", "content": camera_file.read(), "type": "image/jpeg"})
    elif selection == "رابط قوقل درايف" and drive_url:
        fid = get_drive_file_id(drive_url)
        if fid:
            res = requests.get(f"https://docs.google.com/uc?export=download&id={fid}")
            if res.status_code == 200: files_to_process.append({"name": "drive.jpg", "content": res.content, "type": "image/jpeg"})

    if not files_to_process:
        st.warning("⚠️ يرجى إدخال ملف أو صورة أولاً.")
    else:
        with st.spinner("جاري التحليل... انتظر قليلاً"):
            try:
                model = genai.GenerativeModel("gemini-1.5-flash") # تم التحديث للموديل المستقر
                all_extracted_data = []
                
                for f_data in files_to_process:
                    if "pdf" in f_data["type"]:
                        imgs = pdf2image.convert_from_bytes(f_data["content"])
                        buf = io.BytesIO(); imgs[0].save(buf, format='PNG')
                        payload = buf.getvalue()
                    else:
                        payload = compress_image(f_data["content"])

                    prompt = f"""
                    استخرج البيانات التالية فقط في شكل JSON: {', '.join(selected_cols)}.
                    يجب أن يكون الرد عبارة عن قائمة 'الأصناف'.
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    data = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                    items = data if isinstance(data, list) else data.get('الأصناف', [])
                    all_extracted_data.extend(items)

                if all_extracted_data:
                    df = pd.DataFrame(all_extracted_data)
                    # ضمان ترتيب الأعمدة كما تم اختيارها
                    df = df[[c for c in selected_cols if c in df.columns]]
                    
                    st.success("✅ تم الاستخراج بنجاح")
                    st.dataframe(df, use_container_width=True)
                    
                    # زر التحميل
                    excel_io = io.BytesIO()
                    with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='أزواد')
                    st.download_button("تحميل ملف Excel ⬇️", excel_io.getvalue(), "Azwad_Data.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")
