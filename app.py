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


# ----------------- تحميل بيانات ملف residence.xlsx -----------------
def get_residence_file_path():
    for name in ["residence.xlsx", "Residence.xlsx", "residence.xls", "Residence.xls"]:
        if os.path.exists(name):
            return name
    return None

RESIDENCE_FILE = get_residence_file_path() or "residence.xlsx"

def load_initial_data():
    cols = [
        "id", "building", "apartment", "apartment_type", "resident_name", 
        "phone", "plate_number", "plate_letter", "plate_region", 
        "full_plate", "car_type", "car_info", "created_at", "notes"
    ]
    if os.path.exists(RESIDENCE_FILE):
        try:
            df = pd.read_excel(RESIDENCE_FILE)
            for col in cols:
                if col not in df.columns:
                    df[col] = ""
            return df
        except Exception:
            pass
    return pd.DataFrame(INITIAL_CARS_BACKUP, columns=cols)

if "cars_df" not in st.session_state:
    st.session_state.cars_df = load_initial_data()

def get_all_records():
    df = st.session_state.cars_df.copy()
    for col in df.columns:
        df[col] = df[col].apply(clean_str)
    if "phone" in df.columns:
        df["phone"] = df["phone"].apply(format_moroccan_phone)
    return df

def save_to_local_disk():
    try:
        st.session_state.cars_df.to_excel(RESIDENCE_FILE, index=False)
    except Exception:
        pass

def add_record(bld, apt, apt_t, name, phone, p_num, p_let, p_reg, full_plate, car_type, car_info, notes):
    df = st.session_state.cars_df
    try:
        new_id = int(df["id"].max()) + 1 if not df.empty and len(df) > 0 else 1
    except Exception:
        new_id = len(df) + 1

    new_row = {
        "id": new_id,
        "building": clean_str(bld),
        "apartment": clean_str(apt),
        "apartment_type": clean_apt_type(apt_t),
        "resident_name": clean_str(name),
        "phone": format_moroccan_phone(phone),
        "plate_number": clean_str(p_num),
        "plate_letter": str(p_let),
        "plate_region": clean_str(p_reg),
        "full_plate": clean_str(full_plate),
        "car_type": clean_str(car_type),
        "car_info": clean_str(car_info),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "notes": clean_str(notes)
    }
    st.session_state.cars_df = pd.concat([pd.DataFrame([new_row]), df], ignore_index=True)
    save_to_local_disk()

def update_full_record(rec_id, bld, apt, apt_t, name, phone, p_num, p_let, p_reg, full_plate, car_type, car_info, notes):
    df = st.session_state.cars_df
    idx = df[df["id"].astype(str) == str(rec_id)].index
    if not idx.empty:
        df.loc[idx, "building"] = clean_str(bld)
        df.loc[idx, "apartment"] = clean_str(apt)
        df.loc[idx, "apartment_type"] = clean_apt_type(apt_t)
        df.loc[idx, "resident_name"] = clean_str(name)
        df.loc[idx, "phone"] = format_moroccan_phone(phone)
        df.loc[idx, "plate_number"] = clean_str(p_num)
        df.loc[idx, "plate_letter"] = str(p_let)
        df.loc[idx, "plate_region"] = clean_str(p_reg)
        df.loc[idx, "full_plate"] = clean_str(full_plate)
        df.loc[idx, "car_type"] = clean_str(car_type)
        df.loc[idx, "car_info"] = clean_str(car_info)
        df.loc[idx, "notes"] = clean_str(notes)
        st.session_state.cars_df = df
        save_to_local_disk()

def delete_record(rec_id):
    df = st.session_state.cars_df
    st.session_state.cars_df = df[df["id"].astype(str) != str(rec_id)]
    save_to_local_disk()


# ----------------- دليل السكان fm6.xlsx -----------------
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


# ----------------- التعرف الضوئي والكاميرا -----------------
def clean_image_for_ocr(img_np):
    gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    return cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

