import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json
import requests
import re

# دالة لتصغير حجم الصورة
def compress_image(image_bytes, quality=75):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality)
    return output.getvalue()

def get_drive_file_id(url):
    pattern = r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)"
    match = re.search(pattern, url)
    return match.group(1) if match else None

# --- إعدادات الصفحة والتنسيق البصري الاحترافي ---
st.set_page_config(page_title="أداة شركة أزواد الذكية", layout="wide")

# كود CSS للتوسيط والتعريب وتحسين الواجهة
st.markdown("""
    <style>
    /* توسيط المحتوى بالكامل في الصفحة */
    .stApp {
        align-items: center;
        display: flex;
        justify-content: center;
    }
    .main .block-container {
        max-width: 900px;
        padding-top: 2rem;
        text-align: center;
    }
    
    /* تصميم العنوان والأوصاف */
    .title-red { color: #ff4b4b; font-size: 4rem; font-weight: 900; margin-bottom: 0px; line-height: 1.2; }
    .subtitle-gray { color: #6b7280; font-size: 1.4rem; margin-top: 10px; margin-bottom: 40px; }
    
    /* توسيط الراديو وتغيير شكله لأزرار */
    div[data-testid="stRadio"] div[role="radiogroup"] {
        justify-content: center !important;
        gap: 20px !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #ffffff;
        padding: 15px 30px !important;
        border-radius: 12px !important;
        border: 2px solid #e5e7eb !important;
        font-weight: bold !important;
        transition: 0.3s;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(1) { border-color: #ff4b4b !important; color: #ff4b4b !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(2) { border-color: #1a2a40 !important; color: #1a2a40 !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(3) { border-color: #34a853 !important; color: #34a853 !important; }

    /* تعريب صندوق الرفع بالكامل */
    [data-testid="stFileUploadDropzone"] div div::before {
        content: "اسحب وأفلت الفواتير هنا" !important;
        font-weight: bold;
        font-size: 1.2rem;
    }
    [data-testid="stFileUploadDropzone"] div div span { display: none; }
    [data-testid="stFileUploadDropzone"] div div small { display: none; }
    
    /* تعريب زر تصفح الملفات */
    [data-testid="baseButton-secondary"] {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
        height: 45px;
    }
    [data-testid="baseButton-secondary"]::after {
        content: "تصفح الملفات" !important;
        visibility: visible;
        display: block;
        padding: 10px 20px;
    }
    [data-testid="baseButton-secondary"] span { visibility: hidden; }
    
    /* توسيط محاذاة النص في الجدول */
    .stDataFrame { margin: 0 auto; }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">مسح الفواتير وعروض الاسعار وتحويلها اكسل</div>
    <hr>
""", unsafe_allow_html=True)

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ تأكد من إعداد المفتاح السري في Settings > Secrets")
    st.stop()

# خيارات الإدخال في المنتصف
selection = st.radio(
    "طريقة الإدخال",
    ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"],
    horizontal=True,
    label_visibility="collapsed"
)

files_to_process = []

# عرض المحتوى بناءً على الاختيار
if selection == "ارفع ملف / ملفات":
    uploads = st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    if uploads:
        for f in uploads:
            files_to_process.append({"name": f.name, "content": f.read(), "type": f.type})

elif selection == "التقاط صورة / صور":
    camera_file = st.camera_input("")
    if camera_file:
        files_to_process.append({"name": "صورة_كاميرا.jpg", "content": camera_file.read(), "type": "image/jpeg"})

elif selection == "رابط قوقل درايف":
    drive_url = st.text_input("الصق رابط قوقل درايف هنا:", placeholder="تأكد أن الرابط عام (Everyone with the link)")
    if drive_url:
        fid = get_drive_file_id(drive_url)
        if fid:
            d_url = f"https://docs.google.com/uc?export=download&id={fid}"
            with st.spinner("جاري جلب الملف..."):
                try:
                    res = requests.get(d_url)
                    if res.status_code == 200:
                        files_to_process.append({"name": "درايف_ملف.jpg", "content": res.content, "type": "image/jpeg"})
                        st.success("✅ تم الجلب بنجاح")
                except:
                    st.error("تعذر الوصول للرابط")

# --- بدء عملية المعالجة ---
if files_to_process:
    if st.button("🚀 ابدأ التحليل الآن"):
        with st.spinner("جاري تحليل البيانات بذكاء أزواد..."):
            try:
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target_model = next((m for m in available_models if "1.5" in m or "vision" in m), available_models[0])
                model = genai.GenerativeModel(target_model)
                
                all_rows = []
                for f_data in files_to_process:
                    if "pdf" in f_data["type"]:
                        imgs = pdf2image.convert_from_bytes(f_data["content"])
                        buf = io.BytesIO()
                        imgs[0].save(buf, format='PNG')
                        img_payload = buf.getvalue()
                    else:
                        img_payload = compress_image(f_data["content"])

                    prompt = "استخرج تفاصيل الفاتورة كجدول JSON (اسم المورد، رقم الصنف، المادة، الوحدة، وزن الحبة، معامل التحويل، الوحدة الكبيرة، الكمية، السعر)."
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_payload}])
                    clean_json = response.text.strip().replace('```json', '').replace('```', '').strip()
                    data = json.loads(clean_json)
                    
                    # استخراج الأصناف
                    if 'الأصناف' in data: items = data['الأصناف']
                    elif isinstance(data, list): items = data
                    else: items = []
                    
                    all_rows.extend(items)

                if all_rows:
                    st.markdown("### 📊 البيانات المستخرجة")
                    df = pd.DataFrame(all_rows)
                    st.dataframe(df, use_container_width=True)
                    
                    # تصدير الإكسل
                    excel_io = io.BytesIO()
                    with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='أزواد')
                        writer.sheets['أزواد'].right_to_left()
                    
                    st.download_button("📥 تحميل ملف الاكسل (يمين لليسار)", data=excel_io.getvalue(), file_name="AZWAD_DATA.xlsx")
            except Exception as e:
                st.error(f"تنبيه: {e}")
