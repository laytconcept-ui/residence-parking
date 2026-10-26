import io
import os
import re
import time
from datetime import datetime
import json
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(
    page_title="تدبير موقف سيارات إقامة نفيس",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----------------- تثبيت أيقونة التطبيق وتوجيه الكاميرا الخلفية تلقائياً -----------------
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
    // إجبار متصفح الهاتف على فتح الكاميرا الخلفية
    navigator.mediaDevices.getUserMedia = (function(origGetUserMedia) {
        return function(constraints) {
            if (constraints && constraints.video) {
                if (typeof constraints.video === 'object') {
                    constraints.video.facingMode = { ideal: "environment" };
                } else {
                    constraints.video = { facingMode: { ideal: "environment" } };
                }
            }
            return origGetUserMedia.apply(this, arguments);
        };
    })(navigator.mediaDevices.getUserMedia);
    </script>
""",
    unsafe_allow_html=True,
)

ADMIN_PIN = "1234"
RESIDENCE_FILE = "residence.xlsx"

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


def normalize_num(val):
    s = clean_str(val)
    if not s:
        return ""
    s = s.lstrip("0")
    return s if s else "0"


def clean_apt_type(val):
    s = clean_str(val).upper().replace(" ", "")
    for t in ["F2", "F3", "F4", "F5"]:
        if t in s:
            return t
    return s if s else ""


def format_moroccan_phone(phone_val):
    p = clean_str(phone_val).replace(" ", "").replace("-", "")
    if not p:
        return ""
    if len(p) == 9 and p.startswith(("6", "7", "5")):
        p = "0" + p
    return p


# ----------------- قراءة وإدارة ملف residence.xlsx كقاعدة بيانات -----------------
def load_residence_file():
    cols = [
        "id", "building", "apartment", "apartment_type", "resident_name",
        "phone", "plate_number", "plate_letter", "plate_region",
        "full_plate", "car_type", "car_info", "created_at", "notes"
    ]
    target_path = None
    for fname in [RESIDENCE_FILE, "Residence.xlsx", "residence.xls", "Residence.xls"]:
        if os.path.exists(fname):
            target_path = fname
            break

    if target_path:
        try:
            df = pd.read_excel(target_path, dtype=str)
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            for c in df.columns:
                df[c] = df[c].apply(clean_str)
            df["phone"] = df["phone"].apply(format_moroccan_phone)
            df["apartment_type"] = df["apartment_type"].apply(clean_apt_type)
            return df
        except Exception:
            pass

    df_init = pd.DataFrame(INITIAL_CARS_BACKUP, columns=cols)
    try:
        df_init.to_excel(RESIDENCE_FILE, index=False)
    except Exception:
        pass
    return df_init


if "cars_df" not in st.session_state:
    st.session_state.cars_df = load_residence_file()


def save_df_to_residence_file():
    try:
        st.session_state.cars_df.to_excel(RESIDENCE_FILE, index=False)
    except Exception as e:
        st.error(f"خطأ أثناء الكتابة في ملف الإكسيل: {e}")


def get_all_records():
    df = st.session_state.cars_df.copy()
    for col in df.columns:
        df[col] = df[col].apply(clean_str)
    if "phone" in df.columns:
        df["phone"] = df["phone"].apply(format_moroccan_phone)
    return df


def add_record(building, apartment, apartment_type, name, phone, plate_num, plate_let, plate_reg, full_plate, car_type, car_info, notes):
    df = st.session_state.cars_df
    try:
        new_id = int(pd.to_numeric(df["id"], errors="coerce").max()) + 1 if not df.empty else 1
    except Exception:
        new_id = len(df) + 1

    new_row = {
        "id": new_id,
        "building": clean_str(building),
        "apartment": clean_str(apartment),
        "apartment_type": clean_apt_type(apartment_type),
        "resident_name": clean_str(name),
        "phone": format_moroccan_phone(phone),
        "plate_number": clean_str(plate_num),
        "plate_letter": str(plate_let),
        "plate_region": clean_str(plate_reg),
        "full_plate": clean_str(full_plate),
        "car_type": clean_str(car_type),
        "car_info": clean_str(car_info),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "notes": clean_str(notes)
    }
    st.session_state.cars_df = pd.concat([pd.DataFrame([new_row]), df], ignore_index=True)
    save_df_to_residence_file()


def update_full_record(record_id, building, apartment, apartment_type, name, phone, plate_num, plate_let, plate_reg, full_plate, car_type, car_info, notes):
    df = st.session_state.cars_df
    idx = df[df["id"].astype(str) == str(record_id)].index
    if not idx.empty:
        df.loc[idx, "building"] = clean_str(building)
        df.loc[idx, "apartment"] = clean_str(apartment)
        df.loc[idx, "apartment_type"] = clean_apt_type(apartment_type)
        df.loc[idx, "resident_name"] = clean_str(name)
        df.loc[idx, "phone"] = format_moroccan_phone(phone)
        df.loc[idx, "plate_number"] = clean_str(plate_num)
        df.loc[idx, "plate_letter"] = str(plate_let)
        df.loc[idx, "plate_region"] = clean_str(plate_reg)
        df.loc[idx, "full_plate"] = clean_str(full_plate)
        df.loc[idx, "car_type"] = clean_str(car_type)
        df.loc[idx, "car_info"] = clean_str(car_info)
        df.loc[idx, "notes"] = clean_str(notes)
        st.session_state.cars_df = df
        save_df_to_residence_file()


def delete_record(record_id):
    df = st.session_state.cars_df
    st.session_state.cars_df = df[df["id"].astype(str) != str(record_id)].reset_index(drop=True)
    save_df_to_residence_file()


# ----------------- نافذة التعديل والحذف المنبثقة -----------------
@st.dialog("✏️ تعديل بيانات السيارة والساكن أو الحذف")
def edit_car_dialog(row):
    rec_id = int(row["id"])
    st.caption(f"معرف السجل: #{rec_id}")

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
        dlg_name = st.text_input("اسم الساكن", value=str(row["resident_name"]) if pd.notna(row["resident_name"]) else "", key=f"dlg_name_{rec_id}")
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
        if st.button("✅ تأكيد وحفظ التعديلات", type="primary", use_container_width=True, key=f"save_dlg_{rec_id}"):
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
            st.success("✅ تم تحديث بيانات السيارة بنجاح!")
            st.rerun()

    with btn_col2:
        if st.button("🗑️ تأكيد حذف السجل نهائياً", use_container_width=True, key=f"del_dlg_{rec_id}"):
            delete_record(rec_id)
            st.warning("🗑️ تم حذف السجل نهائياً من ملف residence.xlsx!")
            st.rerun()


# ----------------- قراءة دليل الشقق والسكان fm6.xlsx -----------------
@st.cache_data
def load_fm6_directory():
    target_file = None
    for fname in os.listdir("."):
        if "fm6" in fname.lower() and fname.endswith((".xlsx", ".xls")):
            target_file = fname
            break

    if not target_file:
        return pd.DataFrame(columns=["building", "apartment", "apartment_type", "resident_name", "phone"])

    try:
        excel_obj = pd.ExcelFile(target_file)
        df = pd.read_excel(excel_obj, sheet_name=0, dtype=str)

        for i in range(min(5, len(df))):
            row_vals = [str(v).lower().strip() for v in df.iloc[i].values]
            if any(x in row_vals for x in ["apartment", "شقة", "immeuble", "building", "عمارة", "app"]):
                df.columns = df.iloc[i]
                df = df[i + 1 :].reset_index(drop=True)
                break

        col_map = {}
        for col in df.columns:
            c_lower = str(col).lower().strip()
            if any(k in c_lower for k in ["apt", "app", "شقة", "شقه", "logement", "porte"]):
                col_map[col] = "apartment"
            elif any(k in c_lower for k in ["bld", "imm", "عمارة", "عماره", "batiment"]):
                col_map[col] = "building"
            elif any(k in c_lower for k in ["type", "typologie", "صنف", "نوع"]):
                col_map[col] = "apartment_type"
            elif any(k in c_lower for k in ["nom", "name", "prenom", "ساكن", "مالك", "اسم", "resident", "client"]):
                col_map[col] = "resident_name"
            elif any(k in c_lower for k in ["tel", "gsm", "phone", "هاتف", "جوال", "contact"]):
                col_map[col] = "phone"

        df = df.rename(columns=col_map)
        df = df.loc[:, ~df.columns.duplicated()]

        for col in ["building", "apartment", "apartment_type", "resident_name", "phone"]:
            if col not in df.columns:
                df[col] = ""
            else:
                df[col] = df[col].apply(clean_str)

        df["phone"] = df["phone"].apply(format_moroccan_phone)
        df["apartment_type"] = df["apartment_type"].apply(clean_apt_type)
        return df
    except Exception:
        return pd.DataFrame(columns=["building", "apartment", "apartment_type", "resident_name", "phone"])


def get_apartment_info(bld_num, apt_num):
    b_norm = normalize_num(bld_num)
    a_norm = normalize_num(apt_num)

    if not a_norm:
        return None

    df_dir = load_fm6_directory()
    if df_dir.empty:
        return None

    df_dir_copy = df_dir.copy()
    df_dir_copy["b_norm"] = df_dir_copy["building"].apply(normalize_num)
    df_dir_copy["a_norm"] = df_dir_copy["apartment"].apply(normalize_num)

    if b_norm:
        match = df_dir_copy[(df_dir_copy["b_norm"] == b_norm) & (df_dir_copy["a_norm"] == a_norm)]
    else:
        match = df_dir_copy[df_dir_copy["a_norm"] == a_norm]

    if not match.empty:
        r = match.iloc[0]
        return {
            "building": clean_str(r.get("building", "")),
            "apartment_type": clean_apt_type(r.get("apartment_type", "")),
            "resident_name": clean_str(r.get("resident_name", "")),
            "phone": format_moroccan_phone(r.get("phone", "")),
        }
    return None


# ----------------- التعرف فائق السرعة عبر الذكاء البصري مع حماية 503 -----------------
# ----------------- التعرف الفوري السريع جداً (Lightning Fast Vision) -----------------
def analyze_plate_with_vision(image_bytes):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            api_key = None

    if not api_key:
        return None, "يرجى إضافة مفتاح GEMINI_API_KEY في إعدادات Streamlit Secrets."

    try:
        # 1. تقليص حجم الصورة إلى 25KB فقط لتُرفع عبر الإنترنت فورياً
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img.thumbnail((640, 640), Image.Resampling.BILINEAR)
        
        buffered = io.BytesIO()
        pil_img.save(buffered, format="JPEG", quality=60, optimize=True)
        optimized_bytes = buffered.getvalue()

        # 2. أمر استخراج مباشر وبسيط بدون تعقيدات
        client = genai.Client(api_key=api_key)
        prompt = """Extract Moroccan license plate as JSON:
{"plate_number": "12345", "plate_letter": "د", "plate_region": "26", "car_desc": "car make color"}"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",  # أو gemini-3.8-flash المتاح لديك
            contents=[
                types.Part.from_bytes(data=optimized_bytes, mime_type="image/jpeg"),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=0)  # إلغاء وقت التفكير لسرعة فورية
            )
        )

        clean_txt = response.text.strip()
        clean_txt = re.sub(r"^```json\s*", "", clean_txt)
        clean_txt = re.sub(r"\s*```$", "", clean_txt)
        result_json = json.loads(clean_txt)
        return result_json, None

    except Exception as e:
        return None, f"خطأ: {e}"

