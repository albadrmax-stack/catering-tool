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

if 'cols_order' not in st.session_state:
    st.session_state.cols_order = [
        'اسم المورد', 'رقم الفاتورة / عرض السعر', 'رقم الصنف', 'المادة/اسم المنتج', 
        'الوحدة الصغيرة', 'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 
        'الكمية بالوحدة الكبيرة', 'السعر الافرادي', 'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]

st.markdown("""
    <style>
    .stApp { align-items: center; display: flex; justify-content: center; }
    .main .block-container { max-width: 1150px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3rem; font-weight: 900; margin-bottom: 0px; }
    .stButton > button { background-color: #ff4b4b !important; color: white !important; width: 100% !important; border-radius: 10px !important; font-size: 1.2rem; }
    </style>
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div style="text-align: center; color: gray; margin-bottom: 20px;">نظام استخراج وتحليل الفواتير - النسخة المعتمدة المستقرة</div>
""", unsafe_allow_html=True)

# دالة ضغط الصور الأساسية
def compress_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    out = io.BytesIO(); img.save(out, format='JPEG', quality=85)
    return out.getvalue()

# إعداد الـ API
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ تأكد من إعداد المفتاح السري في Settings > Secrets")
    st.stop()

# واجهة الإدخال
selection = st.radio("طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"], horizontal=True)

all_options = st.session_state.cols_order
chosen_cols = st.multiselect("رتب الأعمدة المختارة بسحبها أو اختيارها:", options=all_options, default=st.session_state.cols_order)

with st.form("azwad_stable_form"):
    files_input = None
    if selection == "ارفع ملف / ملفات":
        files_input = st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        cam_raw = st.camera_input("")
        if cam_raw: files_input = [cam_raw]
    elif selection == "رابط قوقل درايف":
        d_url = st.text_input("أدخل رابط درايف المباشر:")

    submit = st.form_submit_button("🚀 ابدأ الاستخراج والتحليل")

if submit:
    final_files = []
    if selection == "رابط قوقل درايف" and d_url:
        fid = re.search(r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)", d_url)
        if fid:
            r = requests.get(f"https://docs.google.com/uc?export=download&id={fid.group(1)}")
            if r.status_code == 200: final_files.append({"name": "drive.jpg", "content": r.content, "type": "image/jpeg"})
    elif files_input:
        input_list = [files_input] if not isinstance(files_input, list) else files_input
        for f in input_list: final_files.append({"name": f.name, "content": f.read(), "type": f.type})

    if not final_files:
        st.warning("⚠️ الرجاء اختيار ملف أولاً.")
    else:
        with st.spinner("جاري تحليل البيانات..."):
            try:
                # صيد الموديل التلقائي
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target_m = next((m for m in models if "1.5" in m or "flash" in m), models[0])
                model = genai.GenerativeModel(target_m)
                
                all_extracted = []
                for f_item in final_files:
                    # معالجة الـ PDF أو الصور
                    if "pdf" in f_item["type"]:
                        pages = pdf2image.convert_from_bytes(f_item["content"])
                        b = io.BytesIO(); pages[0].save(b, format='PNG'); payload = b.getvalue()
                    else:
                        payload = compress_image(f_item["content"])

                    prompt = f"""
                    استخرج البيانات من الفاتورة في قالب JSON بأسماء الحقول المذكورة: {', '.join(chosen_cols)}
                    القواعد:
                    - المادة/اسم المنتج: بدون أرقام أو أوزان.
                    - الضريبة: المبلغ المالي بالريال.
                    - معامل التحويل: الرقم المستنتج (مثل 6 أو 12).
                    - الكمية = (الكمية بالوحدة الكبيرة × معامل التحويل).
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    data = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                    items = data if isinstance(data, list) else data.get('الأصناف', [])
                    
                    # تنظيف اسم المادة برمجياً لضمان الدقة
                    for it in items:
                        if 'المادة/اسم المنتج' in it:
                            it['المادة/اسم المنتج'] = re.sub(r'\d+[\*×]\d+.*|[\d\.]+\s*(جرام|جم|كجم|كيلو|لتر|مل)', '', str(it['المادة/اسم المنتج'])).strip()
                    all_extracted.extend(items)

                if all_extracted:
                    df = pd.DataFrame(all_extracted)
                    df = df[[c for c in chosen_cols if c in df.columns]]
                    st.success("✅ تم استخراج البيانات بنجاح!")
                    st.dataframe(df, use_container_width=True)
                    
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد'); wr.sheets['أزواد'].right_to_left()
                    st.download_button("⬇️ تحميل ملف الإكسل", out.getvalue(), "Azwad_Final.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")
