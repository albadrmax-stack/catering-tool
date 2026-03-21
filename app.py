import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json
import requests
import re

# 1. إعداد الصفحة والتنسيق (توسيط العناصر والعنوان الأحمر الكبير)
st.set_page_config(page_title="أداة شركة أزواد الذكية", layout="wide")

st.markdown("""
    <style>
    .stApp { align-items: center; display: flex; justify-content: center; }
    .main .block-container { max-width: 1250px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.2rem; margin-bottom: 30px; }
    
    /* تنسيق أزرار الراديو */
    div[data-testid="stRadio"] div[role="radiogroup"] { justify-content: center !important; gap: 20px !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #ffffff; padding: 15px 25px !important; border-radius: 12px !important;
        border: 2px solid #e5e7eb !important; font-weight: bold !important;
    }
    
    /* تنسيق زر البداية */
    .stButton > button {
        background-color: #ff4b4b !important; color: white !important;
        font-size: 1.3rem !important; padding: 15px !important;
        border-radius: 10px !important; width: 100% !important;
    }
    .stCheckbox { text-align: right; direction: rtl; font-weight: bold; }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">حدد خياراتك بدقة ثم ابدأ التحليل بنقرة واحدة</div>
""", unsafe_allow_html=True)

# 2. إعداد الـ API وتكوين الموديل (تطبيق آلية البحث المرن لتجنب الـ 404)
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"❌ خطأ في إعداد المفتاح: {e}")
    st.stop()

# 3. دالات المساعدة (ضغط الصور، جلب درايف، إلخ)
def compress_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    out = io.BytesIO(); img.save(out, format='JPEG', quality=85)
    return out.getvalue()

def get_drive_id(url):
    m = re.search(r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)", url)
    return m.group(1) if m else None