# ----------------- تصميم CSS المطور -----------------
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');
    
    header[data-testid="stHeader"], #MainMenu, footer, .stDeployButton { display: none !important; }
    
    [data-testid="InputInstructions"], 
    .stTextInput small, 
    div[data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }

    html, body, [class*="css"], .stApp {
        font-family: 'Cairo', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        background-color: #f8fafc;
        direction: rtl;
        text-align: right;
    }
    
    h1, h2, h3, [data-testid="stHeadingWithActionElements"] h2, .section-header {
        text-align: center !important;
        justify-content: center !important;
    }

    .app-top-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #2563eb 100%);
        border-radius: 18px;
        padding: 16px 20px;
        margin-bottom: 16px;
        color: white;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.2);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        gap: 6px;
    }

    div[data-baseweb="input"], .stTextInput > div > div > input {
        background-color: #ffffff !important;
        border: 2px solid #3b82f6 !important;
        border-radius: 12px !important;
        color: #0f172a !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 5px rgba(59, 130, 246, 0.08) !important;
    }

    .stTextInput > div > div > input:focus, 
    div[data-baseweb="input"]:focus-within {
        border-color: #1d4ed8 !important;
        background-color: #ffffff !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25) !important;
    }

    .stSelectbox div[data-baseweb="select"] {
        border: 2px solid #3b82f6 !important;
        border-radius: 12px !important;
        background-color: #ffffff !important;
        font-weight: 700 !important;
    }

    .morocco-plate-tag {
        display: inline-flex;
        align-items: center;
        background: #ffffff;
        border: 2px solid #0f172a;
        border-radius: 10px;
        padding: 6px 14px;
        gap: 12px;
        margin-bottom: 8px;
    }
    .plate-item { font-size: 20px; font-weight: 900; color: #0f172a; }
    .plate-divider { width: 2px; height: 22px; background-color: #cbd5e1; }
    
    div.stButton > button {
        border-radius: 12px !important;
        padding: 10px 18px !important;
        font-size: 15px !important;
        font-weight: 800 !important;
        transition: all 0.2s ease !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


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
        st.markdown(
            f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div class="morocco-plate-tag">
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

        c_i1, c_i2 = st.columns(2)
        with c_i1:
            apt_disp = f"{apt} ({apt_type})" if apt_type else (apt if apt else "—")
            st.markdown(f"🏢 **العمارة:** `{bld if bld else '—'}` &nbsp;&nbsp;|&nbsp;&nbsp; 🚪 **الشقة:** `{apt_disp}`")
            st.markdown(f"👤 **الساكن:** {row['resident_name'] if pd.notna(row['resident_name']) and row['resident_name'] else 'غير محدد'}")
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

        if allow_edit:
            st.write("")
            if st.button("✏️ تعديل أو حذف هذه السيارة", key=f"btn_edit_card_{rec_id}", use_container_width=True):
                edit_car_dialog(row)


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
                📋 مسجل في دليل الشقق (fm6.xlsx)
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
    <h2 style="margin: 0; font-size: 21px; color: white;">🚗 تدبير موقف سيارات إقامة نفيس</h2>
    <div style="font-size: 11px; opacity: 0.85;">منظومة تسيير متكاملة عبر ملف residence.xlsx</div>
    <div style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; margin-top: 4px;">
        AI Vision Engine ⚡
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
    if st.session_state.get("reset_cam_form", False):
        st.session_state["cam_bld_in"] = ""
        st.session_state["cam_apt_in"] = ""
        st.session_state["cam_desc_in"] = ""
        st.session_state["cam_pnum"] = ""
        st.session_state["cam_preg"] = ""
        st.session_state["cam_name_widget"] = ""
        st.session_state["cam_phone_widget"] = ""
        st.session_state["cam_apttype_widget"] = apt_types_list[0]
        st.session_state["reset_cam_form"] = False

    if "cam_name_widget" not in st.session_state:
        st.session_state["cam_name_widget"] = ""
    if "cam_phone_widget" not in st.session_state:
        st.session_state["cam_phone_widget"] = ""
    if "cam_apttype_widget" not in st.session_state:
        st.session_state["cam_apttype_widget"] = apt_types_list[0]
    if "cam_desc_in" not in st.session_state:
        st.session_state["cam_desc_in"] = ""

    st.subheader("📷 التقاط لوحة السيارة")

    cam_tab1, cam_tab2 = st.tabs(["📸 كاميرا الشاشة المباشرة", "📱 الكاميرا الخلفية الأصلية للهاتف"])

    camera_file = None
    with cam_tab1:
        camera_file = st.camera_input("التقاط عبر الكاميرا الخلفية المباشرة")

    with cam_tab2:
        uploaded_camera = st.file_uploader(
            "📷 انقر هنا لفتح الكاميرا الخلفية للهاتف والتقاط الصورة مباشرة:",
            type=["jpg", "jpeg", "png"],
            key="mobile_env_camera_upload"
        )
        if uploaded_camera is not None:
            camera_file = uploaded_camera

    if camera_file is not None:
        img_bytes = camera_file.getvalue()

        if st.session_state.get("last_processed_img") != img_bytes:
            with st.spinner("⚡ جاري استيعاب الصورة وقراءة ترقيم اللوحة بالذكاء البصري..."):
                plate_data, err = analyze_plate_with_vision(img_bytes)
                if err:
                    st.error(err)
                elif plate_data:
                    st.session_state["cam_pnum"] = plate_data.get("plate_number", "")
                    p_let = plate_data.get("plate_letter", "")
                    st.session_state["cam_plet_val"] = p_let if p_let in letters_list else ""
                    st.session_state["cam_preg"] = plate_data.get("plate_region", "")
                    if plate_data.get("car_desc"):
                        st.session_state["cam_desc_in"] = plate_data.get("car_desc")
                    st.session_state["last_processed_img"] = img_bytes

        main_num = st.session_state.get("cam_pnum", "")
        detected_let = st.session_state.get("cam_plet_val", "")
        region_num = st.session_state.get("cam_preg", "")
        full_display = f"{main_num} | {detected_let if detected_let else '-'} | {region_num if region_num else '-'}"

        if main_num:
            df = get_all_records()
            exist_match = df[df["plate_number"].astype(str) == str(main_num)] if not df.empty else pd.DataFrame()

            if not exist_match.empty:
                st.warning("⚠️ هذه اللوحة مسجلة مسبقاً في النظام:")
                for _, row in exist_match.iterrows():
                    render_car_card(row, allow_edit=True)
            else:
                st.success(f"🎯 ترقيم مرصود بدقة: **{full_display}**")

                c_p1, c_p2, c_p3 = st.columns([2, 1, 1])
                with c_p1:
                    p_num = st.text_input("أرقام اللوحة *", value=main_num, key="cam_pnum")
                with c_p2:
                    idx = letters_list.index(detected_let) if detected_let in letters_list else 0
                    p_let = st.selectbox("الحرف", letters_list, index=idx, key="cam_plet")
                with c_p3:
                    p_reg = st.text_input("العمالة", value=region_num, key="cam_preg")

                car_type = st.radio("صفة الساكن/السيارة:", status_options, horizontal=True, key="cam_status_radio")

                st.markdown("---")
                st.markdown("🏢 **تحديد العمارة والشقة لجلب الساكن فوراً:**")

                col_bld_in, col_apt_in, col_fetch_btn = st.columns([1.5, 1.5, 1])
                with col_bld_in:
                    entered_bld = st.text_input("العمارة:", key="cam_bld_in")
                with col_apt_in:
                    entered_apt = st.text_input("الشقة:", key="cam_apt_in")
                with col_fetch_btn:
                    st.write("")
                    st.write("")
                    if st.button("جلب ⚡", key="cam_fetch_btn", use_container_width=True):
                        data = get_apartment_info(entered_bld, entered_apt)
                        if data:
                            st.session_state["cam_name_widget"] = data["resident_name"]
                            st.session_state["cam_phone_widget"] = data["phone"]
                            apt_t = data["apartment_type"]
                            st.session_state["cam_apttype_widget"] = apt_t if apt_t in apt_types_list else apt_types_list[0]
                            st.rerun()
                        else:
                            st.warning("⚠️ لم يتم العثور على شقة بهذه البيانات في fm6.xlsx.")

                c_t1, c_t2 = st.columns(2)
                with c_t1:
                    apartment_type = st.selectbox(
                        "نوع الشقة:",
                        apt_types_list,
                        key="cam_apttype_widget",
                    )
                with c_t2:
                    name = st.text_input("اسم الساكن", key="cam_name_widget")

                phone = st.text_input("رقم الهاتف", key="cam_phone_widget")
                car_desc = st.text_input("نوع ولون السيارة", value=st.session_state.get("cam_desc_in", ""), key="cam_desc_in")

                if st.button("✅ تأكيد حفظ السيارة في residence.xlsx", type="primary", use_container_width=True):
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
                        st.session_state["reset_cam_form"] = True
                        st.session_state["last_processed_img"] = None
                        st.success("✅ تم حفظ السيارة بنجاح في ملف residence.xlsx!")
                        st.rerun()
                    else:
                        st.error("يرجى كتابة رقم اللوحة.")

# ==================== 2. قسم الاستعلام الشامل ====================
elif st.session_state.active_tab == "search":
    st.subheader("🔍 استعلام وبحث فوري شامل")
    
    with st.expander("🏢 استعلام مباشر وسريع برقم العمارة والشقة (جلب ⚡)", expanded=True):
        col_sbld, col_sapt, col_sbtn = st.columns([1.5, 1.5, 1])
        with col_sbld:
            search_bld = st.text_input("رقم العمارة:", key="search_bld_input")
        with col_sapt:
            search_apt = st.text_input("رقم الشقة:", key="search_apt_input")
        with col_sbtn:
            st.write("")
            st.write("")
            fetch_apt_clicked = st.button("🔍 تأكيد جلب الشقة", key="btn_fetch_in_search", type="primary", use_container_width=True)

        if fetch_apt_clicked:
            if search_apt:
                apt_data = get_apartment_info(search_bld, search_apt)
                if apt_data:
                    st.success("🎯 تم جلب بيانات الشقة بنجاح من fm6.xlsx:")
                    render_directory_card(apt_data)

                    df_all_cars = get_all_records()
                    if not df_all_cars.empty:
                        b_norm = normalize_num(search_bld)
                        a_norm = normalize_num(search_apt)
                        if b_norm:
                            matched_cars = df_all_cars[
                                (df_all_cars["building"].apply(normalize_num) == b_norm) &
                                (df_all_cars["apartment"].apply(normalize_num) == a_norm)
                            ]
                        else:
                            matched_cars = df_all_cars[df_all_cars["apartment"].apply(normalize_num) == a_norm]

                        if not matched_cars.empty:
                            st.markdown(f"#### 🚗 السيارات المسجلة لهذه الشقة ({len(matched_cars)} سيارة):")
                            for _, car_r in matched_cars.iterrows():
                                render_car_card(car_r, allow_edit=True)
                        else:
                            st.info("ℹ️ لا توجد سيارات مسجلة لهذه الشقة بعد في ملف residence.xlsx.")
                else:
                    st.warning("⚠️ لم يتم العثور على شقة بهذه الأرقام في دليل الشقق fm6.xlsx.")
            else:
                st.error("يرجى كتابة رقم الشقة على الأقل.")

    st.markdown("---")
    st.caption("أو ابحث عن أي نص عام (رقم اللوحة، اسم الساكن، الهاتف، العمارة):")

    with st.form("search_form"):
        col_in, col_bt = st.columns([3.5, 1.2])
        with col_in:
            query = st.text_input(
                "🔎 خانة البحث العام:",
                value="",
                label_visibility="collapsed",
            )
        with col_bt:
            search_submitted = st.form_submit_button("🔍 تأكيد البحث", type="primary", use_container_width=True)

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
                st.markdown(f"### 🚗 نتائج موقف السيارات (residence.xlsx) ({len(res_cars)} سيارة)")
                for _, r in res_cars.iterrows():
                    render_car_card(r, allow_edit=True)

        df_dir = load_fm6_directory()
        dir_found = False

        if not df_dir.empty:
            q_norm = normalize_num(query)
            mask_dir = (
                df_dir["resident_name"].astype(str).str.contains(query, case=False)
                | df_dir["phone"].astype(str).str.contains(query)
                | (df_dir["building"].apply(normalize_num) == q_norm)
                | (df_dir["apartment"].apply(normalize_num) == q_norm)
            )
            res_dir = df_dir[mask_dir]
            if not res_dir.empty:
                dir_found = True
                st.markdown(f"### 🏢 نتائج دليل الشقق والسكان (fm6.xlsx) ({len(res_dir)} ساكن)")
                for _, r_dir in res_dir.iterrows():
                    render_directory_card(r_dir)

        if not cars_found and not dir_found:
            st.info("لم يتم العثور على أي تطابق في موقف السيارات ولا في دليل الشقق.")

# ==================== 3. قسم التسجيل اليدوي ====================
elif st.session_state.active_tab == "add":
    if st.session_state.get("reset_manual_form", False):
        st.session_state["m_p_num"] = ""
        st.session_state["m_p_reg"] = ""
        st.session_state["m_bld_in"] = ""
        st.session_state["m_apt_in"] = ""
        st.session_state["m_car_desc"] = ""
        st.session_state["manual_name_widget"] = ""
        st.session_state["manual_phone_widget"] = ""
        st.session_state["manual_apttype_widget"] = apt_types_list[0]
        st.session_state["reset_manual_form"] = False

    st.subheader("➕ تسجيل سيارة يدوياً")

    if "manual_name_widget" not in st.session_state:
        st.session_state["manual_name_widget"] = ""
    if "manual_phone_widget" not in st.session_state:
        st.session_state["manual_phone_widget"] = ""
    if "manual_apttype_widget" not in st.session_state:
        st.session_state["manual_apttype_widget"] = apt_types_list[0]

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        p_num = st.text_input("أرقام اللوحة *", key="m_p_num")
    with c2:
        p_let = st.selectbox("حرف اللوحة", letters_list, key="m_p_let")
    with c3:
        p_reg = st.text_input("العمالة", key="m_p_reg")

    car_type = st.radio("صفة الساكن:", status_options, horizontal=True, key="m_car_type")

    st.markdown("🏢 **تحديد العمارة والشقة:**")
    col_mbld, col_mapt, col_mbtn = st.columns([1.5, 1.5, 1])
    with col_mbld:
        m_bld = st.text_input("العمارة:", key="m_bld_in")
    with col_mapt:
        m_apt = st.text_input("الشقة:", key="m_apt_in")
    with col_mbtn:
        st.write("")
        st.write("")
        if st.button("جلب ⚡", key="m_fetch_btn", use_container_width=True):
            m_data = get_apartment_info(m_bld, m_apt)
            if m_data:
                st.session_state["manual_name_widget"] = m_data["resident_name"]
                st.session_state["manual_phone_widget"] = m_data["phone"]
                apt_t = m_data["apartment_type"]
                st.session_state["manual_apttype_widget"] = apt_t if apt_t in apt_types_list else apt_types_list[0]
                st.rerun()
            else:
                st.warning("⚠️ لم يتم العثور على شقة بهذه الأرقام في ملف fm6.xlsx.")

    c_ma1, c_ma2 = st.columns(2)
    with c_ma1:
        m_apt_type = st.selectbox(
            "نوع الشقة:",
            apt_types_list,
            key="manual_apttype_widget",
        )
    with c_ma2:
        name = st.text_input(
            "اسم الساكن",
            key="manual_name_widget"
        )

    phone = st.text_input(
        "رقم الهاتف",
        key="manual_phone_widget"
    )
    car_desc = st.text_input("نوع ولون السيارة", key="m_car_desc")

    if st.button("✅ تأكيد تسجيل السيارة في residence.xlsx", type="primary", use_container_width=True):
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
                st.session_state["reset_manual_form"] = True
                st.success("✅ تم حفظ السيارة في ملف residence.xlsx بنجاح!")
                st.rerun()
        else:
            st.error("أدخل رقم اللوحة على الأقل.")

# ==================== 4. قسم الإدارة وتنزيل Excel ====================
elif st.session_state.active_tab == "admin":
    st.subheader("🔒 إدارة المنظومة وملف residence.xlsx")

    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        with st.form("pin_form"):
            admin_pass = st.text_input(
                "🔐 أدخل القن السري للوصول للوحة الإدارة:",
                type="password",
                value="",
            )
            pin_submit = st.form_submit_button("🔓 تأكيد الدخول", type="primary", use_container_width=True)

        if pin_submit:
            if admin_pass == ADMIN_PIN:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("⛔ القن السري غير صحيح. يرجى إعادة المحاولة.")

    if st.session_state.admin_authenticated:
        st.success("🔓 تم الدخول كمسؤول للمنظومة.")
        df = get_all_records()

        st.markdown("---")
        df_fm6 = load_fm6_directory()
        if not df_fm6.empty:
            st.success(f"✅ تم تحميل دليل الشقق بنجاح من (fm6.xlsx): **{len(df_fm6)} شقة** مسجلة وجاهزة للربط الفوري.")
        else:
            st.warning("⚠️ لم يتم العثور على ملف fm6.xlsx بجانب app.py في المستودع.")

        if not df.empty:
            st.markdown("---")
            m1, m2, m3 = st.columns(3)
            m1.metric("إجمالي السيارات في residence.xlsx", len(df))
            m2.metric(
                "مكتملة البيانات",
                df["apartment"].replace("", np.nan).dropna().count(),
            )
            missing_count = df["apartment"].replace("", np.nan).isna().sum()
            m3.metric("بحاجة لإكمال الشقة ⚠️", missing_count)

            # تنزيل ملف الإكسيل المحين
            st.markdown("---")
            st.subheader("📥 تنزيل وتصدير ملف residence.xlsx المُحيّن")
            
            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="السيارات")
            towrite.seek(0)

            st.download_button(
                label="📥 تنزيل النسخة المحينة (residence.xlsx)",
                data=towrite,
                file_name="residence.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            # ----------------- الجدول الشامل التفاعلي -----------------
            st.markdown("---")
            st.subheader("📋 الجدول الشامل للسيارات")
            st.info("💡 **انقر على أي سطر في الجدول أسفله لفتح نافذة التعديل أو الحذف المباشر فوراً:**")

            display_cols = ["id", "full_plate", "building", "apartment", "apartment_type", "resident_name", "phone", "car_type", "car_info", "created_at"]
            df_display = df[[c for c in display_cols if c in df.columns]]

            selection_event = st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
            )

            selected_rows = selection_event.selection.get("rows", [])
            if selected_rows:
                selected_idx = selected_rows[0]
                selected_car_row = df.iloc[selected_idx]
                edit_car_dialog(selected_car_row)

        else:
            st.info("لا توجد سيارات مسجلة بعد.")

        st.markdown("---")
        with st.expander("📤 رفع واستبدال ملف residence.xlsx بالكامل يدوياً"):
            uploaded_excel = st.file_uploader("اختر ملف Excel لاستبدال سيارات الموقف", type=["xlsx", "xls"])
            if uploaded_excel is not None:
                if st.button("✅ تأكيد استبدال الملف بالكامل", type="primary"):
                    df_up = pd.read_excel(uploaded_excel)
                    for c in ["id", "building", "apartment", "apartment_type", "resident_name", "phone", "plate_number", "plate_letter", "plate_region", "full_plate", "car_type", "car_info", "created_at", "notes"]:
                        if c not in df_up.columns:
                            df_up[c] = ""
                    st.session_state.cars_df = df_up
                    save_df_to_residence_file()
                    st.success("✅ تم تحديث وتحميل بيانات ملف residence.xlsx بنجاح!")
                    st.rerun()
