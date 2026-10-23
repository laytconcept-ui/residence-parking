import io
import os
import re
from datetime import datetime
import cv2
import easyocr
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(
    page_title="تدبير موقف سيارات إقامة نفيس",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----------------- تثبيت أيقونة السيارة لمتصفح الهاتف -----------------
st.markdown(
    """
    <head>
        <link rel="icon" type="image/png" sizes="192x192" href="https://cdn-icons-png.flaticon.com/512/3202/3202926.png">
        <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/3202/3202926.png">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="theme-color" content="#2563eb">
    </head>
    <script>
    const linkIcon = document.createElement('link');
    linkIcon.rel = 'icon';
    linkIcon.href = 'https://cdn-icons-png.flaticon.com/512/3202/3202926.png';
    document.head.appendChild(linkIcon);

    const linkApple = document.createElement('link');
    linkApple.rel = 'apple-touch-icon';
    linkApple.href = 'https://cdn-icons-png.flaticon.com/512/3202/3202926.png';
    document.head.appendChild(linkApple);
    </script>
""",
    unsafe_allow_html=True,
)

ADMIN_PIN = "1234"
letters_list = ["", "أ", "ب", "د", "هـ", "و", "ج", "ح", "ي", "ز", "ر", "WW"]
status_options = ["مالك", "مكتري", "زائر"]
apt_types_list = ["", "F2", "F3", "F4", "F5", "أخرى"]

INITIAL_CARS_BACKUP = [
    (17, "25", "3", "", "جنان هند", "0642449791", "56110", "ب", "26", "56110 | ب | 26", "مالك", "", "2026-10-15 23:28", ""),
    (16, "14", "8", "", "عكلي اسماعيل", "0618070765", "75321", "د", "26", "75321 | د | 26", "مالك", "", "2026-10-15 14:24", ""),
    (15, "25", "2", "", "جلال الكميلي", "0661966055", "39789", "د", "26", "39789 | د | 26", "مالك", "Sym", "2026-10-15 14:24", ""),
    (14, "10", "8", "", "رضوان ديمات", "0660886406", "55498", "د", "26", "55498 | د | 26", "مالك", "TIGUAAN", "2026-10-15 14:24", ""),
    (13, "25", "", "", "", "", "16910", "أ", "29", "16910 | أ | 29", "مالك", "", "2026-10-15 14:24", ""),
    (12, "", "", "", "", "", "33418", "هـ", "1", "33418 | هـ | 1", "مالك", "", "2026-10-15 14:24", ""),
    (11, "", "", "", "", "", "31694", "د", "26", "31694 | د | 26", "مالك", "", "2026-10-15 14:24", ""),
    (10, "", "", "", "", "", "44217", "م", "26", "44217 | م | 26", "مالك", "", "2026-10-15 14:24", ""),
    (9, "", "", "", "", "", "33929", "د", "1", "33929 | د | 1", "مالك", "", "2026-10-15 14:24", ""),
    (8, "6", "25", "", "حميد", "", "2366", "ب", "", "2366 | ب |", "مالك", "Duster", "2026-10-15 14:24", ""),
    (7, "7", "13", "", "", "", "6050", "", "1", "06050 |  | 1", "مالك", "", "2026-10-15 14:24", ""),
    (6, "", "", "", "", "", "42139", "د", "26", "42139 | د | 26", "مالك", "", "2026-10-15 14:24", ""),
    (5, "", "", "", "", "", "73580", "ب", "", "73580 | ب |", "مالك", "", "2026-10-15 14:24", ""),
    (4, "25", "2", "F2", "جلال الكميلي", "0661966055", "20092", "ب", "6", "20092 | ب | 6", "مالك", "Rexton", "2026-10-15 14:24", ""),
    (3, "5", "4", "", "محمد مجيديلة", "", "17227", "أ", "73", "17227 | أ | 73", "مالك", "", "2026-10-15 14:24", ""),
    (2, "25", "4", "F3", "ابراهيم مغراوي", "0671255086", "53688", "د", "26", "53688 | د | 26", "مالك", "citroen", "2026-10-15 14:24", ""),
    (1, "25", "5", "", "عمر", "0673209182", "50308", "و", "9", "50308 | و | 9", "مالك", "grise", "2026-10-15 14:24", "")
]


def clean_str(val):
    if isinstance(val, (pd.Series, np.ndarray, list)):
        if len(val) == 0:
            return ""
        val = val.iloc[0] if hasattr(val, "iloc") else val[0]
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    if s.lower() == "nan":
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    return s


def clean_apt_type(val):
    s = clean_str(val).upper().replace(" ", "")
    if s in ["F2", "F3", "F4", "F5"]:
        return s
    if "F2" in s:
        return "F2"
    if "F3" in s:
        return "F3"
    if "F4" in s:
        return "F4"
    if "F5" in s:
        return "F5"
    return s if s else ""


def format_moroccan_phone(phone_val):
    p = clean_str(phone_val).replace(" ", "").replace("-", "")
    if not p:
        return ""
    if len(p) == 9 and p.startswith(("6", "7", "5")):
        p = "0" + p
    return p


# ----------------- تصميم واجهة التطبيق (CSS) -----------------
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');

    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    .stDeployButton { display: none !important; }

    html, body, [class*="css"], .stApp {
        font-family: 'Cairo', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        background-color: #f1f5f9;
        direction: rtl;
        text-align: right;
    }

    [data-testid="InputInstructions"] { display: none !important; }

    .app-top-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #2563eb 100%);
        border-radius: 18px;
        padding: 16px 20px;
        margin-bottom: 16px;
        color: white;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.2);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .app-top-header h2 {
        color: #ffffff !important;
        font-size: 20px !important;
        font-weight: 800 !important;
        margin: 0 !important;
        background: transparent !important;
        padding: 0 !important;
        box-shadow: none !important;
    }
    .app-top-header .status-badge {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 5px;
    }

    h2, [data-testid="stHeadingWithActionElements"] h2, .section-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #2563eb 100%) !important;
        border-radius: 14px !important;
        padding: 12px 18px !important;
        color: #ffffff !important;
        font-size: 19px !important;
        font-weight: 800 !important;
        box-shadow: 0 8px 20px -4px rgba(15, 23, 42, 0.25) !important;
        margin-top: 12px !important;
        margin-bottom: 18px !important;
        display: block !important;
        text-align: right !important;
    }

    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #ffffff !important;
        border: 2px solid #2563eb !important;
        border-radius: 12px !important;
        padding: 10px 14px !important;
        font-size: 17px !important;
        font-weight: 800 !important;
        color: #0f172a !important;
    }

    .highlight-pin-box input {
        background-color: #fff1f2 !important;
        border: 2px solid #e11d48 !important;
        border-radius: 12px !important;
        padding: 14px !important;
        font-size: 22px !important;
        font-weight: 900 !important;
        color: #be123c !important;
        text-align: center !important;
        letter-spacing: 6px !important;
    }

    [data-testid="stCameraInput"] {
        width: 100% !important;
        max-width: 100% !important;
        margin: 0 auto !important;
    }
    [data-testid="stCameraInput"] video {
        width: 100% !important;
        height: auto !important;
        min-height: 340px !important;
        border-radius: 16px !important;
        border: 3px solid #2563eb !important;
        box-shadow: 0 10px 25px rgba(37, 99, 235, 0.2) !important;
    }

    .morocco-plate-tag {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: #ffffff;
        border: 2px solid #0f172a;
        border-radius: 10px;
        padding: 6px 14px;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.06), 0 3px 6px rgba(0,0,0,0.08);
        gap: 12px;
        margin-bottom: 12px;
    }
    .plate-item { font-size: 20px; font-weight: 900; color: #0f172a; }
    .plate-divider { width: 2px; height: 22px; background-color: #cbd5e1; }

    div.stButton > button {
        border-radius: 12px !important;
        padding: 10px 18px !important;
        font-size: 15px !important;
        font-weight: 800 !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05) !important;
        transition: all 0.2s ease !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ----------------- الربط بقاعدة بيانات Supabase -----------------
@st.cache_resource
def get_db_engine():
    db_url = st.secrets.get("DATABASE_URL", "")
    if not db_url:
        db_url = os.environ.get("DATABASE_URL", "")

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+psycopg2://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    if not db_url:
        st.error("⚠️ لم يتم العثور على DATABASE_URL في Streamlit Secrets!")
        st.stop()

    return create_engine(
        db_url,
        connect_args={
            "sslmode": "require",
            "connect_timeout": 15
        },
        pool_pre_ping=True,
        pool_recycle=300
    )

engine = get_db_engine()

# ----------------- قراءة دليل الشقق fm6.xlsx -----------------
@st.cache_data
def load_fm6_directory():
    excel_file = None
    for fname in ["fm6.xlsx", "FM6.xlsx", "fm6.xls"]:
        if os.path.exists(fname):
            excel_file = fname
            break

    if excel_file:
        try:
            df = pd.read_excel(excel_file)
            first_row_vals = [str(v).lower().strip() for v in df.iloc[0].values]
            if any(x in first_row_vals for x in ["apartment", "شقة", "immeuble", "building"]):
                df.columns = df.iloc[0]
                df = df[1:].reset_index(drop=True)

            col_map = {}
            for col in df.columns:
                c_lower = str(col).lower().strip()
                if any(k in c_lower for k in ["apt", "apartment", "شقة", "شقه"]):
                    col_map[col] = "apartment"
                elif any(k in c_lower for k in ["bld", "building", "عمارة", "عماره", "imm"]):
                    col_map[col] = "building"
                elif any(k in c_lower for k in ["apartment_type", "typologie", "type", "نوع", "صنف"]):
                    col_map[col] = "apartment_type"
                elif any(k in c_lower for k in ["name", "resident", "nom", "اسم", "قاطن", "ساكن"]):
                    col_map[col] = "resident_name"
                elif any(k in c_lower for k in ["phone", "tel", "هاتف", "جوال", "نقال"]):
                    col_map[col] = "phone"

            df = df.rename(columns=col_map)
            df = df.loc[:, ~df.columns.duplicated()]

            for col in ["apartment", "building", "apartment_type", "resident_name", "phone"]:
                if col not in df.columns:
                    df[col] = ""
                else:
                    df[col] = df[col].apply(clean_str)

            df["phone"] = df["phone"].apply(format_moroccan_phone)
            df["apartment_type"] = df["apartment_type"].apply(clean_apt_type)
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=["apartment", "building", "apartment_type", "resident_name", "phone"])


# ----------------- تهيئة جدول Supabase وحقن البيانات المسبقة -----------------
def init_supabase():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS residents_cars (
                id SERIAL PRIMARY KEY,
                building VARCHAR(50),
                apartment VARCHAR(50),
                apartment_type VARCHAR(50),
                resident_name VARCHAR(255),
                phone VARCHAR(50),
                plate_number VARCHAR(50) NOT NULL,
                plate_letter VARCHAR(50),
                plate_region VARCHAR(50),
                full_plate VARCHAR(100),
                car_type VARCHAR(50) DEFAULT 'مالك',
                car_info VARCHAR(255),
                created_at VARCHAR(100),
                notes TEXT
            );
        """))

        res = conn.execute(text("SELECT COUNT(*) FROM residents_cars")).scalar()
        if res == 0:
            for item in INITIAL_CARS_BACKUP:
                _, bld, apt, apt_t, name, phone, p_num, p_let, p_reg, p_full, c_type, c_info, c_at, notes = item
                conn.execute(text("""
                    INSERT INTO residents_cars 
                    (building, apartment, apartment_type, resident_name, phone, plate_number, plate_letter, plate_region, full_plate, car_type, car_info, created_at, notes)
                    VALUES (:bld, :apt, :apt_t, :name, :phone, :p_num, :p_let, :p_reg, :p_full, :c_type, :c_info, :c_at, :notes)
                """), {
                    "bld": bld, "apt": apt, "apt_t": apt_t, "name": name, "phone": phone,
                    "p_num": p_num, "p_let": p_let, "p_reg": p_reg, "p_full": p_full,
                    "c_type": c_type, "c_info": c_info, "c_at": c_at, "notes": notes
                })

init_supabase()


@st.cache_resource
def get_ocr_reader():
    return easyocr.Reader(["ar", "en"], gpu=False)


def get_all_records():
    with engine.connect() as conn:
        df = pd.read_sql(text("SELECT * FROM residents_cars ORDER BY id DESC"), conn)
    for col in df.columns:
        df[col] = df[col].apply(clean_str)
    if "phone" in df.columns:
        df["phone"] = df["phone"].apply(format_moroccan_phone)
    return df


def get_apartment_info(bld_num, apt_num):
    b_clean = clean_str(bld_num)
    a_clean = clean_str(apt_num)
    if not a_clean:
        return None

    df_dir = load_fm6_directory()
    if not df_dir.empty:
        if b_clean:
            match = df_dir[(df_dir["building"].astype(str) == b_clean) & (df_dir["apartment"].astype(str) == a_clean)]
        else:
            match = df_dir[df_dir["apartment"].astype(str) == a_clean]

        if not match.empty:
            r = match.iloc[0]
            return {
                "building": clean_str(r.get("building", "")),
                "apartment_type": clean_apt_type(r.get("apartment_type", "")),
                "resident_name": clean_str(r.get("resident_name", "")),
                "phone": format_moroccan_phone(r.get("phone", "")),
            }
    return None


def add_record(building, apartment, apartment_type, name, phone, plate_num, plate_let, plate_reg, full_plate, car_type, car_info, notes):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO residents_cars 
            (building, apartment, apartment_type, resident_name, phone, plate_number, plate_letter, plate_region, full_plate, car_type, car_info, created_at, notes)
            VALUES (:bld, :apt, :apt_t, :name, :phone, :p_num, :p_let, :p_reg, :p_full, :c_type, :c_info, :c_at, :notes)
        """), {
            "bld": clean_str(building),
            "apt": clean_str(apartment),
            "apt_t": clean_apt_type(apartment_type),
            "name": clean_str(name),
            "phone": format_moroccan_phone(phone),
            "p_num": clean_str(plate_num),
            "p_let": str(plate_let),
            "p_reg": clean_str(plate_reg),
            "p_full": clean_str(full_plate),
            "c_type": clean_str(car_type),
            "c_info": clean_str(car_info),
            "c_at": now_str,
            "notes": clean_str(notes)
        })


