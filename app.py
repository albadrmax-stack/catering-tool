import streamlit as st
import pandas as pd
import google.generativeai as genai
import io
from PIL import Image
import pdf2image
import json # مكتبة جديدة مطلوبة

# إعداد واجهة البرنامج
st.set_page_config(page_title="مستخرج فواتير الإعاشة الذكي", layout="wide")
st.title("🤖 مستخرج الفواتير المطور (بذكاء Gemini والفصل الذكي)")

# جلب المفتاح السري
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
        st.success(f"✅ تم الاتصال بالمحرك: {target_model}")
        model = genai.GenerativeModel(target_model)
        
        for uploaded_file in uploaded_files:
            with st.spinner(f'جاري قراءة وتحليل الفصل الذكي لـ {uploaded_file.name}...'):
                try:
                    # تحويل الملف إلى صورة
                    if uploaded_file.type == "application/pdf":
                        images = pdf2image.convert_from_bytes(uploaded_file.read())
                        img = images[0]
                    else:
                        img = Image.open(uploaded_file)

                    # --- التحديث الجوهري: "الطلب السحري المحسن للفصل الذكي" ---
                    prompt = """
                    أنت خبير في قراءة وتحليل فواتير الإعاشة العربية.
                    حلل صورة الفاتورة واستخرج الأصناف في تنسيق JSON دقيق يحتوي على قائمة 'الأصناف'، وكل صنف يحتوي على الحقول التالية:
                    'رقم_الصنف'
                    'المادة' (اسم المنتج، مثلاً 'ورق عنب'، مفصولاً عن الأرقام)
                    'تفاصيل_الوزن' (مثلاً '2 كيلو' من '2 ك')
                    'معامل_التحويل_في_الكرتون' (مثلاً '6')
                    'الوحدة_الرئيسية' (مثلاً 'كرتون')
                    'الكمية_بالفاتورة' (الكرتونات)
                    'السعر' (الإجمالي بالفاتورة).

                    قم بتحليل الأنماط المختلطة مثل 'ورق عنب 2 ك* 6' بذكاء شديد لفصل اسم المادة عن تفاصيل التعبئة.
                    أريد النتيجة كـ JSON خام فقط كإجابة نصية، بدون كلام جانبي أو علامات Markdown (لا تستخدم ```json).
                    """
                    
                    response = model.generate_content([prompt, img])
                    
                    # --- كود تحويل النتيجة لجدول إكسل ---
                    st.markdown(f"### بيانات الفاتورة (تم الفصل الذكي) ✅: {uploaded_file.name}")
                    text_result = response.text.strip()

                    try:
                        # تنظيف النتيجة لو Gemini وضعها في مارك داون رغماً عنا
                        cleaned_json_text = text_result.replace('```json', '').replace('```', '').strip()
                        data_json = json.loads(cleaned_json_text)
                        
                        if 'الأصناف' in data_json:
                            # تحويل الـ JSON إلى Pandas DataFrame
                            df = pd.DataFrame(data_json['الأصناف'])
                            
                            # إعادة ترتيب وتسمية الأعمدة لتناسب الإكسل
                            excel_columns_map = {
                                'رقم_الصنف': 'رقم الصنف',
                                'المادة': 'المادة/اسم المنتج',
                                'تفاصيل_الوزن': 'وزن حبة/الوحدة الصغيرة',
                                'معامل_التحويل_في_الكرتون': 'معامل التحويل (حبة/كرتون)',
                                'الوحدة_الرئيسية': 'الوحدة الكبيرة',
                                'الكمية_بالفاتورة': 'الكمية (بالكرتون)',
                                'السعر': 'السعر الإجمالي'
                            }
                            df.rename(columns=excel_columns_map, inplace=True)
                            
                            # عرض الجدول النهائي مفصولاً بذكاء في الواجهة
                            st.dataframe(df, use_container_width=True)

                            # إنشاء ملف الإكسل في الذاكرة
                            excel_io = io.BytesIO()
                            with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                                df.to_excel(writer, index=False, sheet_name='الفاتورة_المستخرجة')
                            
                            # زر تحميل الإكسل
                            st.download_button(
                                label="📥 تحميل الجدول كملف Excel (مفصول بذكاء)",
                                data=excel_io.getvalue(),
                                file_name=f"فاتورة_{uploaded_file.name}_ذكي.xlsx",
                                mime="application/vnd.ms-excel"
                            )
                        else:
                            st.warning("⚠️ نجحت القراءة ولكن لم نتمكن من العثور على جدول البيانات. النتيجة الخام:")
                            st.markdown(response.text)

                    except json.JSONDecodeError:
                        st.warning("⚠️ لم يستطع الذكاء الاصطناعي تنسيق البيانات كجدول ذكي. قد تكون الصورة غير واضحة بما يكفي لفهم تفاصيل التعبئة. النتيجة الخام:")
                        st.markdown(response.text)
                    
                except Exception as e:
                    st.error(f"⚠️ حدث خطأ أثناء قراءة الصورة: {str(e)}")
                    # كشاف لكشف الموديلات لو حدث خطأ
                    with st.expander("🔍 اضغط هنا لكشف تفاصيل حسابك في جوجل"):
                        st.write("الموديلات التي منحتها جوجل لمفتاحك هي:")
                        try:
                            st.write([m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods])
                        except:
                            st.write("لم نتمكن من جلب قائمة الموديلات.")
    else:
        st.error("❌ لم نتمكن من العثور على محرك مناسب في حسابك.")
