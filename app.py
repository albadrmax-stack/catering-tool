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

# تهيئة مخزن الترتيب مع الأعمدة الجديدة
if 'cols_order' not in st.session_state:
    st.session_state.cols_order = [
        'اسم المورد', 'رقم الفاتورة / عرض السعر', 'الرقم الضريبي للمورد', 'رقم السجل التجاري',
        'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 'الكمية', 
        'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي'
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
    div[data-baseweb="select"] { direction: rtl; }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">استخراج شامل ودقيق للبيانات - تنظيف ذكي لاسم المنتج</div>
""", unsafe_allow_html=True)

def compress_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    out = io.BytesIO(); img.save(out, format='JPEG', quality=80)
    return out.getvalue()

def get_drive_id(url):
    m = re.search(r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)", url)
    return m.group(1) if m else None

# --- واجهة الإدخال ---
with st.form("azwad_final_form"):
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
    
    # قائمة الخيارات الموسعة
    all_options = [
        'اسم المورد', 'رقم الفاتورة / عرض السعر', 'الرقم الضريبي للمورد', 'رقم السجل التجاري',
        'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 'الكمية', 
        'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي',
        'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]
    
    chosen_cols = st.multiselect(
        "رتب الأعمدة المختارة بسحبها أو اختيارها بالترتيب:",
        options=all_options,
        default=st.session_state.cols_order
    )

    submit = st.form_submit_button("🚀 ابدأ استخراج وتحليل البيانات بالترتيب المختار")

# --- التنفيذ ---
if submit and (files_input or (selection == "رابط قوقل درايف" and d_url)):
    final_files = []
    if selection == "رابط قوقل درايف":
        fid = get_drive_id(d_url)
        if fid:
            try:
                r = requests.get(f"https://docs.google.com/uc?export=download&id={fid}")
                if r.status_code == 200: final_files.append({"name": "drive.jpg", "content": r.content, "type": "image/jpeg"})
            except: st.error("فشل جلب الملف من درايف")
    else:
        for f in files_input: final_files.append({"name": f.name, "content": f.read(), "type": f.type})

    if final_files:
        with st.spinner("جاري استخراج البيانات وتنظيف اسم المنتج بذكاء..."):
            try:
                gen_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target_m = next((m for m in gen_models if "1.5" in m or "flash" in m), gen_models[0])
                model = genai.GenerativeModel(target_m)
                
                results = []
                for f_item in final_files:
                    if "pdf" in f_item["type"]:
                        p = pdf2image.convert_from_bytes(f_item["content"])
                        b = io.BytesIO(); p[0].save(b, format='PNG'); payload = b.getvalue()
                    else: payload = compress_image(f_data := f_item["content"])

                    # التعليمات البرمجية الصارمة للذكاء الاصطناعي لتنظيف اسم المنتج
                    prompt = f"""
                    أنت خبير تدقيق مالي. استخرج البيانات التالية بدقة من الفاتورة في قالب JSON بأسماء الحقول المذكورة تماماً.
                    ركز جيداً على التعليمات التالية:
                    - 'المادة/اسم المنتج': استخرج اسم المنتج فقط وصافياً تماماً. يجب ألا يحتوي هذا الحقل على أي أرقام أو أوزان (مثلاً '2*6 كيلو' أو '145 جم').
                    - 'رقم الفاتورة / عرض السعر': ابحث عنه في ترويسة الفاتورة.
                    - 'الرقم الضريبي للمورد': الرقم المكون من 15 خانة.
                    - باقي الحقول المطلوبة: {', '.join(chosen_cols)}
                    يجب أن تكون النتيجة قائمة JSON تحت مفتاح 'الأصناف'.
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    data_txt = response.text.strip().replace('```json', '').replace('```', '')
                    data = json.loads(data_txt)
                    items = data if isinstance(data, list) else data.get('الأصناف', [])
                    all_extracted_data = items
                    
                    # تنظيف برمي نهائي احتياطي في لغة بايثون
                    def clean_product_name(text):
                        if text:
                            text = text.strip()
                            # إزالة الأنماط الشائعة مثل "أرقام * أرقام كيلو" أو "أرقام جم"
                            text = re.sub(r'\d+(\*|\×)\d+(\s*[أإآا]?[كك]يلو?|[كك]غ?|\s*جم?)', '', text, flags=re.IGNORECASE)
                            # إزالة الأرقام المفردة في نهاية السلسلة
                            text = re.sub(r'\s*\d+\s*[أإآا]?[كك]يلو?|\d+\s*[كك]غ?|\d+\s*جم?$', '', text, flags=re.IGNORECASE)
                            text = text.strip()
                        return text

                    # تطبيق التنظيف النهائي على عمود المادة/اسم المنتج
                    for item in items:
                        if 'المادة/اسم المنتج' in item:
                            item['المادة/اسم المنتج'] = clean_product_name(item['المادة/اسم المنتج'])
                    
                    results.extend(items)

                if results:
                    df = pd.DataFrame(results)
                    # ضمان الترتيب الذي اختاره المستخدم
                    df = df[[c for c in chosen_cols if c in df.columns]]
                    
                    st.success("✅ تم الاستخراج وتنظيف البيانات بنجاح تام!")
                    st.dataframe(df, use_container_width=True)
                    
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد')
                        wr.sheets['أزواد'].right_to_left()
                    st.download_button("⬇️ تحميل تقرير شركة أزواد الشامل والمنظف", out.getvalue(), "Azwad_Clean_Master_Report.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")