def update_full_record(record_id, building, apartment, apartment_type, name, phone, plate_num, plate_let, plate_reg, full_plate, car_type, car_info, notes):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE residents_cars
            SET building = :bld, apartment = :apt, apartment_type = :apt_t, resident_name = :name, phone = :phone, 
                plate_number = :p_num, plate_letter = :p_let, plate_region = :p_reg, full_plate = :p_full,
                car_type = :c_type, car_info = :c_info, notes = :notes
            WHERE id = :rec_id
        """), {
            "bld": clean_str(building),
            "apt": clean_str(apartment),
            "apt_t": clean_apt_type(apartment_type),
            "name": clean_str(name),
            "phone": format_moroccan_phone(phone),
            "p_num": clean_str(plate_num),
            "p_let": str(plate_let),
            "p_reg": clean_str(plate_reg),
            "p_full": clean_str(full_plate),
            "c_type": clean_str(car_type),
            "c_info": clean_str(car_info),
            "notes": clean_str(notes),
            "rec_id": int(record_id)
        })


def delete_record(record_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM residents_cars WHERE id = :rec_id"), {"rec_id": int(record_id)})


# ----------------- نافذة التعديل والحذف المنبثقة (Modal Dialog) -----------------
@st.dialog("✏️ تعديل بيانات الساكن والسيارة أو الحذف")
def edit_car_dialog(row):
    rec_id = int(row["id"])
    st.caption(f"المعرف السحابي: #{rec_id}")

    c_p1, c_p2, c_p3 = st.columns([2, 1, 1])
    with c_p1:
        dlg_pnum = st.text_input("أرقام اللوحة *", value=clean_str(row["plate_number"]), key=f"dlg_pnum_{rec_id}")
    with c_p2:
        let_val = row["plate_letter"] if pd.notna(row["plate_letter"]) and row["plate_letter"] in letters_list else ""
        dlg_plet = st.selectbox("الحرف", letters_list, index=letters_list.index(let_val) if let_val else 0, key=f"dlg_plet_{rec_id}")
    with c_p3:
        dlg_preg = st.text_input("العمالة", value=clean_str(row["plate_region"]), key=f"dlg_preg_{rec_id}")

    c1, c2, c3 = st.columns(3)
    with c1:
        dlg_bld = st.text_input("رقم العمارة", value=clean_str(row["building"]), key=f"dlg_bld_{rec_id}")
    with c2:
        dlg_apt = st.text_input("رقم الشقة", value=clean_str(row["apartment"]), key=f"dlg_apt_{rec_id}")
    with c3:
        curr_t = clean_apt_type(row.get("apartment_type", ""))
        idx_t = apt_types_list.index(curr_t) if curr_t in apt_types_list else 0
        dlg_apttype = st.selectbox("نوع الشقة", apt_types_list, index=idx_t, key=f"dlg_apttype_{rec_id}")

    c_n1, c_n2 = st.columns(2)
    with c_n1:
        dlg_name = st.text_input("اسم الساكن / المالك", value=str(row["resident_name"]) if pd.notna(row["resident_name"]) else "", key=f"dlg_name_{rec_id}")
    with c_n2:
        dlg_phone = st.text_input("رقم الهاتف", value=clean_str(row["phone"]), key=f"dlg_phone_{rec_id}")

    c_c1, c_c2 = st.columns(2)
    with c_c1:
        dlg_car = st.text_input("نوع ولون السيارة", value=str(row["car_info"]) if pd.notna(row["car_info"]) else "", key=f"dlg_car_{rec_id}")
    with c_c2:
        curr_s = clean_str(row.get("car_type", "مالك"))
        s_idx = status_options.index(curr_s) if curr_s in status_options else 0
        dlg_status = st.radio("الصفة:", status_options, index=s_idx, horizontal=True, key=f"dlg_status_{rec_id}")

    dlg_notes = st.text_input("ملاحظات إضافية", value=clean_str(row["notes"]), key=f"dlg_notes_{rec_id}")

    st.markdown("---")
    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        if st.button("💾 حفظ وتحديث في Supabase", type="primary", use_container_width=True, key=f"save_dlg_{rec_id}"):
            e_p_num = clean_str(dlg_pnum)
            e_p_reg = clean_str(dlg_preg)
            new_full_plate = f"{e_p_num} | {dlg_plet} | {e_p_reg}"
            update_full_record(
                rec_id,
                dlg_bld,
                dlg_apt,
                dlg_apttype,
                dlg_name,
                dlg_phone,
                e_p_num,
                dlg_plet,
                e_p_reg,
                new_full_plate,
                dlg_status,
                dlg_car,
                dlg_notes,
            )
            st.success("✅ تم تحديث بيانات الساكن والسيارة بنجاح في السحابة!")
            st.rerun()

    with btn_col2:
        if st.button("🗑️ حذف هذا السجل نهائياً", use_container_width=True, key=f"del_dlg_{rec_id}"):
            delete_record(rec_id)
            st.warning("🗑️ تم حذف السجل نهائياً من Supabase!")
            st.rerun()


# ----------------- بطاقة عرض السيارة -----------------
def render_car_card(row, allow_edit=True):
    p_num = clean_str(row.get("plate_number", ""))
    p_let = str(row["plate_letter"]) if pd.notna(row["plate_letter"]) and row["plate_letter"] else "-"
    p_reg = clean_str(row.get("plate_region", ""))
    bld = clean_str(row.get("building", ""))
    apt = clean_str(row.get("apartment", ""))
    apt_type = clean_apt_type(row.get("apartment_type", ""))
    c_type = clean_str(row.get("car_type", "مالك"))
    clean_phone = clean_str(row.get("phone", ""))
    rec_id = int(row["id"])

    badge_color = "#15803d" if c_type == "مالك" else ("#1d4ed8" if c_type == "مكتري" else "#b45309")
    badge_bg = "#dcfce7" if c_type == "مالك" else ("#dbeafe" if c_type == "مكتري" else "#fef3c7")
    badge_icon = "🏠" if c_type == "مالك" else ("🔑" if c_type == "مكتري" else "⏱️")

    with st.container(border=True):
        top_col1, top_col2 = st.columns([3, 1])
        with top_col1:
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 6px;">
                    <div class="morocco-plate-tag" style="margin-bottom: 0;">
                        <span class="plate-item">{p_num}</span>
                        <span class="plate-divider"></span>
                        <span class="plate-item" style="color: #2563eb;">{p_let}</span>
                        <span class="plate-divider"></span>
                        <span class="plate-item">{p_reg}</span>
                    </div>
                    <span style="background: {badge_bg}; color: {badge_color}; padding: 4px 12px; border-radius: 20px; font-weight: 800; font-size: 13px;">
                        {badge_icon} {c_type}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with top_col2:
            if allow_edit:
                if st.button("✏️ تعديل / حذف", key=f"btn_open_dlg_{rec_id}", use_container_width=True):
                    edit_car_dialog(row)

        c_i1, c_i2 = st.columns(2)
        with c_i1:
            apt_disp = f"{apt} ({apt_type})" if apt_type else (apt if apt else "—")
            st.markdown(f"🏢 **العمارة:** `{bld if bld else '—'}` &nbsp;&nbsp;|&nbsp;&nbsp; 🚪 **الشقة:** `{apt_disp}`")
            st.markdown(f"👤 **الساكن:** **{row['resident_name'] if pd.notna(row['resident_name']) and row['resident_name'] else 'غير محدد'}**")
        with c_i2:
            st.markdown(f"🚘 **السيارة:** {row['car_info'] if pd.notna(row['car_info']) and row['car_info'] else 'غير محدد'}")
            st.markdown(f"📞 **الهاتف:** `{clean_phone if clean_phone else 'لا يوجد'}`")

        if clean_phone and clean_phone.lower() != "nan":
            b1, b2 = st.columns(2)
            with b1:
                st.link_button("📞 اتصال هاتفي", f"tel:{clean_phone}", use_container_width=True)
            with b2:
                wa_phone = clean_phone[1:] if clean_phone.startswith("0") else clean_phone
                p_full = f"{p_num} | {p_let} | {p_reg}"
                wa_msg = f"السلام عليكم، بخصوص سيارتكم رقم ({p_full}) المتوقفة في موقف إقامة نفيس، يرجى التكرم بتحريكها وشكراً."
                wa_link = f"https://wa.me/212{wa_phone}?text={wa_msg.replace(' ', '%20')}"
                st.link_button("💬 تنبيه واتساب", wa_link, use_container_width=True)


# ----------------- بطاقة عرض الساكن من دليل الشقق (fm6) -----------------
def render_directory_card(row):
    bld = clean_str(row.get("building", ""))
    apt = clean_str(row.get("apartment", ""))
    apt_type = clean_apt_type(row.get("apartment_type", ""))
    name = clean_str(row.get("resident_name", ""))
    phone = clean_str(row.get("phone", ""))

    with st.container(border=True):
        st.markdown(
            """
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="background: #e0f2fe; color: #0369a1; padding: 4px 12px; border-radius: 20px; font-weight: 800; font-size: 13px;">
                    📋 مسجل في دليل الشقق (fm6)
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            apt_text = f"{apt} ({apt_type})" if apt_type else apt
            st.markdown(f"🏢 **العمارة:** `{bld}` &nbsp;&nbsp;|&nbsp;&nbsp; 🚪 **الشقة:** `{apt_text}`")
            st.markdown(f"👤 **الساكن:** **{name if name else 'غير مسجل'}**")
        with c2:
            st.markdown(f"📞 **الهاتف:** `{phone if phone else 'غير متوفر'}`")

        if phone and phone.lower() != "nan":
            b1, b2 = st.columns(2)
            with b1:
                st.link_button("📞 اتصال هاتفي", f"tel:{phone}", use_container_width=True)
            with b2:
                wa_phone = phone[1:] if phone.startswith("0") else phone
                wa_link = f"https://wa.me/212{wa_phone}"
                st.link_button("💬 محادثة واتساب", wa_link, use_container_width=True)


