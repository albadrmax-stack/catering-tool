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

# التنسيق البصري
st.markdown("""
    <style>
    .title-red { color: #ff4b4b; font-size: 3rem; font-weight: 900; text-align: center; }
    .stButton > button { background-color: #ff4b4b !important; color: white !important; width: 100% !important; }
    </style>
    <div class="title-red">أداة شركة أزواد الذكية</div>
    <div style="text-align: center; color: gray;">نظام التحليل المطور - نسخة تتبع الأعطال</div>
""", unsafe_allow_html=True)

# دالة ضغط الصور
def compress_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    out = io.BytesIO(); img.save(out, format='JPEG', quality=80)
    return out.getvalue()

# إعداد الـ API
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ خطأ: لم يتم العثور على API KEY في الإعدادات.")
    st.stop()

# --- واجهة الاختيارات (خارج الفورم لضمان التفاعل) ---
selection = st.radio("طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"], horizontal=True)

all_options = [
    'اسم المورد', 'رقم الفاتورة / عرض السعر', 'رقم الصنف', 'المادة/اسم المنتج', 
    'الوحدة الصغيرة', 'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 
    'الكمية بالوحدة الكبيرة', 'السعر الافرادي', 'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
]

chosen_cols = st.multiselect("اختر ورتب الأعمدة المطلوبة:", options=all_options, default=all_options[:9])

# --- نموذج التحميل والبدء ---
with st.form("extraction_form"):
    files_input = None
    drive_url = ""
    
    if selection == "ارفع ملف / ملفات":
        files_input = st.file_uploader("اسحب الملفات هنا", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        files_input = st.camera_input("التقط صورة")
    elif selection == "رابط قوقل درايف":
        drive_url = st.text_input("رابط درايف المباشر")

    submit = st.form_submit_button("🚀 ابدأ التحليل الآن")

# --- التنفيذ ---
if submit:
    if not files_input and not drive_url:
        st.warning("⚠️ الرجاء اختيار ملف أو وضع رابط أولاً.")
    else:
        results = []
        status_box = st.empty() # مكان لعرض الحالة
        
        try:
            # 1. صيد الموديل
            status_box.info("🔍 جاري الاتصال بخوادم جوجل...")
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_m = next((m for m in models if "1.5" in m or "flash" in m), models[0])
            model = genai.GenerativeModel(target_m)

            # 2. تجهيز الملفات
            final_list = []
            if selection == "رابط قوقل درايف" and drive_url:
                fid = re.search(r"(?:id=|\/d\/|folders\/)([a-zA-Z0-9-_]+)", drive_url)
                if fid:
                    r = requests.get(f"https://docs.google.com/uc?export=download&id={fid.group(1)}")
                    final_list.append({"name": "drive_file.jpg", "content": r.content, "type": "image/jpeg"})
            else:
                input_list = [files_input] if not isinstance(files_input, list) else files_input
                for f in input_list:
                    final_list.append({"name": f.name, "content": f.read(), "type": f.type})

            # 3. المعالجة
            for f_item in final_list:
                status_box.info(f"⏳ جاري قراءة الملف: {f_item['name']}...")
                
                if "pdf" in f_item["type"]:
                    try:
                        p = pdf2image.convert_from_bytes(f_item["content"])
                        b = io.BytesIO(); p[0].save(b, format='PNG'); payload = b.getvalue()
                    except Exception as pdf_err:
                        st.error(f"❌ خطأ في تحويل PDF (ربما تنقص مكتبة Poppler): {pdf_err}")
                        continue
                else:
                    payload = compress_image(f_item["content"])

                status_box.info(f"🧠 الذكاء الاصطناعي يحلل البيانات الآن...")
                
                prompt = f"""
                حلل الفاتورة واستخرج الأصناف في JSON. 
                المطلوب: {', '.join(chosen_cols)}.
                ملاحظة: المادة/اسم المنتج يجب أن يكون بدون أرقام أو أوزان. 
                الضريبة هي المبلغ المالي.
                الكمية الإجمالية = الكمية بالوحدة الكبيرة × معامل التحويل.
                """
                
                response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                data = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                items = data if isinstance(data, list) else data.get('الأصناف', [])
                results.extend(items)

            if results:
                status_box.success("✅ اكتمل التحليل!")
                df = pd.DataFrame(results)
                df = df[[c for c in chosen_cols if c in df.columns]]
                st.dataframe(df, use_container_width=True)
                
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                    df.to_excel(wr, index=False, sheet_name='أزواد')
                    wr.sheets['أزواد'].right_to_left()
                st.download_button("⬇️ تحميل التقرير النهائي", out.getvalue(), "Azwad_Report.xlsx")
            else:
                status_box.error("❌ لم نتمكن من استخراج بيانات. تأكد من وضوح الصورة.")

        except Exception as e:
            status_box.error(f"❌ حدث خطأ تقني: {e}")
