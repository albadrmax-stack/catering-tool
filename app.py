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
    <div style="text-align: center; color: gray;">نسخة معالجة الصور الضخمة (JPG)</div>
""", unsafe_allow_html=True)

# دالة ضغط الصور المحسنة (للتعامل مع الصور الضخمة)
def process_invoice_image(image_bytes):
    # فتح الصورة باستخدام PIL
    img = Image.open(io.BytesIO(image_bytes))
    
    # 1. تحويل الـ PNG إلى JPG (لتقليل الحجم بشكل كبير)
    if img.mode != 'RGB':
        img = img.convert('RGB')
        
    # 2. تغيير الحجم الاحتياطي (إذا كانت دقة الصورة خيالية، نقوم بتصغيرها قليلاً)
    # الأبعاد القصوى المقترحة هي 2000 بكسل لأطول ضلع، للحفاظ على الوضوح
    max_size = 2000
    w, h = img.size
    if w > max_size or h > max_size:
        # حساب نسبة التصغير مع الحفاظ على النسبة
        scale = max_size / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # 3. حفظ الصورة كـ JPEG مع جودة محسنة
    out = io.BytesIO()
    # جودة 80 تعتبر توازناً مثالياً بين الوضوح والحجم
    img.save(out, format='JPEG', quality=80)
    return out.getvalue()

# إعداد الـ API
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ خطأ: لم يتم العثور على API KEY في الإعدادات.")
    st.stop()

# واجهة الاختيارات
selection = st.radio("طريقة الإدخال", ["ارفع ملف / ملفات", "التقاط صورة / صور", "رابط قوقل درايف"], horizontal=True)

all_options = [
    'اسم المورد', 'رقم الفاتورة / عرض السعر', 'رقم الصنف', 'المادة/اسم المنتج', 
    'الوحدة الصغيرة', 'الكمية', 'الوحدة الكبيرة', 'معامل التحويل', 
    'الكمية بالوحدة الكبيرة', 'السعر الافرادي', 'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
]

chosen_cols = st.multiselect("اختر ورتب الأعمدة المطلوبة:", options=all_options, default=all_options[:9])

with st.form("azwad_image_fix_form"):
    files_input = None
    drive_url = ""
    
    if selection == "ارفع ملف / ملفات":
        files_input = st.file_uploader("اسحب الملفات هنا", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    elif selection == "التقاط صورة / صور":
        files_input = st.camera_input("التقط صورة")
    elif selection == "رابط قوقل درايف":
        drive_url = st.text_input("رابط درايف المباشر")

    submit = st.form_submit_button("🚀 ابدأ التحليل الآن")

# التنفيذ
if submit:
    if not files_input and not drive_url:
        st.warning("⚠️ الرجاء اختيار ملف أو وضع رابط أولاً.")
    else:
        results = []
        status_box = st.empty()
        
        try:
            # 1. صيد الموديل
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_m = next((m for m in models if "1.5" in m or "flash" in m), models[0])
            model = genai.GenerativeModel(target_m)

            # 2. تجهيز الملفات
            final_list = []
            # ... منطق درايف ... (كما هو)

            # تجهيز الملفات المرفوعة
            input_list = [files_input] if not isinstance(files_input, list) else files_input
            for f in input_list:
                final_list.append({"name": f.name, "content": f.read(), "type": f.type})

            # 3. المعالجة
            for f_item in final_list:
                status_box.info(f"⏳ جاري تجهيز الملف للتحليل: {f_item['name']}...")
                
                # استخدام دالة معالجة الصور المحسنة (لJPG و PNG الكبيرة)
                if "pdf" in f_item["type"]:
                    # منطق PDF يحتاج لPoppler (الرسالة السابقة)
                    pass
                else:
                    payload = process_invoice_image(f_item["content"])

                status_box.info(f"🧠 الذكاء الاصطناعي يحلل الفاتورة...")
                
                prompt = f"""
                حلل الفاتورة واستخرج الأصناف في JSON. المطلوب: {', '.join(chosen_cols)}.
                اسم المنتج يجب أن يكون بدون أرقام أو أوزان. الضريبة مبلغ مالي. 
                الكمية الإجمالية = الكرتون × معامل التحويل.
                """
                
                response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                data_txt = response.text.strip().replace('```json', '').replace('```', '')
                data = json.loads(data_txt)
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
                status_box.error("❌ لم نتمكن من استخراج بيانات. الصورة قد تكون غير واضحة للذكاء.")

        except Exception as e:
            status_box.error(f"❌ حدث خطأ تقني: {e}")
