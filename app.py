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
    
    all_final_cols = [
        'اسم المورد', 'رقم الفاتورة / عرض السعر', 'الرقم الضريبي للمورد', 'رقم السجل التجاري',
        'رقم الصنف', 'المادة/اسم المنتج', 'الكمية المطلوبة', 'الوحدة الكبيرة', 
        'الكمية بالوحدة الكبيرة', 'الوحدة الصغيرة', 'الكمية بالوحدة الصغيرة', 
        'وحدة الوزن الصغيرة', 'معامل التحويل', 'السعر الافرادي',
        'البيان الأصلي', 'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
    ]
    
    default_on = [
        'اسم المورد', 'رقم الصنف', 'المادة/اسم المنتج', 'الكمية المطلوبة', 
        'الوحدة الكبيرة', 'الكمية بالوحدة الكبيرة', 'الوحدة الصغيرة', 'الكمية بالوحدة الصغيرة', 
        'وحدة الوزن الصغيرة', 'معامل التحويل', 'السعر الافرادي', 'البيان الأصلي', 
        'التصنيف الذكي', 'الضريبة', 'الإجمالي الصافي'
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
        with st.spinner("جاري تحليل البيانات..."):
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

                    prompt = f"""
                    أنت محاسب مستودعات دقيق. استخرج البيانات بصيغة JSON.
                    يجب أن يحتوي الـ JSON على المفاتيح العامة:
                    "اسم المورد" (بالعربي حصراً)، "رقم الفاتورة / عرض السعر"، "الرقم الضريبي للمورد"، "رقم السجل التجاري".
                    
                    ومفتاح "الأصناف" يحتوي على القائمة. استخرج لكل صنف: {', '.join(chosen_cols)}
                    
                    قواعد تفكيك البيان الأصلي (هام جداً ولا تقبل الخطأ):
                    1. 'الكمية المطلوبة': هي الكمية المفوترة فعلياً في الفاتورة (مثال: 50، 20، 5، 2، 10).
                    2. تحليل التعبئة من البيان (مثال "بديل ليمون 12*1 لتر"):
                       - 'الكمية بالوحدة الكبيرة': الرقم الأول في التعبئة.
                       - 'الكمية بالوحدة الصغيرة': الرقم الثاني في التعبئة.
                       - 'وحدة الوزن الصغيرة': وحدة القياس. (ملاحظة ذكية: اقل وزن هو كيلو او لتر. اذا كان الجرام اكتبه ليتم تحويله، لكن يفضل استخراج كيلو/لتر).
                       - 'الوحدة الصغيرة': **الأصل في العبوات هو "علبة" (للأشياء الجامدة)، وللسوائل "جالون"**، إلا إذا نَص البيان صراحة على شيء مختلف.
                       - 'الوحدة الكبيرة': العبوة الخارجية (مثال: كرتون).
                    3. إذا كان الصنف وزناً كلياً بدون ضرب (مثل "طحينة 15 كيلو"):
                       - 'الكمية بالوحدة الكبيرة': 1.
                       - 'الكمية بالوحدة الصغيرة': 15.
                       - 'وحدة الوزن الصغيرة': كيلو.
                       - 'الوحدة الصغيرة': علبة (أو تنكة إذا ذُكرت).
                    4. 'الضريبة': مبلغ مالي بالريال لكل صنف.
                    5. 'التصنيف الذكي': يجب أن يكون كلمة واحدة فقط لا غير (مثال: معلبات، صوصات، بهارات، زيوت، خدمات). يُمنع كتابة كلمتين.
                    6. 'المادة/اسم المنتج': اسم الصنف نظيف بدون أرقام أو أوزان.
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
                            # 1. تنظيف الرقم الكبير لمعامل التحويل
                            raw_qty_large = re.sub(r'[^0-9.]', '', str(item.get('الكمية بالوحدة الكبيرة', 1)))
                            qty_large = float(raw_qty_large) if raw_qty_large else 1
                            
                            small_unit = str(item.get('الوحدة الصغيرة', 'علبة')).strip()
                            large_unit = str(item.get('الوحدة الكبيرة', 'كرتون')).strip()
                            item['معامل التحويل'] = f"{int(qty_large)} {small_unit} / {large_unit}"
                            
                            # 2. الفلتر الذكي لتحويل الجرام إلى كيلو والملليلتر إلى لتر
                            w_unit = str(item.get('وحدة الوزن الصغيرة', '')).strip()
                            if w_unit in ['جرام', 'جم', 'غرام', 'g', 'gram']:
                                try:
                                    small_val = float(str(item.get('الكمية بالوحدة الصغيرة', 0)).replace(',', ''))
                                    new_val = small_val / 1000
                                    item['الكمية بالوحدة الصغيرة'] = int(new_val) if new_val.is_integer() else new_val
                                    item['وحدة الوزن الصغيرة'] = 'كيلو'
                                except: pass
                            elif w_unit in ['مل', 'ملي', 'مليلتر', 'ml']:
                                try:
                                    small_val = float(str(item.get('الكمية بالوحدة الصغيرة', 0)).replace(',', ''))
                                    new_val = small_val / 1000
                                    item['الكمية بالوحدة الصغيرة'] = int(new_val) if new_val.is_integer() else new_val
                                    item['وحدة الوزن الصغيرة'] = 'لتر'
                                except: pass

                            # 3. تنظيف اسم المنتج
                            item['المادة/اسم المنتج'] = re.sub(r'\d+[\*×]\d+.*|[\d\.]+\s*(جرام|جم|كجم|كيلو|لتر|مل)', '', str(item.get('المادة/اسم المنتج', ''))).strip()
                        except: continue
                        
                    all_extracted_data.extend(items)

                if all_extracted_data:
                    df = pd.DataFrame(all_extracted_data)
                    final_cols = [c for c in chosen_cols if c in df.columns]
                    df = df[final_cols]
                    
                    st.success("✅ اكتمل الاستخراج! تم توحيد وحدات الوزن بدقة احترافية.")
                    st.dataframe(df, use_container_width=True)
                    
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                        df.to_excel(wr, index=False, sheet_name='أزواد Master')
                        wr.sheets['أزواد Master'].right_to_left()
                    st.download_button("⬇️ تحميل ملف الاكسل", out.getvalue(), "Azwad_Master_Report.xlsx")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")