# ----------------- شريط الملاحة والتنقل -----------------
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "camera"

st.markdown(
    """
<div class="app-top-header">
    <div>
        <h2>🚗 تدبير موقف سيارات إقامة نفيس</h2>
        <div style="font-size: 11px; opacity: 0.8; margin-top: 2px;">نظام التسيير السحابي المباشر (Supabase Connected)</div>
    </div>
    <div class="status-badge">
        <span style="height: 8px; width: 8px; background-color: #34d399; border-radius: 50%; display: inline-block;"></span>
        سحابي دائم 100%
    </div>
</div>
""",
    unsafe_allow_html=True,
)

nav_c1, nav_c2, nav_c3, nav_c4 = st.columns(4)

with nav_c1:
    btn_type = "primary" if st.session_state.active_tab == "camera" else "secondary"
    if st.button("📷 الكاميرا", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "camera"
        st.rerun()

with nav_c2:
    btn_type = "primary" if st.session_state.active_tab == "search" else "secondary"
    if st.button("🔍 استعلام", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "search"
        st.rerun()

with nav_c3:
    btn_type = "primary" if st.session_state.active_tab == "add" else "secondary"
    if st.button("➕ يدوي", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "add"
        st.rerun()

with nav_c4:
    btn_type = "primary" if st.session_state.active_tab == "admin" else "secondary"
    if st.button("📊 الإدارة", type=btn_type, use_container_width=True):
        st.session_state.active_tab = "admin"
        st.rerun()

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# ==================== 1. قسم الكاميرا ====================
if st.session_state.active_tab == "camera":
    st.subheader("📷 التقاط لوحة السيارة")
    st.caption("وجه الكاميرا نحو اللوحة والتقط الصورة:")

    camera_file = st.camera_input("")

    if camera_file is not None:
        reader = get_ocr_reader()
        image = Image.open(io.BytesIO(camera_file.getvalue()))
        image_np = np.array(image)

        with st.spinner("⚡ جاري استشعار اللوحة وقراءة الترقيم بدقة..."):
            cropped_plate, was_cropped = detect_and_crop_license_plate(image_np)
            processed_np = clean_image_for_ocr(cropped_plate)
            results = reader.readtext(
                processed_np,
                allowlist="0123456789أبدهوجحيخزرWW -|[]()/",
                detail=1,
                paragraph=False,
            )

            if not results and was_cropped:
                processed_orig = clean_image_for_ocr(image_np)
                results = reader.readtext(
                    processed_orig,
                    allowlist="0123456789أبدهوجحيخزرWW -|[]()/",
                    detail=1,
                    paragraph=False,
                )

        main_num, detected_let, region_num, full_display = parse_moroccan_plate(results)

        if main_num:
            df = get_all_records()
            exist_match = df[df["plate_number"].astype(str) == str(main_num)] if not df.empty else pd.DataFrame()

            if not exist_match.empty:
                st.warning("⚠️ هذه اللوحة مسجلة مسبقاً في النظام:")
                for _, row in exist_match.iterrows():
                    render_car_card(row, allow_edit=True)
            else:
                st.success(f"🎯 ترقيم مرصود: **{full_display}**")

                c_p1, c_p2, c_p3 = st.columns([2, 1, 1])
                with c_p1:
                    p_num = st.text_input("الأرقام *", value=main_num, key="cam_pnum")
                with c_p2:
                    idx = letters_list.index(detected_let) if detected_let in letters_list else 0
                    p_let = st.selectbox("الحرف", letters_list, index=idx, key="cam_plet")
                with c_p3:
                    p_reg = st.text_input("العمالة", value=region_num, placeholder="26", key="cam_preg")

                car_type = st.radio(
                    "صفة الساكن/السيارة:",
                    status_options,
                    horizontal=True,
                    key="cam_status_radio",
                )

                st.markdown("---")
                st.markdown("🏢 **تحديد العمارة والشقة لجلب المعطيات بدقة:**")

                if "cam_name_input" not in st.session_state:
                    st.session_state["cam_name_input"] = ""
                if "cam_phone_input" not in st.session_state:
                    st.session_state["cam_phone_input"] = ""
                if "cam_apt_type_val" not in st.session_state:
                    st.session_state["cam_apt_type_val"] = ""

                col_bld_in, col_apt_in, col_fetch_btn = st.columns([1.5, 1.5, 1])
                with col_bld_in:
                    entered_bld = st.text_input("العمارة:", placeholder="مثال: 1", key="cam_bld_input")
                with col_apt_in:
                    entered_apt = st.text_input("الشقة:", placeholder="مثال: 1", key="cam_apt_input")
                with col_fetch_btn:
                    st.write("")
                    st.write("")
                    if st.button("جلب ⚡", key="cam_fetch_btn", use_container_width=True):
                        data = get_apartment_info(entered_bld, entered_apt)
                        if data:
                            st.session_state["cam_name_input"] = data["resident_name"]
                            st.session_state["cam_phone_input"] = data["phone"]
                            st.session_state["cam_apt_type_val"] = data["apartment_type"]
                            st.rerun()
                        else:
                            st.warning("⚠️ لم يتم العثور على شقة بهذه البيانات في fm6.xlsx.")

                c_t1, c_t2 = st.columns(2)
                with c_t1:
                    curr_t = st.session_state.get("cam_apt_type_val", "")
                    idx_type = apt_types_list.index(curr_t) if curr_t in apt_types_list else 0
                    apartment_type = st.selectbox(
                        "نوع الشقة (F2, F3, ...):",
                        apt_types_list,
                        index=idx_type,
                        key=f"cam_apttype_box_{curr_t}",
                    )
                with c_t2:
                    name = st.text_input("اسم الساكن", value=st.session_state.get("cam_name_input", ""), key="cam_name_field")

                phone = st.text_input("رقم الهاتف", value=st.session_state.get("cam_phone_input", ""), key="cam_phone_field")
                car_desc = st.text_input("نوع ولون السيارة (اختياري)", key="cam_desc_in")

                if st.button("💾 حفظ الترقيم سحابياً في Supabase", type="primary", use_container_width=True):
                    if p_num:
                        p_num = clean_str(p_num)
                        p_reg = clean_str(p_reg)
                        full_plate_str = f"{p_num} | {p_let} | {p_reg}"
                        add_record(
                            entered_bld,
                            entered_apt,
                            apartment_type,
                            name,
                            phone,
                            p_num,
                            p_let,
                            p_reg,
                            full_plate_str,
                            car_type,
                            car_desc,
                            "",
                        )
                        st.session_state["cam_name_input"] = ""
                        st.session_state["cam_phone_input"] = ""
                        st.session_state["cam_apt_type_val"] = ""
                        st.success("✅ تم الحفظ السحابي بنجاح في Supabase!")
                        st.rerun()
                    else:
                        st.error("يرجى كتابة رقم اللوحة.")
        else:
            st.warning("تعذر قراءة أرقام واضحة، حاول التقاط صورة أقرب قليلاً للوحة.")

# ==================== 2. قسم الاستعلام الشامل في الجدولين ====================
elif st.session_state.active_tab == "search":
    st.subheader("🔍 استعلام وبحث فوري شامل")
    st.caption("البحث التلقائي يشمل: جدول سيارات الموقف (Supabase Cloud) + دليل الشقق والسكان (fm6):")

    with st.form("search_form"):
        col_in, col_bt = st.columns([3, 1])
        with col_in:
            query = st.text_input(
                "🔎 اكتب رقم اللوحة، اسم الساكن، رقم العمارة، الشقة، أو الهاتف:",
                value="",
                placeholder="",
                label_visibility="collapsed",
            )
        with col_bt:
            search_submitted = st.form_submit_button("🔍 ابحث الآن", type="primary", use_container_width=True)

    if query:
        df_cars = get_all_records()
        cars_found = False

        if not df_cars.empty:
            mask_car = (
                df_cars["plate_number"].astype(str).str.contains(query)
                | df_cars["building"].astype(str).str.contains(query)
                | df_cars["apartment"].astype(str).str.contains(query)
                | df_cars["apartment_type"].astype(str).str.contains(query, case=False)
                | df_cars["car_type"].astype(str).str.contains(query, case=False)
                | df_cars["phone"].astype(str).str.contains(query)
                | df_cars["resident_name"].astype(str).str.contains(query, case=False)
            )
            res_cars = df_cars[mask_car]
            if not res_cars.empty:
                cars_found = True
                st.markdown(f"### 🚗 نتائج موقف السيارات السحابي ({len(res_cars)} سيارة)")
                for _, r in res_cars.iterrows():
                    render_car_card(r, allow_edit=True)

        df_dir_all = load_fm6_directory()
        dir_found = False

        if not df_dir_all.empty:
            mask_dir = (
                df_dir_all["resident_name"].astype(str).str.contains(query, case=False)
                | df_dir_all["phone"].astype(str).str.contains(query)
                | df_dir_all["building"].astype(str).str.contains(query)
                | df_dir_all["apartment"].astype(str).str.contains(query)
            )
            res_dir = df_dir_all[mask_dir]
            if not res_dir.empty:
                dir_found = True
                st.markdown(f"### 🏢 نتائج دليل الشقق والسكان (fm6) ({len(res_dir)} ساكن)")
                for _, r_dir in res_dir.iterrows():
                    render_directory_card(r_dir)

        if not cars_found and not dir_found:
            st.info("لم يتم العثور على أي تطابق في موقف السيارات ولا في دليل الشقق والسكان.")

# ==================== 3. قسم التسجيل اليدوي ====================
elif st.session_state.active_tab == "add":
    st.subheader("➕ تسجيل سيارة يدوياً")

    if "manual_name_input" not in st.session_state:
        st.session_state["manual_name_input"] = ""
    if "manual_phone_input" not in st.session_state:
        st.session_state["manual_phone_input"] = ""
    if "manual_apt_type_val" not in st.session_state:
        st.session_state["manual_apt_type_val"] = ""

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        p_num = st.text_input("أرقام اللوحة *", placeholder="78954", key="m_p_num")
    with c2:
        p_let = st.selectbox("حرف اللوحة", letters_list, key="m_p_let")
    with c3:
        p_reg = st.text_input("العمالة", placeholder="26", key="m_p_reg")

    car_type = st.radio("صفة الساكن:", status_options, horizontal=True, key="m_car_type")

    st.markdown("🏢 **تحديد العمارة والشقة:**")
    col_mbld, col_mapt, col_mbtn = st.columns([1.5, 1.5, 1])
    with col_mbld:
        m_bld = st.text_input("العمارة:", placeholder="مثال: 1", key="m_bld_in")
    with col_mapt:
        m_apt = st.text_input("الشقة:", placeholder="مثال: 1", key="m_apt_in")
    with col_mbtn:
        st.write("")
        st.write("")
        if st.button("جلب ⚡", key="m_fetch_btn", use_container_width=True):
            m_data = get_apartment_info(m_bld, m_apt)
            if m_data:
                st.session_state["manual_name_input"] = m_data["resident_name"]
                st.session_state["manual_phone_input"] = m_data["phone"]
                st.session_state["manual_apt_type_val"] = m_data["apartment_type"]
                st.rerun()
            else:
                st.warning("⚠️ لم يتم العثور على شقة بهذه الأرقام في ملف fm6.xlsx.")

    c_ma1, c_ma2 = st.columns(2)
    with c_ma1:
        curr_m_type = st.session_state.get("manual_apt_type_val", "")
        m_type_idx = apt_types_list.index(curr_m_type) if curr_m_type in apt_types_list else 0
        m_apt_type = st.selectbox(
            "نوع الشقة:",
            apt_types_list,
            index=m_type_idx,
            key=f"manual_apttype_box_{curr_m_type}",
        )
    with c_ma2:
        name = st.text_input("اسم الساكن", value=st.session_state.get("manual_name_input", ""), key="m_name_field")

    phone = st.text_input("رقم الهاتف", value=st.session_state.get("manual_phone_input", ""), key="m_phone_field")
    car_desc = st.text_input("نوع ولون السيارة", placeholder="مثال: داسيا بيضاء", key="m_car_desc")

    if st.button("💾 حفظ في Supabase سحابياً", type="primary", use_container_width=True):
        if p_num:
            p_num = clean_str(p_num)
            p_reg = clean_str(p_reg)
            df = get_all_records()
            if not df.empty and not df[df["plate_number"].astype(str) == str(p_num)].empty:
                st.error(f"⛔ اللوحة ({p_num}) مسجلة مسبقاً بالفعل في المنظومة!")
            else:
                full_plate_str = f"{p_num} | {p_let} | {p_reg}"
                add_record(
                    m_bld,
                    m_apt,
                    m_apt_type,
                    name,
                    phone,
                    p_num,
                    p_let,
                    p_reg,
                    full_plate_str,
                    car_type,
                    car_desc,
                    "",
                )
                st.session_state["manual_name_input"] = ""
                st.session_state["manual_phone_input"] = ""
                st.session_state["manual_apt_type_val"] = ""
                st.success("✅ تم الحفظ بنجاح في Supabase!")
                st.rerun()
        else:
            st.error("أدخل رقم اللوحة على الأقل.")

# ==================== 4. قسم الإدارة ====================
elif st.session_state.active_tab == "admin":
    st.subheader("🔒 إدارة المنظومة وقاعدة البيانات السحابية")

    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        st.markdown('<div class="highlight-pin-box">', unsafe_allow_html=True)
        with st.form("pin_form"):
            admin_pass = st.text_input(
                "🔐 أدخل القن السري للوصول للوحة الإدارة:",
                type="password",
                value="",
                placeholder="",
            )
            pin_submit = st.form_submit_button("🔓 تأكيد الدخول", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if pin_submit:
            if admin_pass == ADMIN_PIN:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("⛔ القن السري غير صحيح. يرجى إعادة المحاولة.")

    if st.session_state.admin_authenticated:
        st.success("🔓 تم الدخول كمسؤول للمنظومة.")

        df_dir_check = load_fm6_directory()
        st.info(f"🏢 دليل الشقق المحمل من المستودع (fm6.xlsx): **{len(df_dir_check)} شقة** جاهزة للربط الفوري.")

        df = get_all_records()

        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.success("☁️ قاعدة البيانات السحابية (Supabase): **متصلة بنجاح**.")
        with col_stat2:
            st.info(f"🚗 سيارات الموقف المحفوظة سحابياً: **{len(df)} سيارة**.")

        if not df.empty:
            st.markdown("---")
            m1, m2, m3 = st.columns(3)
            m1.metric("إجمالي السيارات في السحاب", len(df))
            m2.metric(
                "مكتملة البيانات",
                df["apartment"].replace("", np.nan).dropna().count(),
            )
            missing_count = df["apartment"].replace("", np.nan).isna().sum()
            m3.metric("بحاجة لإكمال الشقة ⚠️", missing_count)

            st.markdown("---")
            st.subheader("📋 قائمة السيارات المسجلة (اضغط على أي سيارة للتعديل أو الحذف)")
            st.caption("اضغط على زر [✏️ تعديل / حذف] لفتح معطيات الساكن وتعديل اسمه أو حذفه:")

            for _, r_car in df.iterrows():
                render_car_card(r_car, allow_edit=True)

            st.markdown("---")
            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="السيارات")
            towrite.seek(0)

            st.download_button(
                label="📥 تنزيل نسخة احتياطية Excel (.xlsx) لكافة السيارات",
                data=towrite,
                file_name=f"residence_cars_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.info("لا توجد سيارات مسجلة بعد في Supabase.")
