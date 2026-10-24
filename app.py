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


# ----------------- نافذة التعديل والحذف المنبثقة (Modal Dialog) -----------------
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
        if st.button("💾 حفظ وتحديث في residence.xlsx", type="primary", use_container_width=True, key=f"save_dlg_{rec_id}"):
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
            st.success("✅ تم تحديث بيانات السيارة بنجاح في ملف residence.xlsx!")
            st.rerun()

    with btn_col2:
        if st.button("🗑️ حذف هذا السجل نهائياً", use_container_width=True, key=f"del_dlg_{rec_id}"):
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


# ----------------- معالجة وفلاتر الصور المتقدمة لعزل وتوضيح الأرقام -----------------
def clean_image_for_ocr(image_np):
    if len(image_np.shape) == 3:
        gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = image_np

    # 1. تكبير الصورة لزيادة دقة الفجوات داخل 8 و 0 و 6
    h, w = gray.shape[:2]
    scaled = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

    # 2. إزالة التشويش وترددات الشاشات الرقمية
    denoised = cv2.fastNlMeansDenoising(scaled, h=10)

    # 3. توضيح التباين الموضعي بدقة (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # 4. تحويل الصورة إلى ثنائية نقية (Otsu Thresholding)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return binary


def detect_and_crop_license_plate(image_np):
    try:
        h, w = image_np.shape[:2]
        gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blur, 50, 150)

        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:25]

        plate_crop = None
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            aspect_ratio = float(cw) / ch if ch > 0 else 0

            # المعايير القياسية للوحة الترقيم المغربية
            if 2.2 <= aspect_ratio <= 6.5 and cw > (w * 0.25) and ch > (h * 0.05):
                pad_x = int(cw * 0.03)
                pad_y = int(ch * 0.06)
                y1 = max(0, y - pad_y)
                y2 = min(h, y + ch + pad_y)
                x1 = max(0, x - pad_x)
                x2 = min(w, x + cw + pad_x)

                plate_crop = image_np[y1:y2, x1:x2]
                break

        if plate_crop is not None:
            return plate_crop, True
    except Exception:
        pass

    return image_np, False


def parse_moroccan_plate(ocr_results):
    arabic_targets = {
        "أ": ["أ", "ا", "إ", "آ"],
        "ب": ["ب"],
        "د": ["د", "ذ"],
        "هـ": ["هـ", "ه", "ة"],
        "و": ["و"],
        "ج": ["ج"],
        "ح": ["ح", "خ"],
        "ي": ["ي", "ى"],
        "ز": ["ز"],
        "ر": ["ر"],
        "WW": ["WW", "ww"],
    }

    if not ocr_results:
        return "", "", "", ""

    boxes = []
    for bbox, text, prob in ocr_results:
        t = text.strip()
        if t:
            x_center = (bbox[0][0] + bbox[1][0] + bbox[2][0] + bbox[3][0]) / 4.0
            boxes.append((x_center, t))

    boxes.sort(key=lambda item: item[0], reverse=True)

    detected_letter = ""
    for x_pos, txt in boxes:
        clean_txt = re.sub(r"[\s\|\/\\\[\]\(\)\-1I!l]", "", txt)
        for main_let, aliases in arabic_targets.items():
            for alias in aliases:
                if alias in clean_txt or alias in txt:
                    detected_letter = main_let
                    break
            if detected_letter:
                break
        if detected_letter:
            break

    if not detected_letter:
        for x_pos, txt in boxes:
            clean_t = txt.strip()
            if clean_t in ["5", "0", "o", "O"]:
                detected_letter = "د"
                break

    num_boxes = []
    for x_pos, txt in boxes:
        nums = re.findall(r"\d+", txt)
        for n in nums:
            num_boxes.append((x_pos, n))

    main_num = ""
    region_num = ""

    if num_boxes:
        all_num_strs = [nb[1] for nb in num_boxes]
        main_num = clean_str(max(all_num_strs, key=len))

        remaining = [nb for nb in num_boxes if nb[1] != main_num]
        if remaining:
            remaining.sort(key=lambda item: item[0], reverse=True)
            for x_p, r_str in remaining:
                clean_r = clean_str(r_str)
                if len(clean_r) <= 2:
                    region_num = clean_r
                    break
            if not region_num:
                region_num = clean_str(remaining[0][1])

    full_display = f"{main_num} | {detected_letter if detected_letter else '-'} | {region_num if region_num else '-'}"
    return main_num, detected_letter, region_num, full_display


