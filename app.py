import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json

# دالة ذكية لتصغير حجم الصورة مع الحفاظ على جودة النص (لتسريع المعالجة)
def compress_image(image_bytes, quality=70):
    """تصغير الصورة لتسريع المعالجة."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality)
    return output.getvalue()

# 1. عنوان الموقع بالعربية
st.set_page_config(page_title="أداة أزواد الذكية لمسح المستندات والصور وتحويلها اكسل", layout="wide")
st.title("أداة أزواد الذكية لمسح المستندات والصور وتحويلها اكسل")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("❌ لم يتم العثور على المفتاح السري.")
    st.stop()

# --- 2. تصميم الأزرار الملونة والمنفصلة بالعربية ---
st.markdown("### ✨ خيارات الرفع (اختر واحداً للبدء):")

# قائمة لتجميع كل الملفات المرفوعة من أي خيار
uploaded_files = []

# استخدام pills لإنشاء أزرار اختيار كبيرة وملونة
selection = st.pills(
    label="اختر طريقة الرفع:",
    options=["الرفع", "الالتقاط"],
    icons=["📁", "📸"],
    format_func=lambda x: "ارفع الملف / الملفات" if x == "الرفع" else "التقاط صورة / صور",
    label_visibility="collapsed"
)

# تخصيص ألوان الأزرار باستخدام CSS (أحمر للرفع، كحلي للالتقاط)
st.markdown("""
<style>
/* لون زر الرفع (الأحمر) */
[data-testid="stPills"] button:nth-child(1) {
    background-color: #ff4b4b !important;
    color: white !important;
    border: 2px solid #ff4b4b !important;
}
[data-testid="stPills"] button:nth-child(1):hover {
    background-color: #ff3333 !important;
}
/* لون زر الالتقاط (الكحلي) */
[data-testid="stPills"] button:nth-child(2) {
    background-color: #1a2a40 !important;
    color: white !important;
    border: 2px solid #1a2a40 !important;
}
[data-testid="stPills"] button:nth-child(2):hover {
    background-color: #2a3a50 !important;
}
/* تنسيق الأزرار لتكون كبيرة وواضحة */
[data-testid="stPills"] button {
    font-size: 1.2rem !important;
    padding: 10px 20px !important;
}
</style>
""", unsafe_allow_html=True)

# تفعيل الخيار المختار
if selection == "الرفع":
    # 3. قبول رفع متعدد الملفات
    file_uploads = st.file_uploader("ارفع الملف / الملفات (PDF/صور)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    if file_uploads:
        uploaded_files.extend(file_uploads)

elif selection == "الالتقاط":
    # 4. الكاميرا لا تعمل تلقائياً، وتدعم التقاط صور متعددة
    camera_captures = st.camera_input("التقاط صورة / صور مباشرة للكاميرا", accept_multiple_files=True)
    if camera_captures:
        uploaded_files.extend(camera_captures)

if uploaded_files:
    with st.spinner("جاري الاتصال بجوجل وفحص المحركات... 🔍"):
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = None
            for m in available_models:
                if "1.5" in m or "vision" in m:
                    target_model = m
                    break
            if not target_model and available_models:
                target_model = available_models[0]
        except Exception as e:
            st.error(f"حدث خطأ أثناء الاتصال بجوجل: {e}")
            st.stop()

    if target_model:
        model = genai.GenerativeModel(target_model)
        
        all_invoices_data = []
        
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            with st.spinner(f'جاري معالجة وتحليل فاتورة: {file_name}...'):
                try:
                    file_content = uploaded_file.read()
                    
                    if uploaded_file.type == "application/pdf":
                        images = pdf2image.convert_from_bytes(file_content)
                        img = images[0]
                        img_bytes = io.BytesIO()
                        img.save(img_bytes, format='PNG')
                        img_to_send = img_bytes.getvalue()

                    else:
                        # تصغير الصورة تلقائياً لتسريع المعالجة
                        st.info(f"تنبيه: حجم الملف الأصلي: {len(file_content)/1024/1024:.2f} ميجا. جاري تصغير الحجم تلقائياً لتسريع المعالجة...")
                        compressed_content = compress_image(file_content)
                        st.success(f"✅ تم تصغير حجم الملف إلى: {len(compressed_content)/1024/1024:.2f} ميجا.")
                        img_to_send = compressed_content

                    # الطلب السحري لفصل البيانات بذكاء
                    prompt = """
                    أنت خبير في قراءة وتحليل فواتير الإعاشة العربية.
                    حلل صورة الفاتورة بدقة، واستخرج 'اسم المورد' (اسم الشركة البائعة من أعلى الفاتورة).
                    استخرج الأصناف في تنسيق JSON دقيق يحتوي على قائمة 'الأصناف'، وكل صنف يجب أن يحتوي على الحقول التالية:
                    'اسم_المورد'
                    'رقم_الصنف'
                    'المادة' (اسم المنتج، مثلاً 'ورق عنب')
                    'الوحدة_الصغيرة' (استخرج النص فقط: مثلاً 'كيلو')
                    'وزن_الحبة' (استخرج الرقم فقط: مثلاً '2')
                    'معامل_التحويل_في_الكرتون' (مثلاً '6')
                    'الوحدة_الرئيسية' (مثلاً 'كرتون')
                    'الكمية_بالفاتورة'
                    'السعر'

                    أريد النتيجة كـ JSON خام فقط كإجابة نصية، بدون كلام جانبي أو علامات Markdown (لا تستخدم ```json).
                    """
                    
                    response = model.generate_content([prompt, img_to_send])
                    text_result = response.text.strip()

                    try:
                        cleaned_json_text = text_result.replace('```json', '').replace('```', '').strip()
                        data_json = json.loads(cleaned_json_text)
                        
                        if 'الأصناف' in data_json:
                            all_invoices_data.extend(data_json['الأصناف'])
                            st.success(f"✅ تم سحب البيانات بنجاح من: {file_name}")
                        else:
                            st.warning(f"⚠️ لم نتمكن من استخراج جدول من: {file_name}")

                    except json.JSONDecodeError:
                        st.warning(f"⚠️ لم يستطع الذكاء الاصطناعي تنسيق بيانات الفاتورة: {file_name}")
                    
                except Exception as e:
                    st.error(f"⚠️ حدث خطأ أثناء قراءة {file_name}: {str(e)}")

        if all_invoices_data:
            st.markdown("### 📊 الجدول النهائي المجمع لجميع الفواتير:")
            df = pd.DataFrame(all_invoices_data)
            
            # إعادة تسمية الأعمدة
            excel_columns_map = {
                'اسم_المورد': 'اسم المورد',
                'رقم_الصنف': 'رقم الصنف',
                'المادة': 'المادة/اسم المنتج',
                'الوحدة_الصغيرة': 'الوحدة',
                'وزن_الحبة': 'وزن الحبة',
                'معامل_التحويل_في_الكرتون': 'معامل التحويل (حبة/كرتون)',
                'الوحدة_الرئيسية': 'الوحدة الكبيرة',
                'الكمية_بالفاتورة': 'الكمية (بالكرتون)',
                'السعر': 'السعر الإجمالي'
            }
            df.rename(columns=excel_columns_map, inplace=True)
            
            # ترتيب الأعمدة
            cols_order = ['اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الوحدة', 'وزن الحبة', 'معامل التحويل (حبة/كرتون)', 'الوحدة الكبيرة', 'الكمية (بالكرتون)', 'السعر الإجمالي']
            existing_cols = [c for c in cols_order if c in df.columns]
            df = df[existing_cols]
            
            st.dataframe(df, use_container_width=True)

            # إنشاء ملف الإكسل
            excel_io = io.BytesIO()
            with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='فواتير_أزواد')
                
                # الوصول لخصائص الشيت وقلب الاتجاه ليكون من اليمين لليسار
                worksheet = writer.sheets['فواتير_أزواد']
                worksheet.right_to_left()
            
            # تحميل ملف الإكسل
            st.download_button(
                label="تحميل اكسل",
                data=excel_io.getvalue(),
                file_name="فواتير_أزواد_المجمعة.xlsx",
                mime="application/vnd.ms-excel"
            )
    else:
        st.error("❌ لم نتمكن من العثور على محرك مناسب في حسابك.")
