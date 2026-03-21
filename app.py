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
    .main .block-container { max-width: 1000px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.2rem; margin-bottom: 30px; }
    
    /* تنسيق أزرار الاختيار */
    div[data-testid="stRadio"] div[role="radiogroup"] { justify-content: center !important; gap: 20px !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #ffffff; padding: 15px 25px !important; border-radius: 12px !important;
        border: 2px solid #e5e7eb !important; font-weight: bold !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(1) { border-color: #ff4b4b !important; color: #ff4b4b !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(2) { border-color: #1a2a40 !important; color: #1a2a40 !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label:nth-of-type(3) { border-color: #34a853 !important; color: #34a853 !important; }

    /* تعريب صندوق الرفع */
    [data-testid="stFileUploadDropzone"] div div::before { content: "اسحب وأفلت الفواتير هنا" !important; font-weight: bold; }
    [data-testid="baseButton-secondary"]::after { content: "تصفح الملفات" !important; visibility: visible; display: block; }
    [data-testid="baseButton-secondary"] span { visibility: hidden; }
    
    .stCheckbox { text-align: right; direction: rtl; font-weight: bold; }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">مسح الفواتير وعروض الاسعار وتحويلها اكسل - خيارات متعددة</div>
""", unsafe_allow_html=True)

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ تأكد من إعداد المفتاح السري في Secrets")
    st.stop()

# --- خيارات الإدخال الثلاثة ---
selection = st.radio(
    "طريقة الإدخال",
    ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"],
    horizontal=True,
    label_visibility="collapsed"
)

files_to_process = []

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
    drive_url = st.text_input("أدخل رابط قوقل درايف المباشر هنا:", placeholder="تأكد أن الرابط عام (Everyone with the link)")
    if drive_url:
        fid = get_drive_file_id(drive_url)
        if fid:
            d_url = f"https://docs.google.com/uc?export=download&id={fid}"
            with st.spinner("جاري جلب الملف من درايف..."):
                try:
                    res = requests.get(d_url)
                    if res.status_code == 200:
                        files_to_process.append({"name": "درايف_ملف.jpg", "content": res.content, "type": "image/jpeg"})
                        st.success("✅ تم الجلب بنجاح")
                except:
                    st.error("تعذر الوصول للرابط")

# --- بدء عملية المعالجة ---
if files_to_process:
    with st.spinner("جاري تحليل البيانات واستخراج الأعمدة المطلوبة..."):
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
                else:
                    payload = compress_image(f_data["content"])

                prompt = """
                تحليل مالي دقيق: استخرج البيانات في JSON يحتوي على قائمة 'الأصناف'.
                الحقول المطلوبة لكل صنف:
                1. المورد
                2. رقم_الصنف
                3. المادة_اسم_المنتج
                4. الوحدة_الصغيرة (مثل جرام، كيلو)
                5. الكمية_بالوحدة_الصغيرة (الرقم فقط)
                6. الوحدة_الكبيرة (مثل كرتون، كيس)
                7. معامل_التحويل (مثل حبة/كرتون)
                8. الكمية_بالوحدة_الكبيرة (مثل 48، 1)
                9. السعر_الافرادي (السعر قبل الضريبة)
                """
                
                response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                data = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                items = data if isinstance(data, list) else data.get('الأصناف', [])
                all_extracted_data.extend(items)

            if all_extracted_data:
                df_full = pd.DataFrame(all_extracted_data)
                
                # تعريب الأعمدة لتطابق الصورة المطلوبة
                col_translation = {
                    'المورد': 'اسم المورد', 'رقم_الصنف': 'رقم الصنف', 'المادة_اسم_المنتج': 'المادة/اسم المنتج',
                    'الوحدة_الصغيرة': 'الوحدة الصغيرة', 'الكمية_بالوحدة_الصغيرة': 'الكمية',
                    'الوحدة_الكبيرة': 'الوحدة الكبيرة', 'معامل_التحويل': 'معامل التحويل',
                    'الكمية_بالوحدة_الكبيرة': 'الكمية بالوحدة الكبيرة', 'السعر_الافرادي': 'السعر الافرادي'
                }
                df_full.rename(columns=col_translation, inplace=True)

                st.markdown("---")
                st.markdown("### ⚙️ تخصيص أعمدة التصدير (الأعمدة المطلوبة مختارة افتراضياً)")
                
                # القائمة المطلوبة في صورتك لتكون Default
                default_cols = [
                    'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 
                    'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي'
                ]
                
                all_cols = list(df_full.columns)
                cols_to_show = []
                check_cols = st.columns(3)
                for i, col in enumerate(all_cols):
                    is_checked = col in default_cols
                    if check_cols[i % 3].checkbox(col, value=is_checked):
                        cols_to_show.append(col)

                if cols_to_show:
                    # ترتيب الأعمدة حسب طلبك في الصورة
                    order = [c for c in default_cols if c in cols_to_show] + [c for c in cols_to_show if c not in default_cols]
                    df_final = df_full[order]
                    
                    st.markdown("### 📊 معاينة الجدول")
                    st.dataframe(df_final, use_container_width=True)

                    excel_io = io.BytesIO()
                    with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False, sheet_name='أزواد')
                        writer.sheets['أزواد'].right_to_left()
                    
                    st.download_button(
                        label="تحميل اكسل ⬇️",
                        data=excel_io.getvalue(),
                        file_name="AZWAD_SMART_EXTRACT.xlsx",
                        mime="application/vnd.ms-excel"
                    )
        except Exception as e:
            st.error(f"تنبيه: {e}")
