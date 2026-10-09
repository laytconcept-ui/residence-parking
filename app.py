import io
import re
import sqlite3
import easyocr
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st

st.set_page_config(
    page_title="تدبير سيارات الإقامة",
    page_icon="🚗",
    layout="centered",
    initial_sidebar_state="collapsed",
)

DB_FILE = "residence_parking.db"

# ----------------- تهيئة EasyOCR وقاعدة البيانات -----------------
@st.cache_resource
def get_ocr_reader():
    return easyocr.Reader(['ar', 'en'], gpu=False)

def init_db():
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("""
        CREATE TABLE IF NOT EXISTS residents_cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building TEXT,
            apartment TEXT,
            resident_name TEXT,
            phone TEXT,
            plate_number TEXT NOT NULL,
            plate_letter TEXT,
            plate_region TEXT,
            full_plate TEXT,
            car_info TEXT,
            notes TEXT
        )
    """)
  # التأكد من وجود عمود full_plate في حال كانت قاعدة البيانات قديمة
  try:
    c.execute("ALTER TABLE residents_cars ADD COLUMN full_plate TEXT")
  except sqlite3.OperationalError:
    pass  # العمود موجود مسبقاً، لا داعي لعمل شيء

  conn.commit()
  conn.close()

init_db()

def get_all_records():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM residents_cars ORDER BY id DESC", conn)
    conn.close()
    return df

def add_record(building, apartment, name, phone, plate_num, plate_let, plate_reg, full_plate, car_info, notes):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO residents_cars (building, apartment, resident_name, phone, plate_number, plate_letter, plate_region, full_plate, car_info, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (building, apartment, name, phone, plate_num, plate_let, plate_reg, full_plate, car_info, notes))
    conn.commit()
    conn.close()

