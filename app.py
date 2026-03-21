import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json
import requests
import re

# إعداد الصفحة وتوسيط الواجهة
st.set_page_config(page_title="أداة شركة أزواد الذكية", layout="wide")

st.markdown("""
    <style>
    .stApp { align-items: center; display: flex; justify-content: center; }
    .main .block-container { max-width: 1200px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3rem; font-weight: 900; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.1rem; margin-bottom: 30px; }
    
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
    div[data-baseweb="select"] { direction: rtl; }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">نظام التحليل الشامل والمنطقي - تم تثبيت كافة الأعمدة والبيانات</div>
""", unsafe_allow_html=True)

def compress_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    out = io.BytesIO(); img.save(out, format='JPEG', quality=85)
    return out.getvalue()

def get_drive_id(url):
    m = re.search(r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)", url)
    return m.group(1) if m else None

# إعداد الـ API مع آلية البحث المرن
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ تأكد من إعداد المفتاح السري")
    st.stop()

# واجهة الإدخال داخل نموذج (Form) لمنع الدوران المتكرر
with st.form("azwad_master_stabilized_form"):
    selection = st.radio("طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"], horizontal=True)
    
    files_input = None
    if selection == "ارفع ملف / ملفات":
        files_input = st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        cam_raw = st.camera_input("")
        if cam_raw: files_input = [cam_raw]
    elif selection == "رابط قوقل درايف":
        d_url = st.text_input("أدخل رابط درايف المباشر:")

    st.markdown("---")
    st.markdown("### ⚙️ اختر الأعمدة (تم تثبيت الترتيب والبيانات المطلوبة)");
    
    # القائمة الكاملة المجمعة والنهائية
    all_final_cols = [
        'اسم المورد', 'رقم الفاتورة / عرض السعر', 'الرقم الضريبي للمورد', 'رقم السجل التجاري',
        'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 'الكمية', 
        'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي',
        'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]
    
    # الأعمدة الأساسية التي تظهر تلقائياً
    default_enabled = [
        'اسم المورد', 'رقم الفاتورة / عرض السعر', 'الرقم الضريبي للمورد', 'رقم السجل التجاري',
        'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 'الكمية', 
        'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي'
    ]
    
    # ميزة الترتيب الديناميكي المخصصة
    chosen_cols = st.multiselect(
        "رتب الأعمدة بسحبها أو اختيارها بالترتيب المطلوب:",
        options=all_final_cols,
        default=default_enabled
    )

    submit = st.form_submit_button("🚀 ابدأ الاستخراج والتحليل الشامل")

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
        with st.spinner("جاري استخراج وتحليل البيانات كافة بالمنطق الرياضي الصحيح..."):
            try:
                # آلية البحث التلقائي عن الموديل (تجاوز خطأ 404)
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target_m = next((m for m in models if "1.5" in m or "flash" in m), models[0])
                model = genai.GenerativeModel(target_m)
                
                results = []
                for f_item in final_files:
                    if "pdf" in f_item["type"]:
                        p = pdf2image.convert_from_bytes(f_item["content"])
                        b = io.BytesIO(); p[0].save(b, format='PNG'); payload = b.getvalue()
                    else: payload = compress_image(f_item["content"])

                    prompt = f"""
                    أنت محلل مالي دقيق. استخرج الأصناف من الفاتورة في JSON.
                    
                    القواعد الذهبية (حرج جداً):
                    1. 'معامل التحويل (آلي ذكي)': اقرأ البيان الأصلي للمادة. إذا وجدت رقمين مضروبين (مثل 6*2) أو كلمة "شد" أو "كرتون"، استنتج الرقم فقط وسجله كعدد حبات في الكرتون. إذا لم يوجد، ضع 1.
                    2. 'الكمية بالوحدة الكبيرة': هي الكمية المكتوبة في عمود الكمية بالفاتورة (عدد الكراتين).
                    3. 'السعر الافرادي': هو سعر الكرتون (الوحدة الكبيرة).
                    4. 'الإجمالي الصافي': (الكمية بالوحدة الكبيرة × السعر الافرادي).
                    5. 'المادة/اسم المنتج': اسم صافي بدون أرقام أو أوزان.
                    6. 'الضريبة': مبلغ الضريبة الفعلي بالريال لكل صنف.
                    7. استخرج بيانات المورد (الاسم، السجل، الرقم الضريبي) ورقم الفاتورة.
                    
                    الحقول المطلوبة: {', '.join(chosen_cols)}
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    data_txt = response.text.strip().replace('```json', '').replace('```', '')
                    data = json.loads(data_txt)
                    items = data if isinstance(data, list) else data.get('الأصناف', [])

                    # --- المعالجة الرياضية البرمجية وتنسيق المعامل ---
                    for item in items:
                        try:
                            qty_large = float(str(item.get('الكمية بالوحدة الكبيرة', 0)).replace(',', ''))
                            factor = float(str(item.get('معامل التحويل', 1)).replace(',', ''))
                            
                            # المنطق الرياضي الصحيح (الحبة = الكرتون × المعامل)
                            item['الكمية'] = qty_large * factor
                            # صياغة المعامل نصياً كما في الصورة
                            item['معامل التحويل'] = f"{int(factor)} حبة / {item.get('الوحدة الكبيرة', 'كرتون')}"
                            
                            # تنظيف اسم المنتج
                            item['المادة/اسم المنتج'] = re.sub(r'\d+[\*×]\d+.*|[\d\.]+\s*(جرام|جم|كجم|كيلو|لتر|مل)', '', str(item.get('المادة/اسم المنتج', ''))).strip()
                        except: continue
                    results.extend(items)

                if results:
                    df = pd.DataFrame(results)
                    df = df[[c for c in chosen_cols if c in df.columns]]
                    
                    st.success("✅ تم استخراج كافة البيانات بالترتيب المعتمد!")
                    st.dataframe(df, use_container_width=True)
                    
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد Master'); wr.sheets['أزواد Master'].right_to_left()
                    st.download_button("⬇️ تحميل التقرير الذهبي الموحد", out.getvalue(), "Azwad_Master_Report.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")