@st.cache_resource
def get_ocr_reader():
    return easyocr.Reader(["ar", "en"], gpu=False)


# ----------------- تصميم واجهة التطبيق CSS (توسيط العناوين) -----------------
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');
    header[data-testid="stHeader"], #MainMenu, footer, .stDeployButton { display: none !important; }
    html, body, [class*="css"], .stApp {
        font-family: 'Cairo', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        background-color: #f1f5f9;
        direction: rtl;
        text-align: right;
    }
    
    /* توسيط جميع الترويسات والعناوين */
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
        Excel Local Mode ⚡
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
    camera_file = st.camera_input("")

    if camera_file is not None:
        reader = get_ocr_reader()
        image = Image.open(io.BytesIO(camera_file.getvalue()))
        image_np = np.array(image)

        with st.spinner("⚡ جاري استشعار اللوحة وتطبيق فلاتر التوضيح بالذكاء الاصطناعي..."):
            cropped_plate, was_cropped = detect_and_crop_license_plate(image_np)
            processed_np = clean_image_for_ocr(cropped_plate)
            
            # قراءة مع تكبير وتحسين استشعار الأرقام
            results = reader.readtext(
                processed_np,
                allowlist="0123456789أبدهوجحيخزرWW -|[]()/",
                detail=1,
                paragraph=False,
                mag_ratio=1.5,
                slope_ths=0.2
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

                car_type = st.radio("صفة الساكن/السيارة:", status_options, horizontal=True, key="cam_status_radio")

                st.markdown("---")
                st.markdown("🏢 **تحديد العمارة والشقة لجلب المعطيات بدقة:**")

                if "fetched_cam_name" not in st.session_state:
                    st.session_state["fetched_cam_name"] = ""
                if "fetched_cam_phone" not in st.session_state:
                    st.session_state["fetched_cam_phone"] = ""
                if "fetched_cam_apt_type" not in st.session_state:
                    st.session_state["fetched_cam_apt_type"] = ""

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
                            st.session_state["fetched_cam_name"] = data["resident_name"]
                            st.session_state["fetched_cam_phone"] = data["phone"]
                            st.session_state["fetched_cam_apt_type"] = data["apartment_type"]
                            st.rerun()
                        else:
                            st.warning("⚠️ لم يتم العثور على شقة بهذه البيانات في fm6.xlsx.")

                c_t1, c_t2 = st.columns(2)
                with c_t1:
                    curr_t = st.session_state.get("fetched_cam_apt_type", "")
                    idx_type = apt_types_list.index(curr_t) if curr_t in apt_types_list else 0
                    apartment_type = st.selectbox(
                        "نوع الشقة (F2, F3, ...):",
                        apt_types_list,
                        index=idx_type,
                        key="cam_apttype_widget",
                    )
                with c_t2:
                    name = st.text_input("اسم الساكن", value=st.session_state.get("fetched_cam_name", ""), placeholder="الاسم الكامل", key="cam_name_widget")

                phone = st.text_input("رقم الهاتف", value=st.session_state.get("fetched_cam_phone", ""), placeholder="06XXXXXXXX", key="cam_phone_widget")
                car_desc = st.text_input("نوع ولون السيارة (اختياري)", key="cam_desc_in")

                if st.button("💾 حفظ في ملف residence.xlsx", type="primary", use_container_width=True):
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
                        st.session_state["fetched_cam_name"] = ""
                        st.session_state["fetched_cam_phone"] = ""
                        st.session_state["fetched_cam_apt_type"] = ""
                        st.success("✅ تم حفظ السيارة بنجاح في ملف residence.xlsx!")
                        st.rerun()
                    else:
                        st.error("يرجى كتابة رقم اللوحة.")
        else:
            st.warning("تعذر قراءة أرقام واضحة، حاول التقاط صورة أقرب للوحة.")

# ==================== 2. قسم الاستعلام الشامل ====================
elif st.session_state.active_tab == "search":
    st.subheader("🔍 استعلام وبحث فوري شامل")
    st.caption("البحث التلقائي يشمل: جدول سيارات الموقف (residence.xlsx) + دليل الشقق والسكان (fm6.xlsx):")

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
    st.subheader("➕ تسجيل سيارة يدوياً")

    if "fetched_manual_name" not in st.session_state:
        st.session_state["fetched_manual_name"] = ""
    if "fetched_manual_phone" not in st.session_state:
        st.session_state["fetched_manual_phone"] = ""
    if "fetched_manual_apt_type" not in st.session_state:
        st.session_state["fetched_manual_apt_type"] = ""

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
                st.session_state["fetched_manual_name"] = m_data["resident_name"]
                st.session_state["fetched_manual_phone"] = m_data["phone"]
                st.session_state["fetched_manual_apt_type"] = m_data["apartment_type"]
                st.rerun()
            else:
                st.warning("⚠️ لم يتم العثور على شقة بهذه الأرقام في ملف fm6.xlsx.")

    c_ma1, c_ma2 = st.columns(2)
    with c_ma1:
        curr_m_type = st.session_state.get("fetched_manual_apt_type", "")
        m_type_idx = apt_types_list.index(curr_m_type) if curr_m_type in apt_types_list else 0
        m_apt_type = st.selectbox(
            "نوع الشقة:",
            apt_types_list,
            index=m_type_idx,
            key="manual_apt_type_widget",
        )
    with c_ma2:
        name = st.text_input("اسم الساكن", value=st.session_state.get("fetched_manual_name", ""), placeholder="الاسم الكامل", key="manual_name_widget")

    phone = st.text_input("رقم الهاتف", value=st.session_state.get("fetched_manual_phone", ""), placeholder="06XXXXXXXX", key="manual_phone_widget")
    car_desc = st.text_input("نوع ولون السيارة", placeholder="مثال: داسيا بيضاء", key="m_car_desc")

    if st.button("💾 حفظ في ملف residence.xlsx", type="primary", use_container_width=True):
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
                st.session_state["fetched_manual_name"] = ""
                st.session_state["fetched_manual_phone"] = ""
                st.session_state["fetched_manual_apt_type"] = ""
                st.success("✅ تم حفظ السيارة في ملف residence.xlsx بنجاح!")
                st.rerun()
        else:
            st.error("أدخل رقم اللوحة على الأقل.")

# ==================== 4. قسم الإدارة وتنزيل Excel والتعديل بالنقر ====================
elif st.session_state.active_tab == "admin":
    st.subheader("🔒 إدارة المنظومة وملف residence.xlsx")

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

            # ----------------- الجدول الشامل التفاعلي (انقر على السطر للتعديل أو الحذف) -----------------
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

            # عند تحديد سطر من الجدول، تفتح نافذة التعديل والحذف المنبثقة
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
                df_up = pd.read_excel(uploaded_excel)
                for c in ["id", "building", "apartment", "apartment_type", "resident_name", "phone", "plate_number", "plate_letter", "plate_region", "full_plate", "car_type", "car_info", "created_at", "notes"]:
                    if c not in df_up.columns:
                        df_up[c] = ""
                st.session_state.cars_df = df_up
                save_df_to_residence_file()
                st.success("✅ تم تحديث وتحميل بيانات ملف residence.xlsx بنجاح!")
                st.rerun()
