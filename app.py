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
    
    st.markdown("### ⚙️ اختر الأعمدة (تم تثبيت الترتيب والبيانات المطلوبة):")
    
    # الأعمدة الجديدة المطابقة للإكسل بالضبط
    excel_cols = [
        '#', 'اسم الصنف', 'التصنيف', 'رمز المادة', 'سعر المادة (ر.س)', 
        'اسم الشركة / المورد', 'الرقم الضريبي', 'رقم السجل التجاري', 
        'رقم الهاتف', 'البريد الإلكتروني', 'عنوان المورد', 
        'الوحدة الكبيرة', 'الوحدة الصغيرة', 'معامل التحويل', 
        'وزن الوحدة الصغيرة (كجم)'
    ]
    
    # الأعمدة الإضافية في حال رغبتم في إظهارها من جديد لاحقاً
    extra_cols = [
        'الكمية المطلوبة', 'الكمية بالوحدة الكبيرة', 'الكمية بالوحدة الصغيرة', 
        'وحدة الوزن الصغيرة', 'رقم الفاتورة / عرض السعر', 'البيان الأصلي', 
        'الضريبة', 'الإجمالي الصافي'
    ]
    
    all_final_cols = excel_cols + extra_cols
    default_on = excel_cols.copy() # الافتراضي سيكون فقط المطابق للإكسل!
    
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
        with st.spinner("جاري تحليل البيانات ومطابقتها مع نموذج الإكسل الجديد..."):
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

                    # استبعاد عمود الترقيم التلقائي من البرومبت ليتم إنشاؤه برمجياً
                    prompt_cols = [c for c in chosen_cols if c != '#']
                    
                    prompt = f"""
                    أنت محاسب مستودعات دقيق. استخرج البيانات بصيغة JSON.
                    يجب أن يحتوي الـ JSON على المفاتيح العامة (تستخرج مرة واحدة للفاتورة):
                    "اسم الشركة / المورد" (بالعربي حصراً)، "الرقم الضريبي"، "رقم السجل التجاري"، "رقم الهاتف"، "البريد الإلكتروني"، "عنوان المورد".
                    
                    ومفتاح "الأصناف" يحتوي على القائمة. استخرج لكل صنف: {', '.join(prompt_cols)}
                    بالإضافة إلى المفاتيح المساعدة التالية (يجب استخراجها دائماً للحسابات): "الكمية بالوحدة الكبيرة", "الكمية بالوحدة الصغيرة", "وحدة الوزن الصغيرة".
                    
                    قواعد تفكيك البيان الأصلي (هام جداً ولا تقبل الخطأ):
                    1. تحليل التعبئة من البيان (مثال "بديل ليمون 12*1 لتر"):
                       - 'الكمية بالوحدة الكبيرة': الرقم الأول في التعبئة.
                       - 'الكمية بالوحدة الصغيرة': الرقم الثاني في التعبئة.
                       - 'وحدة الوزن الصغيرة': وحدة القياس. (ملاحظة ذكية: اقل وزن هو كيلو او لتر. اذا كان الجرام اكتبه ليتم تحويله).
                       - 'الوحدة الصغيرة': **الأصل في العبوات هو "علبة" (للأشياء الجامدة)، وللسوائل "جالون"**، إلا إذا نَص البيان صراحة على شيء مختلف.
                       - 'الوحدة الكبيرة': العبوة الخارجية (مثال: كرتون).
                    2. إذا كان الصنف وزناً كلياً بدون ضرب (مثل "طحينة 15 كيلو"):
                       - 'الكمية بالوحدة الكبيرة': 1.
                       - 'الكمية بالوحدة الصغيرة': 15.
                       - 'وحدة الوزن الصغيرة': كيلو.
                       - 'الوحدة الصغيرة': علبة (أو تنكة إذا ذُكرت).
                    3. 'التصنيف': يجب أن يكون كلمة واحدة فقط لا غير (مثال: معلبات، صوصات، بهارات، زيوت، خدمات). يُمنع كتابة كلمتين.
                    4. 'اسم الصنف': اسم الصنف نظيف بدون أرقام أو أوزان.
                    5. 'رمز المادة': رقم الصنف أو كود المادة المكتوب في الفاتورة.
                    6. 'سعر المادة (ر.س)': السعر الافرادي للصنف.
                    """
                    
                    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": payload}])
                    res_text = response.text.strip().replace('```json', '').replace('```', '').strip()
                    data = json.loads(res_text)
                    
                    items = data if isinstance(data, list) else data.get('الأصناف', [])
                    
                    general_info = {}
                    if isinstance(data, dict):
                        general_info['اسم الشركة / المورد'] = data.get('اسم الشركة / المورد', data.get('اسم المورد', ''))
                        general_info['الرقم الضريبي'] = data.get('الرقم الضريبي', data.get('الرقم الضريبي للمورد', ''))
                        general_info['رقم السجل التجاري'] = data.get('رقم السجل التجاري', '')
                        general_info['رقم الهاتف'] = data.get('رقم الهاتف', '')
                        general_info['البريد الإلكتروني'] = data.get('البريد الإلكتروني', '')
                        general_info['عنوان المورد'] = data.get('عنوان المورد', '')
                    
                    for item in items:
                        for k, v in general_info.items():
                            if k not in item or not str(item.get(k, '')).strip():
                                item[k] = v
                                
                        try:
                            # 1. تنظيف الرقم الكبير لمعامل التحويل
                            raw_qty_large = re.sub(r'[^0-9.]', '', str(item.get('الكمية بالوحدة الكبيرة', 1)))
                            qty_large = float(raw_qty_large) if raw_qty_large else 1
                            
                            small_unit = str(item.get('الوحدة الصغيرة', 'علبة')).strip()
                            large_unit = str(item.get('الوحدة الكبيرة', 'كرتون')).strip()
                            item['معامل التحويل'] = f"{int(qty_large)} {small_unit} / {large_unit}"
                            
                            # 2. الفلتر الذكي لتحويل الجرام إلى كيلو والملليلتر إلى لتر
                            w_unit = str(item.get('وحدة الوزن الصغيرة', '')).strip()
                            
                            # استخراج الرقم الصغير بأمان
                            small_val_raw = str(item.get('الكمية بالوحدة الصغيرة', 0)).replace(',', '')
                            matches = re.findall(r'[0-9.]+', small_val_raw)
                            small_val = float(matches[0]) if matches else 0
                            
                            if w_unit in ['جرام', 'جم', 'غرام', 'g', 'gram']:
                                new_val = small_val / 1000
                                item['وزن الوحدة الصغيرة (كجم)'] = int(new_val) if new_val.is_integer() else new_val
                            elif w_unit in ['مل', 'ملي', 'مليلتر', 'ml']:
                                new_val = small_val / 1000
                                item['وزن الوحدة الصغيرة (كجم)'] = int(new_val) if new_val.is_integer() else new_val
                            else:
                                item['وزن الوحدة الصغيرة (كجم)'] = int(small_val) if small_val.is_integer() else small_val

                            # 3. تنظيف اسم المنتج
                            item['اسم الصنف'] = re.sub(r'\d+[\*×]\d+.*|[\d\.]+\s*(جرام|جم|كجم|كيلو|لتر|مل)', '', str(item.get('اسم الصنف', item.get('المادة/اسم المنتج', '')))).strip()
                        except: continue
                        
                    all_extracted_data.extend(items)

                if all_extracted_data:
                    df = pd.DataFrame(all_extracted_data)
                    
                    # إنشاء عمود الترقيم التلقائي
                    if '#' in chosen_cols:
                        df['#'] = range(1, len(df) + 1)
                        
                    # ترتيب الأعمدة لتطابق الترتيب الذي اختاره المستخدم (مطابق للإكسل)
                    final_cols = [c for c in chosen_cols if c in df.columns]
                    df = df[final_cols]
                    
                    st.success("✅ اكتمل الاستخراج! تم مطابقة وترتيب الأعمدة مع نموذج الإكسل باحترافية.")
                    st.dataframe(df, use_container_width=True)
                    
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد Master')
                        wr.sheets['أزواد Master'].right_to_left()
                    st.download_button("⬇️ تحميل ملف الاكسل", out.getvalue(), "Azwad_Master_Report.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")