# --- بداية واجهة المستخدم (بالترتيب من الصورة 19) ---
with st.container():
    # 3.1 طريقة الإدخال
    selection = st.radio("اختر طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط درايف المباشر"], horizontal=True)

    # 3.2 منطقة التحميل
    files_input = None
    if selection == "ارفع ملف / ملفات":
        files_input = st.file_uploader("قم بسحب وإفلات الملفات هنا", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        cam_raw = st.camera_input("التقط صورة الفاتورة")
        if cam_raw: files_input = [cam_raw]
    elif selection == "رابط درايف المباشر":
        d_url = st.text_input("أدخل رابط درايف المباشر:")

    st.markdown("---")
    
    # 3.3 اختيار الأعمدة الهيكلي (checkboxes كما في الصورة 19)
    st.markdown("### ⚙️ اختر الأعمدة التي تريد استخراجها:")
    
    # تعريف كافة الأعمدة المحاسبية المعتمدة لشركة أزواد
    all_final_cols = [
        'اسم المورد', 'رقم الفاتورة / عرض السعر', 'الرقم الضريبي للمورد', 'رقم السجل التجاري',
        'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 'الكمية', 
        'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي',
        'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]
    
    # تفعيل الأعمدة الأساسية تلقائياً
    default_on = [
        'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 
        'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي',
        'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]
    
    col1, col2, col3 = st.columns(3)
    chosen_cols = []
    
    with col1:
        if st.checkbox('اسم المورد', value=True): chosen_cols.append('اسم المورد')
        if st.checkbox('رقم الصنف', value=True): chosen_cols.append('رقم الصنف')
        if st.checkbox('المادة/اسم المنتج', value=True): chosen_cols.append('المادة/اسم المنتج')
        if st.checkbox('الوحدة الصغيرة', value=True): chosen_cols.append('الوحدة الصغيرة')
        if st.checkbox('الكمية', value=True): chosen_cols.append('الكمية')
        if st.checkbox('الوحدة الكبيرة', value=True): chosen_cols.append('الوحدة الكبيرة')

    with col2:
        if st.checkbox('معامل التحويل', value=True): chosen_cols.append('معامل التحويل')
        if st.checkbox('الكمية بالوحدة الكبيرة', value=True): chosen_cols.append('الكمية بالوحدة الكبيرة')
        if st.checkbox('السعر الافرادي', value=True): chosen_cols.append('السعر الافرادي')
        if st.checkbox('البيان الأصلي', value=True): chosen_cols.append('البيان الأصلي')
        if st.checkbox('التصنيف الذكي', value=True): chosen_cols.append('التصنيف الذكي')
        if st.checkbox('الضريبة', value=True): chosen_cols.append('الضريبة')

    with col3:
        if st.checkbox('الإجمالي الصافي', value=True): chosen_cols.append('الإجمالي الصافي')
        # الأعمدة المحذوفة سابقاً والتي تم تثبيتها الآن
        if st.checkbox('رقم الفاتورة / عرض السعر', value=False): chosen_cols.append('رقم الفاتورة / عرض السعر')
        if st.checkbox('الرقم الضريبي للمورد', value=False): chosen_cols.append('الرقم الضريبي للمورد')
        if st.checkbox('رقم السجل التجاري', value=False): chosen_cols.append('رقم السجل التجاري')

    st.markdown("<br>", unsafe_allow_html=True)
    
    # 3.4 زر التشغيل
    submit = st.button("🚀 ابدأ استخراج وتحليل البيانات")

# --- التنفيذ (بهدوء وتركيز) ---
if submit and (files_input or (selection == "رابط درايف المباشر" and d_url)):
    final_files = []
    if selection == "رابط درايف المباشر":
        fid = get_drive_id(d_url)
        if fid:
            r = requests.get(f"https://docs.google.com/uc?export=download&id={fid.group(1)}")
            if r.status_code == 200: final_files.append({"name": "drive.jpg", "content": r.content, "type": "image/jpeg"})
    else:
        input_list = [files_input] if not isinstance(files_input, list) else files_input
        for f in input_list: final_files.append({"name": f.name, "content": f.read(), "type": f.type})

    if final_files:
        with st.spinner("جاري استخراج البيانات بدقة متناهية..."):
            try:
                # آلية البحث التلقائي عن الموديل (لتجنب الـ 404)
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target_m = next((m for m in models if "1.5" in m or "flash" in m), models[0])
                model = genai.GenerativeModel(target_m)
                
                all_extracted_data = []
                for f_item in final_files:
                    if "pdf" in f_item["type"]:
                        p = pdf2image.convert_from_bytes(f_item["content"])
                        b = io.BytesIO(); p[0].save(b, format='PNG'); payload = b.getvalue()
                    else: payload = compress_image(f_item["content"])

                    # برومبت محاسبي صارم يغطي كل المتطلبات
                    prompt = f"""
                    أنت محلل بيانات محاسبي خبير لشركة تجزئة. استخرج الأصناف في قائمة JSON تحت مفتاح 'الأصناف'.
                    القواعد الحاسمة:
                    1. 'معامل التحويل': استنتج الرقم فقط من البيان الأصلي (مثلاً 6*2 يعني 12). اكتب الرقم فقط. إذا لم يوجد، ضع 1.
                    2. 'الكمية بالوحدة الكبيرة': عدد الكراتين الموجود في عمود الكمية بالفاتورة.
                    3. 'السعر الافرادي': سعر الكرتون (الوحدة الكبيرة).
                    4. 'المادة/اسم المنتج': اسم صافي تماماً بدون أي أرقام أو أوزان (مثل 500جم، 2*6 كيلو).
                    5. 'الضريبة': استخرج مبلغ الضريبة بالريال لكل صنف، وليس النسبة المئوية.
                    6. 'الإجمالي الصافي': الإجمالي كما هو موضح لكل صنف.
                    7. استخرج بيانات المورد الكاملة (الاسم، السجل التجاري، الرقم الضريبي) ورقم الفاتورة.
                    الحقول المطلوبة تماماً هي: {', '.join(chosen_cols)}
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    data = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                    items = data if isinstance(data, list) else data.get('الأصناف', [])

                    # --- المعالجة الرياضية والبرمجية الاحتياطية (لضمان المنطق) ---
                    for item in items:
                        try:
                            # ضمان أن معامل التحويل رقمي للاستخدام في الحساب
                            raw_factor = re.sub(r'[^0-9.]', '', str(item.get('معامل التحويل', 1)))
                            factor = float(raw_factor) if raw_factor else 1
                            
                            qty_large = float(str(item.get('الكمية بالوحدة الكبيرة', 0)).replace(',', ''))
                            
                            # تطبيق المعادلة الرياضية (الكمية (الكلية) = الكراتين × المعامل) برمجياً
                            item['الكمية'] = qty_large * factor
                            
                            # إعادة صياغة معامل التحويل نصياً للعرض (X حبة / كرتون) كما في الصور
                            item['معامل التحويل'] = f"{int(factor)} حبة / {item.get('الوحدة الكبيرة', 'كرتون')}"
                            
                            # تنظيف احتياطي لاسم المنتج من أي أرقام/أوزان متبقية
                            item['المادة/اسم المنتج'] = re.sub(r'\d+[\*×]\d+.*|[\d\.]+\s*(جرام|جم|كجم|كيلو|لتر|مل)', '', str(item.get('المادة/اسم المنتج', ''))).strip()
                        except: continue
                    all_extracted_data.extend(items)

                if all_extracted_data:
                    df = pd.DataFrame(all_extracted_data)
                    # ضمان ترتيب الأعمدة المختارة
                    final_cols = [c for c in chosen_cols if c in df.columns]
                    df = df[final_cols]
                    
                    st.success("✅ اكتمل الاستخراج والتحليل بنجاح تام!")
                    st.dataframe(df, use_container_width=True)
                    
                    # تصدير إكسل RTL
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد Master')
                        wr.sheets['أزواد Master'].right_to_left()
                    st.download_button("⬇️ تحميل تقرير أزواد الشامل والمنظف", out.getvalue(), "Azwad_Master_Report.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")