def detect_and_crop_license_plate(image_np):
    h, w = image_np.shape[:2]
    gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 200)
    contours, _ = cv2.findContours(edged, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        aspect_ratio = float(cw) / float(ch) if ch > 0 else 0
        if 2.0 <= aspect_ratio <= 6.5 and cw > (w * 0.25) and ch > (h * 0.08):
            pad_x = int(cw * 0.05)
            pad_y = int(ch * 0.05)
            return image_np[max(0, y - pad_y):min(h, y + ch + pad_y), max(0, x - pad_x):min(w, x + cw + pad_x)], True
    return image_np, False

def parse_moroccan_plate(results):
    all_text = " ".join([r[1] for r in results]).strip()
    digits = re.findall(r"\d+", all_text)
    main_num, region_num, detected_let = "", "", ""

    for item in letters_list:
        if item and item in all_text:
            detected_let = item
            break

    if digits:
        main_num = max(digits, key=len)
        remaining = [d for d in digits if d != main_num]
        if remaining:
            region_num = remaining[0]

    full_display = f"{main_num} | {detected_let if detected_let else '-'} | {region_num}"
    return main_num, detected_let, region_num, full_display

@st.cache_resource
def get_ocr_reader():
    return easyocr.Reader(["ar", "en"], gpu=False)


# ----------------- واجهة CSS -----------------
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');
    header[data-testid="stHeader"], #MainMenu, footer, .stDeployButton { display: none !important; }
    html, body, [class*="css"], .stApp {
        font-family: 'Cairo', sans-serif !important;
        background-color: #f1f5f9;
        direction: rtl;
        text-align: right;
    }
    .app-top-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #2563eb 100%);
        border-radius: 18px;
        padding: 16px 20px;
        margin-bottom: 16px;
        color: white;
        display: flex;
        justify-content: space-between;
        align-items: center;
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
</style>
""",
    unsafe_allow_html=True,
)


# ----------------- نافذة التعديل المنبثقة -----------------
@st.dialog("✏️ تعديل بيانات الساكن والسيارة أو الحذف")
def edit_car_dialog(row):
    rec_id = int(row["id"])
    c_p1, c_p2, c_p3 = st.columns([2, 1, 1])
    with c_p1:
        dlg_pnum = st.text_input("أرقام اللوحة *", value=clean_str(row["plate_number"]), key=f"dlg_p_{rec_id}")
    with c_p2:
        let_val = row["plate_letter"] if pd.notna(row["plate_letter"]) and row["plate_letter"] in letters_list else ""
        dlg_plet = st.selectbox("الحرف", letters_list, index=letters_list.index(let_val) if let_val else 0, key=f"dlg_l_{rec_id}")
    with c_p3:
        dlg_preg = st.text_input("العمالة", value=clean_str(row["plate_region"]), key=f"dlg_r_{rec_id}")

    c1, c2, c3 = st.columns(3)
    with c1:
        dlg_bld = st.text_input("رقم العمارة", value=clean_str(row["building"]), key=f"dlg_b_{rec_id}")
    with c2:
        dlg_apt = st.text_input("رقم الشقة", value=clean_str(row["apartment"]), key=f"dlg_a_{rec_id}")
    with c3:
        curr_t = clean_apt_type(row.get("apartment_type", ""))
        idx_t = apt_types_list.index(curr_t) if curr_t in apt_types_list else 0
        dlg_apttype = st.selectbox("نوع الشقة", apt_types_list, index=idx_t, key=f"dlg_t_{rec_id}")

    c_n1, c_n2 = st.columns(2)
    with c_n1:
        dlg_name = st.text_input("اسم الساكن", value=str(row["resident_name"]) if pd.notna(row["resident_name"]) else "", key=f"dlg_n_{rec_id}")
    with c_n2:
        dlg_phone = st.text_input("رقم الهاتف", value=clean_str(row["phone"]), key=f"dlg_ph_{rec_id}")

    c_c1, c_c2 = st.columns(2)
    with c_c1:
        dlg_car = st.text_input("نوع ولون السيارة", value=str(row["car_info"]) if pd.notna(row["car_info"]) else "", key=f"dlg_c_{rec_id}")
    with c_c2:
        curr_s = clean_str(row.get("car_type", "مالك"))
        s_idx = status_options.index(curr_s) if curr_s in status_options else 0
        dlg_status = st.radio("الصفة:", status_options, index=s_idx, horizontal=True, key=f"dlg_s_{rec_id}")

    dlg_notes = st.text_input("ملاحظات إضافية", value=clean_str(row["notes"]), key=f"dlg_nt_{rec_id}")

    st.markdown("---")
    btn1, btn2 = st.columns(2)
    with btn1:
        if st.button("💾 حفظ التعديل", type="primary", use_container_width=True, key=f"sv_{rec_id}"):
            new_full_plate = f"{dlg_pnum} | {dlg_plet} | {dlg_preg}"
            update_full_record(rec_id, dlg_bld, dlg_apt, dlg_apttype, dlg_name, dlg_phone, dlg_pnum, dlg_plet, dlg_preg, new_full_plate, dlg_status, dlg_car, dlg_notes)
            st.success("✅ تم تعديل البيانات بنجاح!")
            st.rerun()
    with btn2:
        if st.button("🗑️ حذف السجل", use_container_width=True, key=f"dl_{rec_id}"):
            delete_record(rec_id)
            st.warning("🗑️ تم الحذف بنجاح!")
            st.rerun()


# ----------------- بطاقة عرض السيارة -----------------
def render_car_card(row):
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

    with st.container(border=True):
        top_col1, top_col2 = st.columns([3, 1])
        with top_col1:
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div class="morocco-plate-tag">
                        <span class="plate-item">{p_num}</span>
                        <span class="plate-divider"></span>
                        <span class="plate-item" style="color: #2563eb;">{p_let}</span>
                        <span class="plate-divider"></span>
                        <span class="plate-item">{p_reg}</span>
                    </div>
                    <span style="background: {badge_bg}; color: {badge_color}; padding: 4px 12px; border-radius: 20px; font-weight: 800; font-size: 13px;">
                        {c_type}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with top_col2:
            if st.button("✏️ تعديل / حذف", key=f"open_dlg_{rec_id}", use_container_width=True):
                edit_car_dialog(row)

        c1, c2 = st.columns(2)
        with c1:
            apt_disp = f"{apt} ({apt_type})" if apt_type else (apt if apt else "—")
            st.markdown(f"🏢 **العمارة:** `{bld if bld else '—'}` &nbsp;&nbsp;|&nbsp;&nbsp; 🚪 **الشقة:** `{apt_disp}`")
            st.markdown(f"👤 **الساكن:** **{row['resident_name'] if pd.notna(row['resident_name']) and row['resident_name'] else 'غير محدد'}**")
        with c2:
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


# ----------------- شريط التنقل -----------------
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "camera"

st.markdown(
    """
<div class="app-top-header">
    <div>
        <h2 style="margin:0; font-size:20px; color:white;">🚗 تدبير موقف سيارات إقامة نفيس</h2>
        <div style="font-size: 11px; opacity: 0.85; margin-top: 3px;">منظومة محلية متكاملة عبر ملف residence.xlsx</div>
    </div>
    <div style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700;">
        Excel Local Mode ⚡
    </div>
</div>
""",
    unsafe_allow_html=True,
)

c_nav1, c_nav2, c_nav3, c_nav4 = st.columns(4)
with c_nav1:
    if st.button("📷 الكاميرا", type="primary" if st.session_state.active_tab == "camera" else "secondary", use_container_width=True):
        st.session_state.active_tab = "camera"
        st.rerun()
with c_nav2:
    if st.button("🔍 استعلام", type="primary" if st.session_state.active_tab == "search" else "secondary", use_container_width=True):
        st.session_state.active_tab = "search"
        st.rerun()
with c_nav3:
    if st.button("➕ يدوي", type="primary" if st.session_state.active_tab == "add" else "secondary", use_container_width=True):
        st.session_state.active_tab = "add"
        st.rerun()
with c_nav4:
    if st.button("📊 الإدارة", type="primary" if st.session_state.active_tab == "admin" else "secondary", use_container_width=True):
        st.session_state.active_tab = "admin"
        st.rerun()

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# ==================== 1. قسم الكاميرا ====================
if st.session_state.active_tab == "camera":
    st.subheader("📷 التقاط لوحة السيارة")
    camera_file = st.camera_input("")

    if camera_file is not None:
        reader = get_ocr_reader()
        image = Image.open(io.BytesIO(camera_file.getvalue()))
        image_np = np.array(image)

        with st.spinner("⚡ جاري قراءة الترقيم..."):
            cropped_plate, was_cropped = detect_and_crop_license_plate(image_np)
            processed_np = clean_image_for_ocr(cropped_plate)
            results = reader.readtext(processed_np, allowlist="0123456789أبدهوجحيخزرWW -|[]()/", detail=1, paragraph=False)

        main_num, detected_let, region_num, full_display = parse_moroccan_plate(results)

        if main_num:
            df = get_all_records()
            exist_match = df[df["plate_number"].astype(str) == str(main_num)] if not df.empty else pd.DataFrame()

            if not exist_match.empty:
                st.warning("⚠️ هذه اللوحة مسجلة مسبقاً في النظام:")
                for _, row in exist_match.iterrows():
                    render_car_card(row)
            else:
                st.success(f"🎯 ترقيم مرصود: **{full_display}**")
                c_p1, c_p2, c_p3 = st.columns([2, 1, 1])
                with c_p1:
                    p_num = st.text_input("الأرقام *", value=main_num, key="cam_pnum")
                with c_p2:
                    p_let = st.selectbox("الحرف", letters_list, index=letters_list.index(detected_let) if detected_let in letters_list else 0, key="cam_plet")
                with c_p3:
                    p_reg = st.text_input("العمالة", value=region_num, key="cam_preg")

                car_type = st.radio("صفة الساكن:", status_options, horizontal=True, key="cam_stat")

                st.markdown("---")
                if "cam_name_val" not in st.session_state:
                    st.session_state["cam_name_val"] = ""
                if "cam_phone_val" not in st.session_state:
                    st.session_state["cam_phone_val"] = ""
                if "cam_type_val" not in st.session_state:
                    st.session_state["cam_type_val"] = ""

                col_b, col_a, col_btn = st.columns([1.5, 1.5, 1])
                with col_b:
                    e_bld = st.text_input("العمارة:", key="cam_b_in")
                with col_a:
                    e_apt = st.text_input("الشقة:", key="cam_a_in")
                with col_btn:
                    st.write("")
                    st.write("")
                    if st.button("جلب ⚡", key="cam_fetch"):
                        d = get_apartment_info(e_bld, e_apt)
                        if d:
                            st.session_state["cam_name_val"] = d["resident_name"]
                            st.session_state["cam_phone_val"] = d["phone"]
                            st.session_state["cam_type_val"] = d["apartment_type"]
                            st.rerun()

                c_t1, c_t2 = st.columns(2)
                with c_t1:
                    curr_t = st.session_state.get("cam_type_val", "")
                    idx_t = apt_types_list.index(curr_t) if curr_t in apt_types_list else 0
                    apt_type = st.selectbox("نوع الشقة:", apt_types_list, index=idx_t, key="cam_at_box")
                with c_t2:
                    name = st.text_input("اسم الساكن", value=st.session_state.get("cam_name_val", ""), key="cam_nm")

                phone = st.text_input("رقم الهاتف", value=st.session_state.get("cam_phone_val", ""), key="cam_ph")
                car_desc = st.text_input("نوع ولون السيارة", key="cam_cd")

                if st.button("💾 تسجيل السيارة", type="primary", use_container_width=True):
                    if p_num:
                        full_plate_str = f"{p_num} | {p_let} | {p_reg}"
                        add_record(e_bld, e_apt, apt_type, name, phone, p_num, p_let, p_reg, full_plate_str, car_type, car_desc, "")
                        st.success("✅ تم حفظ السيارة بنجاح!")
                        st.rerun()
        else:
            st.warning("تعذر قراءة أرقام واضحة، حاول التقاط صورة أقرب للوحة.")

# ==================== 2. قسم الاستعلام ====================
elif st.session_state.active_tab == "search":
    st.subheader("🔍 استعلام وبحث فوري")
    query = st.text_input("🔎 اكتب رقم اللوحة، اسم الساكن، العمارة، الشقة أو الهاتف:", value="")

    if query:
        df_cars = get_all_records()
        if not df_cars.empty:
            mask = (
                df_cars["plate_number"].astype(str).str.contains(query)
                | df_cars["building"].astype(str).str.contains(query)
                | df_cars["apartment"].astype(str).str.contains(query)
                | df_cars["phone"].astype(str).str.contains(query)
                | df_cars["resident_name"].astype(str).str.contains(query, case=False)
            )
            res = df_cars[mask]
            if not res.empty:
                st.markdown(f"### 🚗 نتائج موقف السيارات ({len(res)} سيارة)")
                for _, r in res.iterrows():
                    render_car_card(r)

        df_dir = load_fm6_directory()
        if not df_dir.empty:
            mask_dir = (
                df_dir["resident_name"].astype(str).str.contains(query, case=False)
                | df_dir["phone"].astype(str).str.contains(query)
                | df_dir["building"].astype(str).str.contains(query)
                | df_dir["apartment"].astype(str).str.contains(query)
            )
            res_dir = df_dir[mask_dir]
            if not res_dir.empty:
                st.markdown(f"### 🏢 نتائج دليل الشقق fm6 ({len(res_dir)} ساكن)")
                for _, rd in res_dir.iterrows():
                    st.info(f"عمارة: {rd['building']} | شقة: {rd['apartment']} | ساكن: {rd['resident_name']} | هاتف: {rd['phone']}")

# ==================== 3. قسم التسجيل اليدوي ====================
elif st.session_state.active_tab == "add":
    st.subheader("➕ تسجيل سيارة يدوياً")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        p_num = st.text_input("أرقام اللوحة *", key="man_num")
    with c2:
        p_let = st.selectbox("الحرف", letters_list, key="man_let")
    with c3:
        p_reg = st.text_input("العمالة", key="man_reg")

    car_type = st.radio("صفة الساكن:", status_options, horizontal=True, key="man_type")
    
    col_b, col_a = st.columns(2)
    with col_b:
        m_bld = st.text_input("العمارة:", key="man_bld")
    with col_a:
        m_apt = st.text_input("الشقة:", key="man_apt")

    c_t1, c_t2 = st.columns(2)
    with c_t1:
        m_apttype = st.selectbox("نوع الشقة:", apt_types_list, key="man_at")
    with c_t2:
        m_name = st.text_input("اسم الساكن", key="man_name")

    m_phone = st.text_input("رقم الهاتف", key="man_phone")
    m_desc = st.text_input("نوع ولون السيارة", key="man_desc")

    if st.button("💾 تسجيل وحفظ", type="primary", use_container_width=True):
        if p_num:
            full_plate_str = f"{p_num} | {p_let} | {p_reg}"
            add_record(m_bld, m_apt, m_apttype, m_name, m_phone, p_num, p_let, p_reg, full_plate_str, car_type, m_desc, "")
            st.success("✅ تم حفظ السيارة بنجاح!")
            st.rerun()

# ==================== 4. قسم الإدارة ====================
elif st.session_state.active_tab == "admin":
    st.subheader("🔒 إدارة المنظومة وتحميل ملف Excel")
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        admin_pass = st.text_input("🔐 أدخل القن السري:", type="password")
        if st.button("🔓 تأكيد الدخول", type="primary"):
            if admin_pass == ADMIN_PIN:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("القن السري غير صحيح.")
    else:
        df = get_all_records()
        st.success(f"📊 إجمالي السيارات المسجلة: **{len(df)} سيارة**.")

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False)
        st.download_button("📥 تحميل ملف residence.xlsx كاملاً ومحدثاً", out.getvalue(), f"residence_{datetime.now().strftime('%Y%m%d')}.xlsx", use_container_width=True)

        st.markdown("---")
        for _, r in df.iterrows():
            render_car_card(r)
