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

st.markdown("""
    <style>
    .stApp { align-items: center; display: flex; justify-content: center; }
    .main .block-container { max-width: 1000px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.2rem; margin-bottom: 30px; }
    
    /* تعريب صندوق الرفع */
    [data-testid="stFileUploadDropzone"] div div::before { content: "اسحب وأفلت الفواتير هنا" !important; font-weight: bold; }
    [data-testid="baseButton-secondary"]::after { content: "تصفح الملفات" !important; visibility: visible; display: block; }
    [data-testid="baseButton-secondary"] span { visibility: hidden; }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">نظام جرد وتدقيق الفواتير الذكي - حساب تلقائي للأسعار</div>
""", unsafe_allow_html=True)

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ تأكد من إعداد المفتاح السري في Settings > Secrets")
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

# --- بدء عملية المعالجة ---
if files_to_process:
    if st.button("🚀 تحليل وحساب الأسعار"):
        with st.spinner("جاري استخراج البيانات وحساب السعر الإفرادي..."):
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                all_rows = []
                
                for f_data in files_to_process:
                    img_payload = compress_image(f_data["content"]) if "pdf" not in f_data["type"] else f_data["content"]
                    
                    # Prompt مطور لاستخراج البيانات بدقة وحساب الإفرادي
                    prompt = """
                    استخرج البيانات من الفاتورة بدقة عالية كجدول JSON.
                    هام جداً:
                    1. المادة: استخرج اسم المنتج فقط بدون الأوزان أو الأرقام الملحقة (مثلاً: 'بديل ليمون' بدلاً من 'بديل ليمون فرشلي 12*1 لتر').
                    2. السعر الإجمالي: هو السعر قبل الضريبة.
                    3. السعر الإفرادي: قم بقسمة السعر الإجمالي على الكمية.
                    الأعمدة المطلوبة: [اسم المورد، رقم الصنف، المادة، الوحدة، الكمية، السعر الإفرادي، السعر الإجمالي].
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_payload}])
                    clean_json = response.text.strip().replace('```json', '').replace('```', '').strip()
                    data = json.loads(clean_json)
                    items = data if isinstance(data, list) else data.get('الأصناف', [])
                    all_rows.extend(items)

                if all_rows:
                    df = pd.DataFrame(all_rows)
                    
                    # تحويل القيم لأرقام لضمان دقة العمليات الحسابية
                    df['الكمية'] = pd.to_numeric(df['الكمية'], errors='coerce')
                    df['السعر الإجمالي'] = pd.to_numeric(df['السعر الإجمالي'], errors='coerce')
                    
                    # حساب السعر الإفرادي في حال لم يحسبه الذكاء الاصطناعي بدقة
                    df['السعر الإفرادي'] = (df['السعر الإجمالي'] / df['الكمية']).round(2)
                    
                    # إعادة ترتيب الأعمدة حسب طلبك
                    cols_order = ['اسم المورد', 'رقم الصنف', 'المادة', 'الوحدة', 'الكمية', 'السعر الإفرادي', 'السعر الإجمالي']
                    df = df[cols_order]

                    st.markdown("### 📊 الكشف النهائي المعتمد")
                    st.dataframe(df, use_container_width=True)
                    
                    # تصدير الإكسل
                    excel_io = io.BytesIO()
                    with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='أزواد')
                        # تنسيق العملة في الإكسل
                        workbook = writer.book
                        worksheet = writer.sheets['أزواد']
                        worksheet.right_to_left()
                    
                    st.download_button("📥 تحميل ملف الاكسل المعدل", data=excel_io.getvalue(), file_name="AZWAD_FINAL_REPORT.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ أثناء المعالجة: {e}")
