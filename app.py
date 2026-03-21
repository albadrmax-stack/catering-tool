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

# القائمة الكاملة للأعمدة المتاحة
all_cols_options = [
    'اسم المورد', 'رقم الفاتورة / عرض السعر', 'رقم الصنف', 'المادة/اسم المنتج', 
    'الوحدة الصغيرة', 'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 
    'الكمية بالوحدة الكبيرة', 'السعر الافرادي', 'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
]

st.markdown("""
    <style>
    .stApp { align-items: center; display: flex; justify-content: center; }
    .main .block-container { max-width: 1150px; padding-top: 2rem; text-align: center; }
    .title-red { color: #ff4b4b; font-size: 3rem; font-weight: 900; margin-bottom: 0px; }
    .stButton > button { background-color: #ff4b4b !important; color: white !important; width: 100% !important; border-radius: 10px !important; font-size: 1.2rem; height: 3em; }
    </style>
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div style="text-align: center; color: gray; margin-bottom: 20px;">نظام استخراج وتحليل الفواتير - النسخة المعتمدة المستقرة</div>
""", unsafe_allow_html=True)

# دالة ضغط الصور
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

# --- بداية نموذج الإدخال ---
with st.container():
    selection = st.radio("طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"], horizontal=True)

    # 1. منطقة رفع الملفات
    files_input = None
    if selection == "ارفع ملف / ملفات":
        files_input = st.file_uploader("قم بسحب وإفلات الملفات هنا", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        cam_raw = st.camera_input("التقط صورة الفاتورة")
        if cam_raw: files_input = [cam_raw]
    elif selection == "رابط قوقل درايف":
        d_url = st.text_input("أدخل رابط درايف المباشر:")

    st.markdown("---")
    
    # 2. سطر اختيار وترتيب الأعمدة (تم نقله هنا تحت أمر الرفع)
    st.markdown("### ⚙️ اختر ورتب الأعمدة التي تريد استخراجها:")
    chosen_cols = st.multiselect(
        "اسحب الأسماء أو اخترها بالترتيب المطلوب (من اليمين لليسار):", 
        options=all_cols_options, 
        default=all_cols_options
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. زر البدء
    submit = st.button("🚀 ابدأ الاستخراج والتحليل الآن")

if submit:
    final_files = []
    # منطق جلب الملفات
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
        with st.spinner("جاري تحليل البيانات واستخراج الأعمدة المختارة..."):
            try:
                model = genai.GenerativeModel("gemini-1.5-flash")
                all_extracted = []
                
                for f_item in final_files:
                    if "pdf" in f_item["type"]:
                        pages = pdf2image.convert_from_bytes(f_item["content"])
                        b = io.BytesIO(); pages[0].save(b, format='PNG'); payload = b.getvalue()
                    else:
                        payload = compress_image(f_item["content"])

                    prompt = f"""
                    استخرج البيانات من الفاتورة بدقة عالية.
                    يجب أن يحتوي الـ JSON على الحقول التالية فقط وبالترتيب: {', '.join(chosen_cols)}
                    قواعد هامة:
                    - 'المادة/اسم المنتج': استخرج الاسم فقط (بدون أوزان أو أرقام).
                    - 'معامل التحويل': استنتجه من سياق الصنف (مثلاً كرتون فيه 6 حبات -> المعامل 6).
                    - 'الكمية بالوحدة الكبيرة': إذا كانت الوحدة كرتون، ضع الكمية هنا.
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    res_text = response.text.strip().replace('```json', '').replace('```', '')
                    data = json.loads(res_text)
                    items = data if isinstance(data, list) else data.get('الأصناف', [])
                    all_extracted.extend(items)

                if all_extracted:
                    df = pd.DataFrame(all_extracted)
                    # إعادة ترتيب الأعمدة حسب اختيار المستخدم
                    df = df[[c for c in chosen_cols if c in df.columns]]
                    
                    st.success("✅ تم الاستخراج بنجاح!")
                    st.dataframe(df, use_container_width=True)
                    
                    # تحويل لإكسل
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد')
                        wr.sheets['أزواد'].right_to_left()
                    st.download_button("⬇️ تحميل تقرير أزواد الشامل (Excel)", out.getvalue(), "Azwad_Analysis.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ تقني: {e}")
