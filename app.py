import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json
import requests
import re

# دالة لتصغير حجم الصورة للحفاظ على السرعة والجودة
def compress_image(image_bytes, quality=75):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality)
    return output.getvalue()

# دالة لاستخراج معرف الملف من رابط قوقل درايف
def get_drive_file_id(url):
    pattern = r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)"
    match = re.search(pattern, url)
    return match.group(1) if match else None

# --- إعدادات الصفحة والعناوين المطلوبة ---
st.set_page_config(page_title="أداة شركة أزواد الذكية", layout="wide")

# تصميم العنوان (الأحمر العريض) والوصف (الرمادي الصغير)
st.markdown("""
    <div style="text-align: right;">
        <h1 style="color: #ff4b4b; font-size: 3rem; margin-bottom: 5px;">أداة شركة أزواد الذكية</h1>
        <p style="color: #6b7280; font-size: 1.2rem;">مسح الفواتير وعروض الاسعار وتحويلها اكسل</p>
    </div>
    <hr>
""", unsafe_allow_html=True)

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("❌ خطأ: لم يتم العثور على المفتاح السري (API Key).")
    st.stop()

# --- تنسيق الأزرار الثلاثة الملونة بالعربية ---
st.markdown("""
<style>
    div[data-testid="stRadio"] div[role="radiogroup"] {
        flex-direction: row !important;
        gap: 20px !important;
        justify-content: flex-start !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #f9fafb;
        padding: 15px 30px !important;
        border-radius: 12px !important;
        border: 2px solid #e5e7eb !important;
        font-weight: bold !important;
        cursor: pointer !important;
    }
    /* الخيار 1: الرفع (أحمر) */
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(1) { border-color: #ff4b4b !important; color: #ff4b4b !important; }
    /* الخيار 2: التقاط (كحلي) */
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(2) { border-color: #1a2a40 !important; color: #1a2a40 !important; }
    /* الخيار 3: درايف (أخضر) */
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(3) { border-color: #34a853 !important; color: #34a853 !important; }
</style>
""", unsafe_allow_html=True)

selection = st.radio(
    "اختر طريقة الإدخال:",
    ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"],
    horizontal=True,
    label_visibility="collapsed"
)

# قائمة لتجميع كل المحتويات المراد تحليلها
files_to_process = []

if selection == "ارفع ملف / ملفات":
    uploads = st.file_uploader("قم بسحب الصور أو ملفات PDF هنا", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    if uploads:
        for f in uploads:
            files_to_process.append({"name": f.name, "content": f.read(), "type": f.type})

elif selection == "التقاط صورة / صور":
    camera_files = st.camera_input("التقط صور الفواتير مباشرة")
    if camera_files:
        # ملاحظة: في النسخ الحالية st.camera_input تلتقط صورة واحدة، أضفتها للقائمة للتوافق
        files_to_process.append({"name": "صورة_كاميرا.jpg", "content": camera_files.read(), "type": "image/jpeg"})

elif selection == "رابط قوقل درايف":
    drive_url = st.text_input("الصق رابط الملف من قوقل درايف (تأكد أن الوصول عام):")
    if drive_url:
        fid = get_drive_file_id(drive_url)
        if fid:
            d_url = f"https://docs.google.com/uc?export=download&id={fid}"
            with st.spinner("جاري سحب الملف من درايف..."):
                try:
                    res = requests.get(d_url)
                    if res.status_code == 200:
                        files_to_process.append({"name": "ملف_درايف.jpg", "content": res.content, "type": "image/jpeg"})
                        st.success("✅ تم جلب الملف بنجاح!")
                except Exception as e:
                    st.error(f"❌ تعذر الوصول للرابط: {e}")

# --- بدء المعالجة الذكية ---
if files_to_process:
    with st.spinner("جاري الاتصال بمحرك شركة أزواد الذكي... 🔍"):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in available_models if "1.5" in m or "vision" in m), available_models[0])
            model = genai.GenerativeModel(target_model)
        except Exception as e:
            st.error(f"خطأ في الاتصال: {e}")
            st.stop()

    all_rows = []
    for f_data in files_to_process:
        with st.spinner(f"جاري تحليل: {f_data['name']}..."):
            try:
                # معالجة الملفات (PDF أو صور مضغوطة)
                if "pdf" in f_data["type"]:
                    imgs = pdf2image.convert_from_bytes(f_data["content"])
                    buf = io.BytesIO()
                    imgs[0].save(buf, format='PNG')
                    img_payload = buf.getvalue()
                else:
                    img_payload = compress_image(f_data["content"])

                prompt = """
                تحليل دقيق للفاتورة: استخرج (اسم المورد، رقم الصنف، المادة، الوحدة، وزن الحبة، معامل التحويل، الوحدة الكبيرة، الكمية، السعر).
                أريد النتيجة JSON فقط في قائمة تحت مفتاح 'الأصناف'.
                """
                
                response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_payload}])
                clean_json = response.text.strip().replace('```json', '').replace('```', '').strip()
                data = json.loads(clean_json)
                if 'الأصناف' in data:
                    all_rows.extend(data['الأصناف'])
            except Exception as e:
                st.warning(f"⚠️ خطأ في {f_data['name']}: {e}")

    if all_rows:
        df = pd.DataFrame(all_rows)
        # تنسيق الأعمدة
        col_map = {
            'اسم_المورد': 'اسم المورد', 'رقم_الصنف': 'رقم الصنف', 'المادة': 'المادة/اسم المنتج',
            'الوحدة': 'الوحدة', 'وزن_الحبة': 'وزن الحبة', 'معامل_التحويل': 'معامل التحويل',
            'الوحدة_الكبيرة': 'الوحدة الكبيرة', 'الكمية': 'الكمية', 'السعر': 'السعر الإجمالي'
        }
        df.rename(columns=col_map, inplace=True)
        st.dataframe(df, use_container_width=True)

        # تصدير الإكسل من اليمين لليسار
        excel_io = io.BytesIO()
        with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='أزواد')
            writer.sheets['أزواد'].right_to_left()
        
        st.download_button("تحميل اكسل", data=excel_io.getvalue(), file_name="AZWAD_REPORT.xlsx", mime="application/vnd.ms-excel")
