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

# تهيئة مخزن الترتيب في ذاكرة المتصفح
if 'cols_order' not in st.session_state:
    st.session_state.cols_order = [
        'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 
        'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي'
    ]

st.markdown("""
    <style>
    .stApp { align-items: center; display: flex; justify-content: center; }
    .main .block-container { max-width: 1100px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.1rem; margin-bottom: 30px; }
    
    .stButton > button {
        background-color: #ff4b4b !important; color: white !important;
        font-size: 1.3rem !important; padding: 10px !important;
        border-radius: 10px !important; width: 100% !important;
    }
    .stCheckbox { text-align: right; direction: rtl; font-weight: bold; }
    .order-box { background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin-bottom: 20px; border: 1px dashed #ff4b4b; }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">رتب أعمدتك كما تحب: العمود الذي تختاره أولاً يظهر أولاً في الإكسل</div>
""", unsafe_allow_html=True)

# دالات المساعدة
def compress_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    out = io.BytesIO(); img.save(out, format='JPEG', quality=80)
    return out.getvalue()

def get_drive_id(url):
    m = re.search(r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)", url)
    return m.group(1) if m else None

# --- واجهة الإدخال ---
with st.form("dynamic_form"):
    selection = st.radio("طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"], horizontal=True)
    
    files_input = None
    if selection == "ارفع ملف / ملفات":
        files_input = st.file_uploader("قم بسحب الملفات", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        cam_raw = st.camera_input("التقط صورة")
        if cam_raw: files_input = [cam_raw]
    elif selection == "رابط قوقل درايف":
        d_url = st.text_input("رابط درايف:")

    st.markdown("### ⚙️ اختر الأعمدة (بالترتيب الذي تفضله):")
    
    all_options = [
        'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 
        'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 
        'السعر الافرادي', 'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]
    
    # ميزة الترتيب الذكي: نستخدم multiselect ليسمح للمستخدم بالترتيب اليدوي
    chosen_cols = st.multiselect(
        "اسحب الأسماء أو اخترها بالترتيب المطلوب (من اليمين لليسار):",
        options=all_options,
        default=st.session_state.cols_order
    )

    submit = st.form_submit_button("🚀 ابدأ استخراج وتحليل البيانات بالترتيب المختار")

# --- التنفيذ ---
if submit and (files_input or (selection == "رابط قوقل درايف" and d_url)):
    final_files = []
    # منطق جلب الملفات
    if selection == "رابط قوقل درايف":
        fid = get_drive_id(d_url)
        if fid:
            r = requests.get(f"https://docs.google.com/uc?export=download&id={fid}")
            if r.status_code == 200: final_files.append({"name": "drive.jpg", "content": r.content, "type": "image/jpeg"})
    else:
        for f in files_input: final_files.append({"name": f.name, "content": f.read(), "type": f.type})

    if final_files:
        with st.spinner("جاري التحليل وفق ترتيبك الخاص..."):
            try:
                # صيد الموديل
                gen_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                model = genai.GenerativeModel(next((m for m in gen_models if "1.5" in m), gen_models[0]))
                
                results = []
                for f_item in final_files:
                    if "pdf" in f_item["type"]:
                        p = pdf2image.convert_from_bytes(f_item["content"])
                        b = io.BytesIO(); p[0].save(b, format='PNG'); payload = b.getvalue()
                    else: payload = compress_image(f_data := f_item["content"])

                    prompt = f"استخرج البيانات التالية فقط في JSON بأسماء الحقول المذكورة: {', '.join(chosen_cols)}"
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    data = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                    items = data if isinstance(data, list) else data.get('الأصناف', [])
                    results.extend(items)

                if results:
                    df = pd.DataFrame(results)
                    # السحر هنا: إعادة ترتيب الأعمدة تماماً كما اختار المستخدم في الـ multiselect
                    df = df[[c for c in chosen_cols if c in df.columns]]
                    
                    st.success("✅ اكتمل التحليل بالترتيب المطلوب!")
                    st.dataframe(df, use_container_width=True)
                    
                    # إكسل
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد')
                        wr.sheets['أزواد'].right_to_left()
                    st.download_button("⬇️ تحميل الإكسل المُرتب", out.getvalue(), "Azwad_Custom_Order.xlsx")
            except Exception as e:
                st.error(f"خطأ: {e}")
