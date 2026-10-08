import io
import re
import sqlite3
import easyocr
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st

# ضبط الصفحة لتبدو مثالية على الهاتف
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
    return easyocr.Reader(["ar", "en"], gpu=False)


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS residents_cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building TEXT NOT NULL,
            apartment TEXT NOT NULL,
            resident_name TEXT,
            phone TEXT,
            plate_number TEXT NOT NULL,
            plate_letter TEXT,
            plate_region TEXT,
            car_info TEXT,
            notes TEXT
        )
    """
    )
    conn.commit()
    conn.close()


init_db()


def get_all_records():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM residents_cars", conn)
    conn.close()
    return df


def add_record(
    building,
    apartment,
    name,
    phone,
    plate_num,
    plate_let,
    plate_reg,
    car_info,
    notes,
):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO residents_cars (building, apartment, resident_name, phone, plate_number, plate_letter, plate_region, car_info, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            building,
            apartment,
            name,
            phone,
            plate_num,
            plate_let,
            plate_reg,
            car_info,
            notes,
        ),
    )
    conn.commit()
    conn.close()


def delete_record(record_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM residents_cars WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


# دالة عرض البطاقة بمعلومات المقيم والاتصال
def render_card_native(row):
    with st.container(border=True):
        p_num = str(row["plate_number"])
        p_let = str(row["plate_letter"]) if row["plate_letter"] else "-"
        p_reg = str(row["plate_region"]) if row["plate_region"] else "-"
        plate_str = f"{p_num} | {p_let} | {p_reg}"

        st.subheader(f"🚘 لوحة: {plate_str}")
        st.write(f"🏢 **عمارة:** {row['building']}  |  🚪 **شقة:** {row['apartment']}")
        st.write(
            f"👤 **الساكن:** {row['resident_name'] if row['resident_name'] else 'غير محدد'}"
        )
        st.write(
            f"🚗 **السيارة:** {row['car_info'] if row['car_info'] else 'غير مسجل'}"
        )

        clean_phone = (
            str(row["phone"]).replace(" ", "").replace("-", "")
            if row["phone"]
            else ""
        )
        if clean_phone:
            st.write(f"📞 **الهاتف:** `{clean_phone}`")
            c_call, c_wa = st.columns(2)
            with c_call:
                st.link_button(
                    "📞 اتصال هاتفي",
                    f"tel:{clean_phone}",
                    use_container_width=True,
                )
            with c_wa:
                wa_phone = (
                    clean_phone[1:]
                    if clean_phone.startswith("0")
                    else clean_phone
                )
                wa_link = f"https://wa.me/212{wa_phone}?text=السلام%20عليكم%20بخصوص%20سيارتكم%20في%20الإقامة"
                st.link_button(
                    "💬 واتساب", wa_link, use_container_width=True
                )


# ----------------- إدارة التنقل عبر الأزرار (Session State) -----------------
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "camera"

st.title("🚗 مواقف سيارات الإقامة")

# عرض شريط أزرار التنقل الرئيسية أعلى الشاشة
col1, col2, col3, col4 = st.columns(4)

with col1:
    btn_type = (
        "primary" if st.session_state.active_tab == "camera" else "secondary"
    )
    if st.button("📷 الكاميرا", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "camera"
        st.rerun()

with col2:
    btn_type = (
        "primary" if st.session_state.active_tab == "search" else "secondary"
    )
    if st.button("🔍 بحث سريع", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "search"
        st.rerun()

with col3:
    btn_type = (
        "primary" if st.session_state.active_tab == "add" else "secondary"
    )
    if st.button("➕ تسجيل", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "add"
        st.rerun()

with col4:
    btn_type = (
        "primary" if st.session_state.active_tab == "admin" else "secondary"
    )
    if st.button("📊 الإدارة", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "admin"
        st.rerun()

st.markdown("---")

letters_list = [
    "أ",
    "ب",
    "د",
    "هـ",
    "و",
    "ز",
    "ح",
    "ط",
    "ي",
    "ك",
    "ل",
    "م",
    "ن",
    "س",
    "ع",
    "ف",
    "ص",
    "ق",
    "ر",
    "ش",
    "ت",
    "ث",
    "خ",
    "ذ",
    "ض",
    "ظ",
    "غ",
    "ج",
    "WW",
    "أخرى",
]

# ==================== 1. قسم الكاميرا ====================
if st.session_state.active_tab == "camera":
    st.subheader("📷 مسح اللوحة بالكاميرا")
    camera_file = st.camera_input("التقط صورة اللوحة")

    if camera_file is not None:
        reader = get_ocr_reader()
        image = Image.open(io.BytesIO(camera_file.getvalue()))
        image_np = np.array(image)

        with st.spinner("جاري قراءة اللوحة..."):
            results = reader.readtext(image_np)
            full_text = " ".join([res[1] for res in results])
            numbers = re.findall(r"\d+", full_text)

        if numbers:
            target_number = max(numbers, key=len)
            st.success(f"الترقيم المقروء: {target_number}")

            df = get_all_records()
            matches = (
                df[df["plate_number"].astype(str).str.contains(target_number)]
                if not df.empty
                else pd.DataFrame()
            )

            if not matches.empty:
                st.info("✅ السيارة مسجلة مسبقاً:")
                for _, row in matches.iterrows():
                    render_card_native(row)
            else:
                st.warning(f"⚠️ السيارة بالرقم ({target_number}) غير مسجلة.")
                with st.form("quick_reg_form"):
                    st.write("**تسجيل سريع للسيارة:**")
                    p_num = st.text_input(
                        "أرقام اللوحة *", value=target_number
                    )
                    p_let = st.selectbox("حرف اللوحة", letters_list)
                    p_reg = st.text_input(
                        "عمالة اللوحة", placeholder="مثال: 26"
                    )

                    bld = st.text_input("رقم العمارة *", placeholder="مثال: 14")
                    apt = st.text_input("رقم الشقة *", placeholder="مثال: 3")
                    name = st.text_input(
                        "اسم الساكن", placeholder="مثال: أحمد"
                    )
                    phone = st.text_input(
                        "رقم الهاتف", placeholder="مثال: 0612345678"
                    )
                    car_desc = st.text_input(
                        "نوع ولون السيارة",
                        placeholder="مثال: Dacia Duster رمادية",
                    )

                    if st.form_submit_button(
                        "💾 حفظ البيانات", use_container_width=True
                    ):
                        if bld and apt and p_num:
                            add_record(
                                bld,
                                apt,
                                name,
                                phone,
                                p_num,
                                p_let,
                                p_reg,
                                car_desc,
                                "",
                            )
                            st.success("تم الحفظ بنجاح!")
                            st.rerun()
                        else:
                            st.error("يرجى ملء اللوحة والعمارة والشقة.")
        else:
            st.error("تعذر قراءة أرقام واضحة. يرجى الاقتراب من اللوحة.")

# ==================== 2. قسم البحث السريع ====================
elif st.session_state.active_tab == "search":
    st.subheader("🔍 استعلام فوري")
    query = st.text_input(
        "البحث:", placeholder="اكتب رقم اللوحة، العمارة، أو الاسم..."
    )

    if query:
        df = get_all_records()
        if not df.empty:
            mask = (
                df["plate_number"].astype(str).str.contains(query)
                | df["building"].astype(str).str.contains(query)
                | df["resident_name"].astype(str).str.contains(query, case=False)
            )
            results = df[mask]
            if not results.empty:
                st.write(f"النتائج ({len(results)}):")
                for _, row in results.iterrows():
                    render_card_native(row)
            else:
                st.warning("لا توجد نتائج مطابقة.")

# ==================== 3. قسم التسجيل اليدوي ====================
elif st.session_state.active_tab == "add":
    st.subheader("➕ تسجيل يدوي لسيارة")
    with st.form("manual_entry_form", clear_on_submit=True):
        bld = st.text_input("رقم العمارة *", placeholder="مثال: 12")
        apt = st.text_input("رقم الشقة *", placeholder="مثال: 5")
        name = st.text_input("اسم الساكن")
        phone = st.text_input("رقم الهاتف")

        st.write("---")
        p_num = st.text_input("أرقام اللوحة *", placeholder="مثال: 12345")
        p_let = st.selectbox("حرف اللوحة", letters_list, key="manual_let")
        p_reg = st.text_input("العمالة", placeholder="مثال: 26")
        car_desc = st.text_input(
            "نوع ولون السيارة", placeholder="مثال: Clio سوداء"
        )

        if st.form_submit_button(
            "💾 حفظ في النظام", use_container_width=True
        ):
            if bld and apt and p_num:
                add_record(
                    bld, apt, name, phone, p_num, p_let, p_reg, car_desc, ""
                )
                st.success("تم حفظ البيانات بنجاح!")
            else:
                st.error("يرجى ملء الحقول المطلوبة (*)")

# ==================== 4. قسم الإدارة وتصدير Excel ====================
elif st.session_state.active_tab == "admin":
    st.subheader("📊 السجلات وتصدير Excel")
    df = get_all_records()
    if not df.empty:
        c1, c2 = st.columns(2)
        c1.metric("إجمالي السيارات", len(df))
        c2.metric("العمارات المغطاة", df["building"].nunique())

        st.dataframe(df, use_container_width=True)

        towrite = io.BytesIO()
        with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="السيارات")
        towrite.seek(0)

        st.download_button(
            label="📥 تنزيل ملف Excel (.xlsx)",
            data=towrite,
            file_name="residence_cars.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        with st.expander("🗑️ حذف سجل"):
            del_id = st.number_input("رقم السجل (ID):", min_value=1, step=1)
            if st.button("حذف نهائي", use_container_width=True):
                delete_record(del_id)
                st.rerun()
    else:
        st.info("لا توجد سيارات مسجلة بعد.")