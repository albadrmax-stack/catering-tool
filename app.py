import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json

# 1. تعديل عنوان الموقع والصفحة كما طلبت
st.set_page_config(page_title="أداة أزواد الذكية لمسح المستندات والصور وتحويلها اكسل", layout="wide")
st.title("أداة أزواد الذكية لمسح المستندات والصور وتحويلها اكسل")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("❌ لم يتم العثور على المفتاح السري.")
    st.stop()

uploaded_files = st.file_uploader("ارفع فواتيرك (PDF أو صور)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

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
        
        # قائمة لتجميع كل الأصناف من كل الفواتير المرفوعة في جدول واحد
        all_invoices_data = []
        
        for uploaded_file in uploaded_files:
            with st.spinner(f'جاري قراءة وتحليل فاتورة: {uploaded_file.name}...'):
                try:
                    if uploaded_file.type == "application/pdf":
                        images = pdf2image.convert_from_bytes(uploaded_file.read())
                        img = images[0]
                    else:
                        img = Image.open(uploaded_file)

                    # 2. تعديل الطلب السحري لإضافة (اسم المورد) في كل صنف
                    prompt = """
                    أنت خبير في قراءة وتحليل فواتير الإعاشة العربية.
                    حلل صورة الفاتورة بدقة، واستخرج 'اسم المورد' (اسم الشركة البائعة من أعلى الفاتورة).
                    استخرج الأصناف في تنسيق JSON دقيق يحتوي على قائمة 'الأصناف'، وكل صنف يجب أن يحتوي على الحقول التالية:
                    'اسم_المورد' (اكتب اسم الشركة التي استخرجتها هنا ليتكرر مع كل صنف)
                    'رقم_الصنف'
                    'المادة' (اسم المنتج، مثلاً 'ورق عنب'، مفصولاً عن الأرقام)
                    'تفاصيل_الوزن' (مثلاً '2 كيلو' من '2 ك')
                    'معامل_التحويل_في_الكرتون' (مثلاً '6')
                    'الوحدة_الرئيسية' (مثلاً 'كرتون')
                    'الكمية_بالفاتورة'
                    'السعر'

                    أريد النتيجة كـ JSON خام فقط كإجابة نصية، بدون كلام جانبي أو علامات Markdown (لا تستخدم ```json).
                    """
                    
                    response = model.generate_content([prompt, img])
                    text_result = response.text.strip()

                    try:
                        cleaned_json_text = text_result.replace('```json', '').replace('```', '').strip()
                        data_json = json.loads(cleaned_json_text)
                        
                        if 'الأصناف' in data_json:
                            # إضافة أصناف هذه الفاتورة إلى القائمة الكبرى
                            all_invoices_data.extend(data_json['الأصناف'])
                            st.success(f"✅ تم سحب البيانات بنجاح من: {uploaded_file.name}")
                        else:
                            st.warning(f"⚠️ لم نتمكن من استخراج جدول من: {uploaded_file.name}")

                    except json.JSONDecodeError:
                        st.warning(f"⚠️ لم يستطع الذكاء الاصطناعي تنسيق بيانات الفاتورة: {uploaded_file.name}")
                    
                except Exception as e:
                    st.error(f"⚠️ حدث خطأ أثناء قراءة {uploaded_file.name}: {str(e)}")

        # بعد الانتهاء من كل الفواتير، نقوم بإنشاء الجدول الموحد
        if all_invoices_data:
            st.markdown("### 📊 الجدول النهائي المجمع لجميع الفواتير:")
            df = pd.DataFrame(all_invoices_data)
            
            # إعادة تسمية الأعمدة
            excel_columns_map = {
                'اسم_المورد': 'اسم المورد',
                'رقم_الصنف': 'رقم الصنف',
                'المادة': 'المادة/اسم المنتج',
                'تفاصيل_الوزن': 'وزن حبة/الوحدة الصغيرة',
                'معامل_التحويل_في_الكرتون': 'معامل التحويل (حبة/كرتون)',
                'الوحدة_الرئيسية': 'الوحدة الكبيرة',
                'الكمية_بالفاتورة': 'الكمية (بالكرتون)',
                'السعر': 'السعر الإجمالي'
            }
            df.rename(columns=excel_columns_map, inplace=True)
            
            # ترتيب الأعمدة لضمان أن اسم المورد يظهر أولاً
            cols_order = ['اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'وزن حبة/الوحدة الصغيرة', 'معامل التحويل (حبة/كرتون)', 'الوحدة الكبيرة', 'الكمية (بالكرتون)', 'السعر الإجمالي']
            existing_cols = [c for c in cols_order if c in df.columns]
            df = df[existing_cols]
            
            # عرض الجدول
            st.dataframe(df, use_container_width=True)

            # إنشاء ملف الإكسل
            excel_io = io.BytesIO()
            with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='الفواتير_المجمعة')
            
            # 3. تعديل اسم الزر كما طلبت
            st.download_button(
                label="تحميل اكسل",
                data=excel_io.getvalue(),
                file_name="فواتير_أزواد_المجمعة.xlsx",
                mime="application/vnd.ms-excel"
            )
    else:
        st.error("❌ لم نتمكن من العثور على محرك مناسب في حسابك.")