def delete_record(record_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM residents_cars WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

# دالة تحليل النص المستخرج من EasyOCR لاستخراج أجزاء اللوحة المغربية
def parse_moroccan_plate(text_list):
    arabic_letters = ["أ", "ب", "د", "هـ", "و", "ز", "ح", "ط", "ي", "ك", "ل", "م", "ن", "س", "ع", "ف", "ص", "ق", "ر", "ش", "ت", "ث", "خ", "ذ", "ض", "ظ", "غ", "ج", "WW"]
    combined = " ".join(text_list)
    
    # البحث عن الأرقام
    nums = re.findall(r'\d+', combined)
    main_num = ""
    region = ""
    detected_letter = ""

    if nums:
        # الرقم الأطول عادة هو رقم التسجيل الرئيسي
        main_num = max(nums, key=len)
        remaining_nums = [n for n in nums if n != main_num]
        if remaining_nums:
            # الرقم الآخر هو غالباً رمز العمالة (مثلاً 26)
            region = remaining_nums[0]

    # البحث عن الحرف العربي
    for item in text_list:
        clean_item = item.strip()
        for let in arabic_letters:
            if let in clean_item:
                detected_letter = let
                break
        if detected_letter:
            break

    full_display = f"{main_num} | {detected_letter if detected_letter else '-'} | {region if region else '-'}"
    return main_num, detected_letter, region, full_display

# ----------------- شريط التنقل بالأزرار -----------------
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "camera"

st.title("🚗 جرد وتدبير سيارات الإقامة")

col1, col2, col3, col4 = st.columns(4)

with col1:
    btn_type = "primary" if st.session_state.active_tab == "camera" else "secondary"
    if st.button("📷 الكاميرا", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "camera"
        st.rerun()

with col2:
    btn_type = "primary" if st.session_state.active_tab == "search" else "secondary"
    if st.button("🔍 استعلام", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "search"
        st.rerun()

with col3:
    btn_type = "primary" if st.session_state.active_tab == "add" else "secondary"
    if st.button("➕ يدوي", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "add"
        st.rerun()

with col4:
    btn_type = "primary" if st.session_state.active_tab == "admin" else "secondary"
    if st.button("📊 الإدارة", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "admin"
        st.rerun()

st.markdown("---")

letters_list = ["", "أ", "ب", "د", "هـ", "و", "ز", "ح", "ط", "ي", "ك", "ل", "م", "ن", "س", "ع", "ف", "ص", "ق", "ر", "ش", "ت", "ث", "خ", "ذ", "ض", "ظ", "غ", "ج", "WW", "أخرى"]

# ==================== 1. مسح الكاميرا والجرد السريع ====================
if st.session_state.active_tab == "camera":
    st.subheader("📷 التقاط لوحة السيارة")
    st.caption("التقط صورة اللوحة وسيتم نقل الترقيم كاملاً لتسجيله بنقرة واحدة.")

    camera_file = st.camera_input("التقاط صورة اللوحة")

    if camera_file is not None:
        reader = get_ocr_reader()
        image = Image.open(io.BytesIO(camera_file.getvalue()))
        image_np = np.array(image)

        with st.spinner("جاري قراءة اللوحة بالكامل..."):
            results = reader.readtext(image_np)
            detected_texts = [res[1] for res in results]
            
        main_num, detected_let, region_num, full_display = parse_moroccan_plate(detected_texts)

        if main_num:
            st.success(f"🎯 الترقيم المقروء كاملاً: **{full_display}**")
            
            # فحص هل هي مسجلة مسبقاً لمنع التكرار
            df = get_all_records()
            is_exist = False
            if not df.empty:
                exist_match = df[df['plate_number'].astype(str) == str(main_num)]
                if not exist_match.empty:
                    is_exist = True
                    st.info("ℹ️ هذه السيارة مسجلة مسبقاً في الجدول:")
                    st.dataframe(exist_match[['id', 'building', 'apartment', 'plate_number', 'plate_letter', 'plate_region']], use_container_width=True)

            if not is_exist:
                st.write("### 📝 تأكيد الترقيم والحفظ السريع:")
                with st.form("quick_census_form"):
                    col_p1, col_p2, col_p3 = st.columns([2, 1, 1])
                    with col_p1:
                        p_num = st.text_input("الأرقام *", value=main_num)
                    with col_p2:
                        idx = letters_list.index(detected_let) if detected_let in letters_list else 0
                        p_let = st.selectbox("الحرف", letters_list, index=idx)
                    with col_p3:
                        p_reg = st.text_input("العمالة", value=region_num, placeholder="26")

                    st.caption("👇 الخانات التالية **اختيارية** تماماً (يمكن تركها فارغة وتعبئتها لاحقاً):")
                    c_bld, c_apt = st.columns(2)
                    with c_bld:
                        bld = st.text_input("رقم العمارة (اختياري)", placeholder="مثال: 14")
                    with c_apt:
                        apt = st.text_input("رقم الشقة (اختياري)", placeholder="مثال: 3")

                    c_name, c_phone = st.columns(2)
                    with c_name:
                        name = st.text_input("اسم الساكن (اختياري)")
                    with c_phone:
                        phone = st.text_input("الهاتف (اختياري)")

                    car_desc = st.text_input("نوع ولون السيارة (اختياري)", placeholder="مثال: Dacia رمادية")

                    save_now = st.form_submit_button("💾 حفظ الترقيم فوراً في الجدول", use_container_width=True)

                    if save_now:
                        if p_num:
                            full_plate_str = f"{p_num} | {p_let} | {p_reg}"
                            add_record(bld, apt, name, phone, p_num, p_let, p_reg, full_plate_str, car_desc, "")
                            st.success(f"🎉 تم تسجيل الترقيم [{full_plate_str}] في الجدول بنجاح!")
                            st.rerun()
                        else:
                            st.error("يرجى التأكد من وجود رقم اللوحة.")
        else:
            raw_text = " ".join(detected_texts)
            st.error(f"تعذر استخراج أرقام واضحة. النص المقروء: {raw_text if raw_text else 'لا يوجد'}")
            st.info("يمكنك كتابة الترقيم يدوياً من تبويب ➕ يدوي.")

# ==================== 2. قسم الاستعلام ====================
elif st.session_state.active_tab == "search":
    st.subheader("🔍 استعلام سريع")
    query = st.text_input("ابحث بالترقيم، العمارة أو الشقة:")
    if query:
        df = get_all_records()
        if not df.empty:
            mask = df['plate_number'].astype(str).str.contains(query) | \
                   df['building'].astype(str).str.contains(query) | \
                   df['apartment'].astype(str).str.contains(query) | \
                   df['resident_name'].astype(str).str.contains(query, case=False)
            res = df[mask]
            if not res.empty:
                st.write(f"النتائج ({len(res)}):")
                st.dataframe(res[['id', 'building', 'apartment', 'plate_number', 'plate_letter', 'plate_region', 'resident_name', 'phone', 'car_info']], use_container_width=True)
            else:
                st.warning("لا يوجد تطابق.")

# ==================== 3. قسم التسجيل اليدوي ====================
elif st.session_state.active_tab == "add":
    st.subheader("➕ تسجيل ترقيم يدوياً")
    with st.form("manual_add"):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            p_num = st.text_input("أرقام اللوحة *", placeholder="78954")
        with c2:
            p_let = st.selectbox("حرف اللوحة", letters_list)
        with c3:
            p_reg = st.text_input("العمالة", placeholder="26")

        st.caption("البيانات التالية اختيارية:")
        c_b, c_a = st.columns(2)
        with c_b:
            bld = st.text_input("العمارة")
        with c_a:
            apt = st.text_input("الشقة")

        name = st.text_input("اسم الساكن")
        phone = st.text_input("رقم الهاتف")
        car_desc = st.text_input("نوع ولون السيارة")

        if st.form_submit_button("💾 حفظ في الجدول", use_container_width=True):
            if p_num:
                full_plate_str = f"{p_num} | {p_let} | {p_reg}"
                add_record(bld, apt, name, phone, p_num, p_let, p_reg, full_plate_str, car_desc, "")
                st.success("تم الحفظ بنجاح!")
            else:
                st.error("أدخل رقم اللوحة على الأقل.")

# ==================== 4. قسم الإدارة وتصدير Excel ====================
elif st.session_state.active_tab == "admin":
    st.subheader("📊 جدول الترقيمات والسيارات المسجلة")
    df = get_all_records()
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي السيارات المسجلة", len(df))
        c2.metric("شقق مكتملة البيانات", df['apartment'].replace('', np.nan).dropna().count())
        c3.metric("ترقيمات بدون شقق بعد", df['apartment'].replace('', np.nan).isna().sum())

        st.dataframe(df, use_container_width=True)

        towrite = io.BytesIO()
        with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ترقيمات السيارات')
        towrite.seek(0)

        st.download_button(
            label="📥 تنزيل الجدول في ملف Excel (.xlsx)",
            data=towrite,
            file_name="residence_parking_census.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        with st.expander("🗑️ حذف سطر من الجدول"):
            del_id = st.number_input("أدخل رقم السجل (ID) لحذفه:", min_value=1, step=1)
            if st.button("تأكيد الحذف", use_container_width=True):
                delete_record(del_id)
                st.rerun()
    else:
        st.info("الجدول فارغ حتى الآن. ابدأ بالتقاط اللوحات عبر الكاميرا.")
