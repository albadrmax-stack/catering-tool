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

# --- إعدادات الصفحة والتنسيق البصري ---
st.set_page_config(page_title="أداة شركة أزواد الذكية", layout="wide")

# كود CSS للتوسيط والتعريب الكامل
st.markdown("""
    <style>
    /* توسيط المحتوى بالكامل */
    .main .block-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
    }
    
    /* تنسيق العناوين */
    .title-red { color: #ff4b4b; font-size: 3.5rem; font-weight: bold; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.3rem; margin-top: 0px; margin-bottom: 30px; }
    
    /* توسيط أزرار الاختيار (Radio) */
    div[data-testid="stRadio"] div[role="radiogroup"] {
        justify-content: center !important;
        gap: 20px !important;
    }
    
    /* تعريب صندوق الرفع وتحسين شكله */
    section[data-testid="stFileUploadDropzone"] div div::before {
        content: "اسحب وأفلت الملفات هنا" !important;
        font-family: sans-serif;
    }
    section[data-testid="stFileUploadDropzone"] div div span {
        display: none !important;
    }
    section[data-testid="stFileUploadDropzone"] div div small {
        display: none !important;
    }
    button[data-testid="baseButton-secondary"] {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
    }
    /* تغيير نص زر التصفح */
    button[data-testid="baseButton-secondary"]::after {
        content: "تصفح الملفات" !important;
        visibility: visible;
        display: block;
        position: absolute;
        background-color: #ff4b4b;
        padding: 5px 15px;
        border-radius: 5px;
    }
    button[data-testid="baseButton-secondary"] span {
        visibility: hidden;
    }

    /* تنسيق أزرار الاختيار */
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #ffffff;
        padding: 15px 25px !important;
        border-radius: 12px !important;
        border: 2px solid #e5e7eb !important;
        font-weight: bold !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(1) { border-color: #ff4b4b !important; color: #ff4b4b !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(2) { border-color: #1a2a40 !important; color: #1a2a40 !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(3) { border-color: #34a853 !important; color: #34a853 !important; }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">مسح الفواتير وعروض الاسعار وتحويلها اكسل</div>
    <hr style="width: 100%;">
""", unsafe_allow_html=True)

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ تأكد من إعداد المفتاح السري.")
    st.stop()

selection = st.radio(
    "طريقة الإدخال",
    ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"],
    horizontal=True,
    label_visibility="collapsed"
)

files_to_process = []

# توسيط صناديق الإدخال
col_side1, col_mid, col_side2 = st.columns([1, 4, 1])

with col_mid:
    if selection == "ارفع ملف / ملفات":
        uploads = st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
        if uploads:
            for f in uploads:
                files_to_process.append({"name": f.name, "content": f.read(), "type": f.type})

    elif selection == "التقاط صورة / صور":
        camera_files = st.camera_input("")
        if camera_files:
            files_to_process.append({"name": "صورة_كاميرا.jpg", "content": camera_files.read(), "type": "image/jpeg"})

    elif selection == "رابط قوقل درايف":
        drive_url = st.text_input("أدخل رابط قوقل درايف المباشر هنا:", placeholder="الصق الرابط هنا...")
        if drive_url:
            fid = get_drive_file_id(drive_url)
            if fid:
                d_url = f"https://docs.google.com/uc?export=download&id={fid}"
                with st.spinner("جاري السحب..."):
                    try:
                        res = requests.get(d_url)
                        if res.status_code == 200:
                            files_to_process.append({"name": "درايف.jpg", "content": res.content, "type": "image/jpeg"})
                            st.success("✅ تم جلب الملف")
                    except:
                        st.error("فشل الجلب")

# --- المعالجة والعرض ---
if files_to_process:
    with st.spinner("جاري المعالجة الذكية..."):
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
                if 'الأصناف' in data: all_rows.extend(data['الأصناف'])
                elif isinstance(data, list): all_rows.extend(data)

            if all_rows:
                df = pd.DataFrame(all_rows)
                st.dataframe(df, use_container_width=True)
                
                excel_io = io.BytesIO()
                with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='أزواد')
                    writer.sheets['أزواد'].right_to_left()
                
                st.download_button("تحميل ملف الاكسل ⬇️", data=excel_io.getvalue(), file_name="AZWAD_REPORT.xlsx")
        except Exception as e:
            st.error(f"تنبيه: {e}")
