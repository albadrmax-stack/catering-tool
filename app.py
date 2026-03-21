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
    .main .block-container { max-width: 1200px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3rem; font-weight: 900; margin-bottom: 0px; }
    .subtitle-gray { color: #6b7280; font-size: 1.1rem; margin-bottom: 30px; }
    .stButton > button { background-color: #ff4b4b !important; color: white !important; width: 100% !important; border-radius: 10px !important; }
    </style>
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div class="subtitle-gray">إصدار التصحيح المنطقي والحسابي - الربط بين الكرتون والحبة</div>
""", unsafe_allow_html=True)

def compress_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    out = io.BytesIO(); img.save(out, format='JPEG', quality=85)
    return out.getvalue()

def get_drive_id(url):
    m = re.search(r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)", url)
    return m.group(1) if m else None

with st.form("azwad_logic_fix_form"):
    selection = st.radio("طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"], horizontal=True)
    files_input = None
    if selection == "ارفع ملف / ملفات":
        files_input = st.file_uploader("", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        cam_raw = st.camera_input("")
        if cam_raw: files_input = [cam_raw]
    elif selection == "رابط قوقل درايف":
        d_url = st.text_input("رابط درايف:")

    all_options = st.session_state.cols_order
    chosen_cols = st.multiselect("رتب الأعمدة المختارة:", options=all_options, default=st.session_state.cols_order)
    submit = st.form_submit_button("🚀 ابدأ الاستخراج والحساب المنطقي")

if submit and (files_input or (selection == "رابط قوقل درايف" and d_url)):
    final_files = []
    if selection == "رابط قوقل درايف":
        fid = get_drive_id(d_url)
        if fid:
            r = requests.get(f"https://docs.google.com/uc?export=download&id={fid}")
            if r.status_code == 200: final_files.append({"name": "drive.jpg", "content": r.content, "type": "image/jpeg"})
    else:
        for f in files_input: final_files.append({"name": f.name, "content": f.read(), "type": f.type})

    if final_files:
        with st.spinner("جاري معالجة المنطق الرياضي للفاتورة..."):
            try:
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target_m = next((m for m in models if "1.5" in m or "flash" in m), models[0])
                model = genai.GenerativeModel(target_m)
                
                results = []
                for f_item in final_files:
                    if "pdf" in f_item["type"]:
                        p = pdf2image.convert_from_bytes(f_item["content"]); b = io.BytesIO(); p[0].save(b, format='PNG'); payload = b.getvalue()
                    else: payload = compress_image(f_item["content"])

                    prompt = """
                    أنت محلل بيانات مالي دقيق. استخرج البيانات من الفاتورة في JSON.
                    
                    المنطق المطلوب (حرج جداً):
                    1. 'الكمية بالوحدة الكبيرة': هي عدد الكراتين/الشدات المكتوب في عمود الكمية بالفاتورة.
                    2. 'معامل التحويل': استخرجه من الوصف (مثلاً 2*6 يعني 12، أو 6*2500 يعني 6). استخرج الرقم فقط.
                    3. 'السعر الافرادي': هو سعر الوحدة الكبيرة (الكرتون).
                    4. 'الإجمالي الصافي': (الكمية بالوحدة الكبيرة × السعر الافرادي).
                    5. 'الضريبة': مبلغ الضريبة الفعلي بالريال.
                    6. 'المادة/اسم المنتج': اسم صافي بدون أرقام أو أوزان.
                    
                    الحقول: [اسم المورد، رقم الفاتورة / عرض السعر، رقم الصنف، المادة/اسم المنتج، الوحدة الصغيرة، الوحدة الكبيرة، معامل التحويل، الكمية بالوحدة الكبيرة، السعر الافرادي، البيان الأصلي، التصنيف الذكي، الضريبة، الإجمالي الصافي]
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    data = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                    items = data if isinstance(data, list) else data.get('الأصناف', [])

                    # --- المعالجة الرياضية البرمجية (لضمان المنطق) ---
                    for item in items:
                        try:
                            # تنظيف الأرقام
                            qty_large = float(str(item.get('الكمية بالوحدة الكبيرة', 0)).replace(',', ''))
                            factor = float(str(item.get('معامل التحويل', 1)).replace(',', ''))
                            price = float(str(item.get('السعر الافرادي', 0)).replace(',', ''))
                            
                            # العملية الحسابية الصحيحة
                            item['الكمية'] = qty_large * factor # الكمية الصغيرة الإجمالية
                            item['معامل التحويل'] = f"{int(factor)} حبة / {item.get('الوحدة الكبيرة', 'كرتون')}"
                            
                            # تنظيف اسم المنتج
                            item['المادة/اسم المنتج'] = re.sub(r'\d+[\*×]\d+.*|[\d\.]+\s*(جرام|جم|كجم|كيلو|لتر|مل)', '', str(item.get('المادة/اسم المنتج', ''))).strip()
                        except:
                            continue

                    results.extend(items)

                if results:
                    df = pd.DataFrame(results)
                    df = df[[c for c in chosen_cols if c in df.columns]]
                    st.success("✅ تم تصحيح المنطق الرياضي والحسابات!")
                    st.dataframe(df, use_container_width=True)
                    
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد'); wr.sheets['أزواد'].right_to_left()
                    st.download_button("⬇️ تحميل التقرير المنطقي المصحح", out.getvalue(), "Azwad_Corrected_Logic.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")
