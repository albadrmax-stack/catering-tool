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
    <div class="subtitle-gray">اداة خاصة لفريق ازواد لعمليات الجرد والتصنيع والمشتريات</div>
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
    
    st.markdown("### ⚙️ اختر الأعمدة (تم تنظيف التكرارات ومطابقة الإكسل):")
    
    # القائمة الموحدة والمنظفة نهائياً بناءً على طلبك
    clean_excel_cols = [
        '#', 'اسم الصنف', 'التصنيف', 'رمز المادة', 'سعر المادة (ر.س)', 
        'اسم الشركة / المورد', 'الالرقم الضريبي', 'رقم السجل التجاري', 
        'رقم الهاتف', 'البريد الإلكتروني', 'عنوان المورد', 
        'الوحدة الكبيرة', 'الوحدة الصغيرة', 'معامل التحويل', 
        'وزن الوحدة الصغيرة (كجم)'
    ]
    
    # أي أعمدة إضافية ضرورية للحسابات تظل هنا ولا تظهر للمستخدم إلا إذا طلبها
    optional_cols = ['الكمية المطلوبة', 'الضريبة', 'الإجمالي الصافي', 'رقم الفاتورة / عرض السعر', 'البيان الأصلي']
    
    all_final_cols = clean_excel_cols + optional_cols
    default_on = clean_excel_cols.copy()
    
    chosen_cols = st.multiselect(
        "رتب الأعمدة بسحبها أو اختيارها بالترتيب المطلوب:", 
        options=all_final_cols, 
        default=default_on
    )

    st.markdown("<br>", unsafe_allow_html=True)
    submit = st.button("🚀 ابدأ استخراج وتحليل البيانات")

if submit and (files_input or (selection == "رابط درايف المباشر" and d_url)):
    final_files = []
    input_list = [files_input] if not isinstance(files_input, list) and files_input else files_input
    if selection == "رابط درايف المباشر" and d_url:
        fid = get_drive_id(d_url)
        if fid:
            r = requests.get(f"https://docs.google.com/uc?export=download&id={fid}")
            if r.status_code == 200: final_files.append({"name": "drive.jpg", "content": r.content, "type": "image/jpeg"})
    elif input_list:
        for f in input_list: final_files.append({"name": f.name, "content": f.read(), "type": f.type})

    if final_files:
        with st.spinner("جاري استخراج البيانات وحقن بيانات الترويسة في كل سطر..."):
            try:
                model = genai.GenerativeModel("gemini-1.5-flash")
                
                all_extracted_data = []
                for f_item in final_files:
                    if "pdf" in f_item["type"]:
                        p = pdf2image.convert_from_bytes(f_item["content"])
                        b = io.BytesIO(); p[0].save(b, format='PNG'); payload = b.getvalue()
                    else: payload = compress_image(f_item["content"])

                    # برومبت ذكي يركز على استخراج الترويسة بشكل منفصل ثم حقنها
                    prompt = f"""
                    استخرج البيانات من الفاتورة بصيغة JSON:
                    1. بيانات الترويسة (Header): استخرج بدقة (اسم الشركة / المورد، الرقم الضريبي، رقم السجل التجاري، رقم الهاتف، البريد الإلكتروني، عنوان المورد).
                    2. بيانات الأصناف (Table): استخرج لكل صنف (اسم الصنف، التصنيف، رمز المادة، سعر المادة (ر.س)، الوحدة الكبيرة، الوحدة الصغيرة، الكمية بالوحدة الكبيرة، الكمية بالوحدة الصغيرة، وحدة الوزن الصغيرة، الضريبة، الإجمالي الصافي).
                    
                    قواعد هامة:
                    - 'التصنيف': كلمة واحدة.
                    - 'الوحدة الصغيرة': الأصل "علبة" أو "جالون".
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    res_text = response.text.strip().replace('```json', '').replace('```', '').strip()
                    data = json.loads(res_text)
                    
                    items = data.get('الأصناف', data if isinstance(data, list) else [])
                    
                    # استخراج بيانات الترويسة لضمان حقنها
                    header = {
                        'اسم الشركة / المورد': data.get('اسم الشركة / المورد', ''),
                        'الالرقم الضريبي': data.get('الرقم الضريبي', ''),
                        'رقم السجل التجاري': data.get('رقم السجل التجاري', ''),
                        'رقم الهاتف': data.get('رقم الهاتف', ''),
                        'البريد الإلكتروني': data.get('البريد الإلكتروني', ''),
                        'عنوان المورد': data.get('عنوان المورد', '')
                    }
                    
                    for item in items:
                        # حقن بيانات الترويسة في كل صنف
                        for key, value in header.items():
                            item[key] = value
                            
                        # الحسابات والتحويلات المعتادة
                        try:
                            q_big = float(str(item.get('الكمية بالوحدة الكبيرة', 1)).replace(',', ''))
                            q_small = float(str(item.get('الكمية بالوحدة الصغيرة', 0)).replace(',', ''))
                            u_small = str(item.get('الوحدة الصغيرة', 'علبة'))
                            u_big = str(item.get('الوحدة الكبيرة', 'كرتون'))
                            item['معامل التحويل'] = f"{int(q_big)} {u_small} / {u_big}"
                            
                            # تحويل الوزن (جرام -> كيلو)
                            w_unit = str(item.get('وحدة الوزن الصغيرة', '')).strip()
                            if any(x in w_unit for x in ['جرام', 'جم', 'g']):
                                item['وزن الوحدة الصغيرة (كجم)'] = q_small / 1000
                            else:
                                item['وزن الوحدة الصغيرة (كجم)'] = q_small
                                
                            item['اسم الصنف'] = re.sub(r'\d+[\*×]\d+.*|[\d\.]+\s*(جرام|جم|كجم|كيلو|لتر|مل)', '', str(item.get('اسم الصنف', ''))).strip()
                        except: pass
                        
                    all_extracted_data.extend(items)

                if all_extracted_data:
                    df = pd.DataFrame(all_extracted_data)
                    if '#' in chosen_cols: df['#'] = range(1, len(df) + 1)
                    
                    # الفلترة النهائية بناء على اختيار المستخدم المنظف
                    final_df = df[[c for c in chosen_cols if c in df.columns]]
                    
                    st.success("✅ تم تنظيف الأعمدة وحقن بيانات المورد بنجاح!")
                    st.dataframe(final_df, use_container_width=True)
                    
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        final_df.to_excel(wr, index=False, sheet_name='Azwad_Report')
                        wr.sheets['Azwad_Report'].right_to_left()
                    st.download_button("⬇️ تحميل التقرير النهائي المنظف", out.getvalue(), "Azwad_Clean_Report.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")
