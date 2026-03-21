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

st.markdown("""
    <style>
    .stApp { align-items: center; display: flex; justify-content: center; }
    .main .block-container { max-width: 1250px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.2rem; margin-bottom: 30px; }
    
    div[data-testid="stRadio"] div[role="radiogroup"] { justify-content: center !important; gap: 20px !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #ffffff; padding: 15px 25px !important; border-radius: 12px !important;
        border: 2px solid #e5e7eb !important; font-weight: bold !important;
    }
    
    .stButton > button {
        background-color: #ff4b4b !important; color: white !important;
        font-size: 1.3rem !important; padding: 15px !important;
        border-radius: 10px !important; width: 100% !important;
    }
    </style>
    
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">تم ضبط المورد العربي، وشكل المعامل، وحسابات الطحينة بدقة متناهية</div>
""", unsafe_allow_html=True)

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"❌ خطأ في إعداد المفتاح: {e}")
    st.stop()

def compress_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    out = io.BytesIO(); img.save(out, format='JPEG', quality=85)
    return out.getvalue()

def get_drive_id(url):
    m = re.search(r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)", url)
    return m.group(1) if m else None

with st.container():
    selection = st.radio("اختر طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط درايف المباشر"], horizontal=True)

    files_input = None
    if selection == "ارفع ملف / ملفات":
        files_input = st.file_uploader("قم بسحب وإفلات الملفات هنا", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        cam_raw = st.camera_input("التقط صورة الفاتورة")
        if cam_raw: files_input = [cam_raw]
    elif selection == "رابط درايف المباشر":
        d_url = st.text_input("أدخل رابط درايف المباشر:")

    st.markdown("---")
    
    st.markdown("### ⚙️ اختر الأعمدة (تم تثبيت الترتيب والبيانات المطلوبة):")
    
    # تم تعديل "الكمية" إلى "الكمية بالوحدة الصغيرة" هنا
    all_final_cols = [
        'اسم المورد', 'رقم الفاتورة / عرض السعر', 'الرقم الضريبي للمورد', 'رقم السجل التجاري',
        'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 'الكمية بالوحدة الصغيرة', 
        'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي',
        'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]
    
    default_on = [
        'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة الصغيرة', 
        'الكمية بالوحدة الصغيرة', 'الوحدة الكبيرة', 'معامل التحويل', 'الكمية بالوحدة الكبيرة', 'السعر الافرادي',
        'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]
    
    chosen_cols = st.multiselect(
        "رتب الأعمدة بسحبها أو اختيارها بالترتيب المطلوب:", 
        options=all_final_cols, 
        default=default_on
    )

    st.markdown("<br>", unsafe_allow_html=True)
    submit = st.button("🚀 ابدأ استخراج وتحليل البيانات")

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
        with st.spinner("جاري استخراج البيانات وضبط المنطق الحسابي والمورد العربي..."):
            try:
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target_m = next((m for m in models if "1.5" in m or "flash" in m), models[0])
                model = genai.GenerativeModel(target_m)
                
                all_extracted_data = []
                for f_item in final_files:
                    if "pdf" in f_item["type"]:
                        p = pdf2image.convert_from_bytes(f_item["content"])
                        b = io.BytesIO(); p[0].save(b, format='PNG'); payload = b.getvalue()
                    else: payload = compress_image(f_item["content"])

                    # برومبت صارم جداً يعالج اللغات والأوزان بوضوح
                    prompt = f"""
                    أنت محاسب مستودعات دقيق. استخرج البيانات بصيغة JSON.
                    يجب أن يحتوي الـ JSON على المفاتيح العامة:
                    "اسم المورد" (هام جداً: استخرجه باللغة العربية حصراً كما هو مكتوب في الفاتورة أو الختم، مثال: شركة الخامة الاولية للتجارة)، "رقم الفاتورة / عرض السعر"، "الرقم الضريبي للمورد"، "رقم السجل التجاري".
                    
                    ومفتاح "الأصناف" يحتوي على القائمة. استخرج لكل صنف: {', '.join(chosen_cols)}
                    
                    قواعد حاسمة:
                    1. 'معامل التحويل': استخرج الرقم فقط بناءً على الآتي:
                       - إذا وجد علامة ضرب (مثل "ورق عنب 6*2") -> المعامل هو الرقم الأول (6).
                       - إذا كان الصنف عبوة بوزن كلي (مثل "طحينة 15 كيلو") -> المعامل هو هذا الرقم (15).
                       - إذا لم يوجد تعبئة -> المعامل 1.
                    2. 'الوحدة الصغيرة': إذا كان البيان فيه ضرب (6*2) فالوحدة "حبة" أو "علبة". وإذا كان بوزن كلي (15 كيلو) فالوحدة "كيلو".
                    3. 'الضريبة': مبلغ مالي بالريال (وليس النسبة).
                    4. 'التصنيف الذكي': كلمة واحدة (معلبات، بهارات، صوصات).
                    5. 'المادة/اسم المنتج': اسم نظيف بدون أوزان.
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    res_text = response.text.strip().replace('```json', '').replace('```', '').strip()
                    data = json.loads(res_text)
                    
                    items = data if isinstance(data, list) else data.get('الأصناف', [])
                    
                    general_info = {}
                    if isinstance(data, dict):
                        general_info['اسم المورد'] = data.get('اسم المورد', '')
                        general_info['رقم الفاتورة / عرض السعر'] = data.get('رقم الفاتورة / عرض السعر', '')
                        general_info['الرقم الضريبي للمورد'] = data.get('الرقم الضريبي للمورد', '')
                        general_info['رقم السجل التجاري'] = data.get('رقم السجل التجاري', '')
                    
                    for item in items:
                        for k, v in general_info.items():
                            if k not in item or not str(item.get(k, '')).strip():
                                item[k] = v
                                
                        try:
                            # 1. استخراج المعامل كرقم صافي للحساب
                            raw_factor = re.sub(r'[^0-9.]', '', str(item.get('معامل التحويل', 1)))
                            factor = float(raw_factor) if raw_factor else 1
                            qty_large = float(str(item.get('الكمية بالوحدة الكبيرة', 0)).replace(',', ''))
                            
                            # 2. حساب الكمية بالوحدة الصغيرة
                            item['الكمية بالوحدة الصغيرة'] = qty_large * factor
                            
                            # 3. تنسيق شكل معامل التحويل (الرقم + الوحدة الصغيرة / الوحدة الكبيرة)
                            small_unit = str(item.get('الوحدة الصغيرة', 'حبة')).strip()
                            large_unit = str(item.get('الوحدة الكبيرة', 'كرتون')).strip()
                            item['معامل التحويل'] = f"{int(factor)} {small_unit} / {large_unit}"
                            
                            # 4. تنظيف الاسم
                            item['المادة/اسم المنتج'] = re.sub(r'\d+[\*×]\d+.*|[\d\.]+\s*(جرام|جم|كجم|كيلو|لتر|مل)', '', str(item.get('المادة/اسم المنتج', ''))).strip()
                        except: continue
                        
                    all_extracted_data.extend(items)

                if all_extracted_data:
                    df = pd.DataFrame(all_extracted_data)
                    final_cols = [c for c in chosen_cols if c in df.columns]
                    df = df[final_cols]
                    
                    st.success("✅ تم ضبط المورد العربي، معامل التحويل، وحسابات الطحينة بنجاح!")
                    st.dataframe(df, use_container_width=True)
                    
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد Master')
                        wr.sheets['أزواد Master'].right_to_left()
                    st.download_button("⬇️ تحميل تقرير أزواد الشامل والمنظف", out.getvalue(), "Azwad_Master_Report.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")
