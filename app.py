import io
import os
import re
import sqlite3
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

ADMIN_PIN = "1234"
DB_FILE = "residence_parking.db"

letters_list = ["", "أ", "ب", "د", "هـ", "و", "ج", "ح", "ي", "ز", "ر", "WW"]


def clean_str(val):
  if pd.isna(val) or val is None:
    return ""
  s = str(val).strip()
  if s.lower() == "nan":
    return ""
  if s.endswith(".0"):
    s = s[:-2]
  return s


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

    /* إطار الكاميرا الطبيعي والواضح */
    [data-testid="stCameraInput"] {
        width: 100% !important;
        max-width: 100% !important;
        margin: 0 auto !important;
    }
    [data-testid="stCameraInput"] video {
        width: 100% !important;
        height: auto !important;
        min-height: 320px !important;
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

# ----------------- تهيئة EasyOCR وقاعدة البيانات -----------------


@st.cache_resource
def get_ocr_reader():
  return easyocr.Reader(["ar", "en"], gpu=False)


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
            car_type TEXT DEFAULT 'مقيم',
            car_info TEXT,
            created_at TEXT,
            notes TEXT
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS apartments_directory (
            building TEXT,
            apartment TEXT,
            resident_name TEXT,
            phone TEXT,
            PRIMARY KEY (building, apartment)
        )
    """)

  cols = [
      ("full_plate", "TEXT"),
      ("car_type", "TEXT DEFAULT 'مقيم'"),
      ("created_at", "TEXT"),
      ("notes", "TEXT"),
  ]
  for col_name, col_type in cols:
    try:
      c.execute(f"ALTER TABLE residents_cars ADD COLUMN {col_name} {col_type}")
    except sqlite3.OperationalError:
      pass
  conn.commit()
  conn.close()


init_db()


def get_all_records():
  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query("SELECT * FROM residents_cars ORDER BY id DESC", conn)
  conn.close()

  for col in [
      "building",
      "apartment",
      "plate_number",
      "plate_region",
      "resident_name",
      "phone",
      "notes",
  ]:
    if col in df.columns:
      df[col] = df[col].apply(clean_str)

  return df


def get_apartment_info(bld_num, apt_num):
  b_clean = clean_str(bld_num)
  a_clean = clean_str(apt_num)
  if not a_clean:
    return None

  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()

  if b_clean:
    c.execute(
        "SELECT building, resident_name, phone FROM apartments_directory WHERE"
        " building = ? AND apartment = ?",
        (b_clean, a_clean),
    )
    res = c.fetchone()
  else:
    c.execute(
        "SELECT building, resident_name, phone FROM apartments_directory WHERE"
        " apartment = ?",
        (a_clean,),
    )
    res = c.fetchone()

  conn.close()
  if res:
    return {
        "building": clean_str(res[0]),
        "resident_name": clean_str(res[1]),
        "phone": clean_str(res[2]),
    }
  return None


def add_or_update_apartment_dir(bld, apt, name, phone):
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute(
      """
        INSERT OR REPLACE INTO apartments_directory (building, apartment, resident_name, phone)
        VALUES (?, ?, ?, ?)
    """,
      (clean_str(bld), clean_str(apt), clean_str(name), clean_str(phone)),
  )
  conn.commit()
  conn.close()


def add_record(
    building,
    apartment,
    name,
    phone,
    plate_num,
    plate_let,
    plate_reg,
    full_plate,
    car_type,
    car_info,
    notes,
):
  now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
  building = clean_str(building)
  apartment = clean_str(apartment)
  plate_num = clean_str(plate_num)
  plate_reg = clean_str(plate_reg)
  phone = clean_str(phone)

  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute(
      """
        INSERT INTO residents_cars (building, apartment, resident_name, phone, plate_number, plate_letter, plate_region, full_plate, car_type, car_info, created_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
      (
          building,
          apartment,
          name,
          phone,
          plate_num,
          plate_let,
          plate_reg,
          full_plate,
          car_type,
          car_info,
          now_str,
          notes,
      ),
  )
  conn.commit()
  conn.close()


def update_full_record(
    record_id,
    building,
    apartment,
    name,
    phone,
    plate_num,
    plate_let,
    plate_reg,
    full_plate,
    car_type,
    car_info,
    notes,
):
  building = clean_str(building)
  apartment = clean_str(apartment)
  plate_num = clean_str(plate_num)
  plate_reg = clean_str(plate_reg)
  phone = clean_str(phone)

  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute(
      """
        UPDATE residents_cars
        SET building = ?, apartment = ?, resident_name = ?, phone = ?, 
            plate_number = ?, plate_letter = ?, plate_region = ?, full_plate = ?,
            car_type = ?, car_info = ?, notes = ?
        WHERE id = ?
    """,
      (
          building,
          apartment,
          name,
          phone,
          plate_num,
          plate_let,
          plate_reg,
          full_plate,
          car_type,
          car_info,
          notes,
          int(record_id),
      ),
  )
  conn.commit()
  conn.close()


def delete_record(record_id):
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("DELETE FROM residents_cars WHERE id = ?", (int(record_id),))
  conn.commit()
  conn.close()


# ----------------- معالجة الصور الطبيعية والمثالية -----------------
def clean_image_for_ocr(image_np):
  """تحويل الصورة الطبيعي مع المحافظة التامة على نقاء وتفاصيل الخط الأصلي"""
  gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
  # تحسين بسيط للتباين دون إتلاف حواف الحروف
  enhanced = cv2.equalizeHist(gray)
  return enhanced


def parse_moroccan_plate(ocr_results):
  """تفكيك الأرقام والحروف بدقة وبدون خلط"""
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

  detected_texts = []
  for item in ocr_results:
    text = item[1].strip()
    if text:
      detected_texts.append(text)

  combined_text = " ".join(detected_texts)

  # 1. التقاط الحرف العربي
  detected_letter = ""
  for main_let, aliases in arabic_targets.items():
    for alias in aliases:
      if alias in combined_text:
        detected_letter = main_let
        break
    if detected_letter:
      break

  # تصحيح خاص لخلط الحرف د بالرقم 5
  if not detected_letter:
    for item in detected_texts:
      if item == "5" or (len(item) == 1 and item in ["5", "o", "O"]):
        detected_letter = "د"
        break

  # 2. استخراج الأرقام
  all_numbers = re.findall(r"\d+", combined_text)
  if detected_letter == "د" and "5" in all_numbers and len(all_numbers) >= 2:
    all_numbers.remove("5")

  main_num = ""
  region_num = ""

  if all_numbers:
    main_num = clean_str(max(all_numbers, key=len))
    remaining_nums = [n for n in all_numbers if n != main_num]

    if remaining_nums:
      for rn in remaining_nums:
        if len(rn) <= 2:
          region_num = clean_str(rn)
          break
      if not region_num:
        region_num = clean_str(remaining_nums[0])

  full_display = f"{main_num} | {detected_letter if detected_letter else '-'} | {region_num if region_num else '-'}"
  return main_num, detected_letter, region_num, full_display


# ----------------- بطاقة عرض السيارة -----------------
def render_car_card(row, allow_edit=True):
  p_num = clean_str(row.get("plate_number", ""))
  p_let = (
      str(row["plate_letter"])
      if pd.notna(row["plate_letter"]) and row["plate_letter"]
      else "-"
  )
  p_reg = clean_str(row.get("plate_region", ""))
  bld = clean_str(row.get("building", ""))
  apt = clean_str(row.get("apartment", ""))
  c_type = (
      row["car_type"]
      if "car_type" in row and pd.notna(row["car_type"])
      else "مقيم"
  )
  clean_phone = clean_str(row.get("phone", ""))
  rec_id = int(row["id"])

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
            <span style="background: {'#dcfce7' if c_type=='مقيم' else '#fef3c7'}; color: {'#15803d' if c_type=='مقيم' else '#b45309'}; padding: 4px 12px; border-radius: 20px; font-weight: 800; font-size: 12px;">
                {'✅ مقيم' if c_type=='مقيم' else '⏱️ زائر'}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c_i1, c_i2 = st.columns(2)
    with c_i1:
      st.markdown(
          f"🏢 **العمارة:** `{bld if bld else '—'}` &nbsp;&nbsp;|&nbsp;&nbsp; 🚪"
          f" **الشقة:** `{apt if apt else '—'}`"
      )
      st.markdown(
          "👤 **الساكن:**"
          f" {row['resident_name'] if pd.notna(row['resident_name']) and row['resident_name'] else 'غير محدد'}"
      )
    with c_i2:
      st.markdown(
          "🚘 **السيارة:**"
          f" {row['car_info'] if pd.notna(row['car_info']) and row['car_info'] else 'غير محدد'}"
      )
      st.markdown(f"📞 **الهاتف:** `{clean_phone if clean_phone else 'لا يوجد'}`")

    if clean_phone and clean_phone.lower() != "nan":
      b1, b2 = st.columns(2)
      with b1:
        st.link_button(
            "📞 اتصال هاتفي", f"tel:{clean_phone}", use_container_width=True
        )
      with b2:
        wa_phone = (
            clean_phone[1:] if clean_phone.startswith("0") else clean_phone
        )
        p_full = f"{p_num} | {p_let} | {p_reg}"
        wa_msg = f"السلام عليكم، بخصوص سيارتكم رقم ({p_full}) المتوقفة في موقف إقامة نفيس، يرجى التكرم بتحريكها وشكراً."
        wa_link = (
            f"https://wa.me/212{wa_phone}?text={wa_msg.replace(' ', '%20')}"
        )
        st.link_button("💬 تنبيه واتساب", wa_link, use_container_width=True)

    if allow_edit:
      with st.expander("✏️ تعديل أو إكمال معطيات هذه السيارة"):
        col_e1, col_e2 = st.columns(2)
        with col_e1:
          e_bld = st.text_input(
              "العمارة",
              value=clean_str(row["building"]),
              key=f"card_bld_{rec_id}",
          )
          e_apt = st.text_input(
              "الشقة",
              value=clean_str(row["apartment"]),
              key=f"card_apt_{rec_id}",
          )

        with col_e2:
          e_name = st.text_input(
              "اسم الساكن",
              value=(
                  str(row["resident_name"])
                  if pd.notna(row["resident_name"])
                  else ""
              ),
              key=f"card_name_{rec_id}",
          )
          e_phone = st.text_input(
              "رقم الهاتف",
              value=clean_str(row["phone"]),
              key=f"card_phone_{rec_id}",
          )

        col_e3, col_e4 = st.columns(2)
        with col_e3:
          e_car = st.text_input(
              "نوع ولون السيارة",
              value=str(row["car_info"]) if pd.notna(row["car_info"]) else "",
              key=f"card_car_{rec_id}",
          )
        with col_e4:
          curr_type = (
              str(row["car_type"])
              if "car_type" in row and pd.notna(row["car_type"])
              else "مقيم"
          )
          type_idx = 0 if curr_type == "مقيم" else 1
          e_type = st.radio(
              "الصفة",
              ["مقيم", "زائر مؤقت"],
              index=type_idx,
              horizontal=True,
              key=f"card_type_{rec_id}",
          )

        e_notes = st.text_input(
            "ملاحظات",
            value=clean_str(row["notes"]),
            key=f"card_notes_{rec_id}",
        )

        if st.button(
            "💾 حفظ التعديلات", key=f"btn_save_card_{rec_id}", type="primary"
        ):
          p_full_str = f"{clean_str(row['plate_number'])} | {row['plate_letter']} | {clean_str(row['plate_region'])}"
          update_full_record(
              rec_id,
              e_bld,
              e_apt,
              e_name,
              e_phone,
              clean_str(row["plate_number"]),
              str(row["plate_letter"]),
              clean_str(row["plate_region"]),
              p_full_str,
              e_type,
              e_car,
              e_notes,
          )
          st.success("✅ تم حفظ التعديلات بنجاح!")
          st.rerun()


# ----------------- شريط الملاحة والتنقل -----------------
if "active_tab" not in st.session_state:
  st.session_state.active_tab = "camera"

st.markdown(
    """
<div class="app-top-header">
    <div>
        <h2>🚗 تدبير موقف سيارات إقامة نفيس</h2>
        <div style="font-size: 11px; opacity: 0.8; margin-top: 2px;">نظام التسيير والتحقق الفوري</div>
    </div>
    <div class="status-badge">
        <span style="height: 8px; width: 8px; background-color: #34d399; border-radius: 50%; display: inline-block;"></span>
        النظام متصل
    </div>
</div>
""",
    unsafe_allow_html=True,
)

nav_c1, nav_c2, nav_c3, nav_c4 = st.columns(4)

with nav_c1:
  btn_type = (
      "primary" if st.session_state.active_tab == "camera" else "secondary"
  )
  if st.button("📷 الكاميرا", type=btn_type, use_container_width=True):
    st.session_state.active_tab = "camera"
    st.rerun()

with nav_c2:
  btn_type = (
      "primary" if st.session_state.active_tab == "search" else "secondary"
  )
  if st.button("🔍 استعلام", type=btn_type, use_container_width=True):
    st.session_state.active_tab = "search"
    st.rerun()

with nav_c3:
  btn_type = "primary" if st.session_state.active_tab == "add" else "secondary"
  if st.button("➕ يدوي", type=btn_type, use_container_width=True):
    st.session_state.active_tab = "add"
    st.rerun()

with nav_c4:
  btn_type = (
      "primary" if st.session_state.active_tab == "admin" else "secondary"
  )
  if st.button("📊 الإدارة", type=btn_type, use_container_width=True):
    st.session_state.active_tab = "admin"
    st.rerun()

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# ==================== 1. قسم الكاميرا فائق الدقة ====================
if st.session_state.active_tab == "camera":
  st.subheader("📷 التقاط لوحة السيارة")
  st.caption("وجه الكاميرا بوضوح بحيث تملأ اللوحة معظم الشاشة:")

  camera_file = st.camera_input("")

  if camera_file is not None:
    reader = get_ocr_reader()
    image = Image.open(io.BytesIO(camera_file.getvalue()))
    image_np = np.array(image)

    with st.spinner("⚡ جاري قراءة الترقيم بأعلى دقة..."):
      processed_np = clean_image_for_ocr(image_np)
      # قراءة مباشرة بصورة نظيفة وغير مشوهة
      results = reader.readtext(
          processed_np,
          allowlist="0123456789أبدهوجحيخزرWW -|",
          detail=1,
          paragraph=False,
      )

    main_num, detected_let, region_num, full_display = parse_moroccan_plate(
        results
    )

    if main_num:
      df = get_all_records()
      exist_match = (
          df[df["plate_number"].astype(str) == str(main_num)]
          if not df.empty
          else pd.DataFrame()
      )

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
          idx = (
              letters_list.index(detected_let)
              if detected_let in letters_list
              else 0
          )
          p_let = st.selectbox(
              "الحرف", letters_list, index=idx, key="cam_plet"
          )
        with c_p3:
          p_reg = st.text_input(
              "العمالة", value=region_num, placeholder="26", key="cam_preg"
          )

        car_type = st.radio(
            "الصفة:", ["مقيم", "زائر مؤقت"], horizontal=True, key="cam_type"
        )

        st.markdown("---")
        st.markdown("🏢 **تحديد العمارة والشقة لجلب المعطيات بدقة:**")

        col_bld_in, col_apt_in, col_fetch_btn = st.columns([1.5, 1.5, 1])
        with col_bld_in:
          entered_bld = st.text_input(
              "العمارة:", placeholder="مثال: 5", key="cam_bld_input"
          )
        with col_apt_in:
          entered_apt = st.text_input(
              "الشقة:", placeholder="مثال: 12", key="cam_apt_input"
          )
        with col_fetch_btn:
          st.write("")
          st.write("")
          fetch_btn = st.button(
              "جلب ⚡", use_container_width=True, type="secondary"
          )

        apt_data = (
            get_apartment_info(entered_bld, entered_apt)
            if (entered_bld or entered_apt)
            else None
        )
        if apt_data:
          st.success(
              f"✅ تم التعرف على الساكن: **{apt_data['resident_name']}**"
              f" (عمارة {apt_data['building']} - شقة {entered_apt})"
          )

        c_name, c_phone = st.columns(2)
        with c_name:
          name = st.text_input(
              "اسم الساكن",
              value=apt_data["resident_name"] if apt_data else "",
              placeholder="الاسم الكامل",
          )
        with c_phone:
          phone = st.text_input(
              "رقم الهاتف",
              value=apt_data["phone"] if apt_data else "",
              placeholder="06XXXXXXXX",
          )

        car_desc = st.text_input("نوع ولون السيارة (اختياري)")

        if st.button(
            "💾 حفظ الترقيم والمعطيات في المنظومة",
            type="primary",
            use_container_width=True,
        ):
          if p_num:
            p_num = clean_str(p_num)
            p_reg = clean_str(p_reg)
            full_plate_str = f"{p_num} | {p_let} | {p_reg}"
            add_record(
                entered_bld,
                entered_apt,
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
            st.success("تم الحفظ بنجاح!")
            st.rerun()
          else:
            st.error("يرجى كتابة رقم اللوحة.")
    else:
      st.warning(
          "تعذر قراءة أرقام واضحة، حاول التقاط صورة أقرب للوحة السيارة."
      )

# ==================== 2. قسم الاستعلام ====================
elif st.session_state.active_tab == "search":
  st.subheader("🔍 استعلام وبحث فوري")

  with st.form("search_form"):
    col_in, col_bt = st.columns([3, 1])
    with col_in:
      query = st.text_input(
          "🔎 أدخل رقم اللوحة أو الساكن:",
          value="",
          placeholder="",
          label_visibility="collapsed",
      )
    with col_bt:
      search_submitted = st.form_submit_button(
          "🔍 ابحث الآن", type="primary", use_container_width=True
      )

  if query:
    df = get_all_records()
    if not df.empty:
      mask = (
          df["plate_number"].astype(str).str.contains(query)
          | df["building"].astype(str).str.contains(query)
          | df["apartment"].astype(str).str.contains(query)
          | df["resident_name"].astype(str).str.contains(query, case=False)
      )
      res = df[mask]
      if not res.empty:
        st.write(f"تم العثور على ({len(res)}) سيارة:")
        for _, r in res.iterrows():
          render_car_card(r, allow_edit=True)
      else:
        st.info("لا توجد سيارة مطابقة لبيانات البحث.")
    else:
      st.info("لا توجد سيارات مسجلة في النظام بعد.")

# ==================== 3. قسم التسجيل اليدوي ====================
elif st.session_state.active_tab == "add":
  st.subheader("➕ تسجيل سيارة يدوياً")

  c1, c2, c3 = st.columns([2, 1, 1])
  with c1:
    p_num = st.text_input("أرقام اللوحة *", placeholder="78954")
  with c2:
    p_let = st.selectbox("حرف اللوحة", letters_list)
  with c3:
    p_reg = st.text_input("العمالة", placeholder="26")

  car_type = st.radio("الصفة:", ["مقيم", "زائر مؤقت"], horizontal=True)

  st.markdown("🏢 **تحديد العمارة والشقة:**")
  col_mbld, col_mapt, col_mbtn = st.columns([1.5, 1.5, 1])
  with col_mbld:
    m_bld = st.text_input("العمارة:", placeholder="مثال: 5", key="m_bld_in")
  with col_mapt:
    m_apt = st.text_input("الشقة:", placeholder="مثال: 12", key="m_apt_in")
  with col_mbtn:
    st.write("")
    st.write("")
    btn_m_fetch = st.button("جلب ⚡", key="m_fetch", use_container_width=True)

  m_data = (
      get_apartment_info(m_bld, m_apt) if (m_bld or m_apt) else None
  )

  c_a, c_b = st.columns(2)
  with c_a:
    name = st.text_input(
        "اسم الساكن",
        value=m_data["resident_name"] if m_data else "",
        key="m_name_input",
    )
  with c_b:
    phone = st.text_input(
        "رقم الهاتف",
        value=m_data["phone"] if m_data else "",
        key="m_phone_input",
    )

  car_desc = st.text_input("نوع ولون السيارة")

  if st.button("💾 حفظ في المنظومة", type="primary", use_container_width=True):
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
        st.success("تم الحفظ بنجاح!")
        st.rerun()
    else:
      st.error("أدخل رقم اللوحة على الأقل.")

# ==================== 4. قسم الإدارة وتحميل دليل الشقق ====================
elif st.session_state.active_tab == "admin":
  st.subheader("🔒 إدارة المنظومة ودليل الشقق")

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
      pin_submit = st.form_submit_button(
          "🔓 تأكيد الدخول", type="primary", use_container_width=True
      )
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
    st.subheader("🏢 رفع وتحديث دليل الشقق والسكان (Excel)")
    st.caption("ارفع ملف Excel الخاص بالقاطنين والشقق:")

    uploaded_dir = st.file_uploader(
        "اختر ملف Excel الخاص بسكان الإقامة", type=["xlsx", "xls"]
    )
    if uploaded_dir is not None:
      try:
        dir_df = pd.read_excel(uploaded_dir)

        first_row_vals = [
            str(v).lower().strip() for v in dir_df.iloc[0].values
        ]
        if any(
            x in first_row_vals
            for x in ["apartment", "شقة", "immeuble", "building"]
        ):
          dir_df.columns = dir_df.iloc[0]
          dir_df = dir_df[1:].reset_index(drop=True)

        col_map = {}
        for col in dir_df.columns:
          c_lower = str(col).lower().strip()
          if any(k in c_lower for k in ["apt", "apartment", "شقة", "شقه"]):
            col_map[col] = "apartment"
          elif any(
              k in c_lower for k in ["bld", "building", "عمارة", "عماره", "imm"]
          ):
            col_map[col] = "building"
          elif any(
              k in c_lower
              for k in ["name", "resident", "nom", "اسم", "قاطن", "ساكن"]
          ):
            col_map[col] = "resident_name"
          elif any(
              k in c_lower for k in ["phone", "tel", "هاتف", "جوال", "نقال"]
          ):
            col_map[col] = "phone"

        dir_df = dir_df.rename(columns=col_map)

        if "apartment" in dir_df.columns and "building" in dir_df.columns:
          added_count = 0
          for _, row in dir_df.iterrows():
            apt = clean_str(row.get("apartment", ""))
            bld = clean_str(row.get("building", ""))
            name = clean_str(row.get("resident_name", ""))
            phone = clean_str(row.get("phone", ""))
            if apt and bld:
              add_or_update_apartment_dir(bld, apt, name, phone)
              added_count += 1
          st.success(
              f"🎉 تم تسجيل وتحديث ({added_count}) شقة وسكانها موزعة على"
              " العمارات بنجاح!"
          )
          st.rerun()
        else:
          st.error("الملف يجب أن يحتوي على عمودين: رقم الشقة ورقم العمارة.")
      except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة الملف: {e}")

    conn = sqlite3.connect(DB_FILE)
    apt_count = conn.cursor().execute("SELECT COUNT(*) FROM apartments_directory").fetchone()[0]
    conn.close()
    st.info(f"إجمالي الشقق المسجلة في دليل الإقامة حالياً: **{apt_count} شقة**")

    if not df.empty:
      st.markdown("---")
      m1, m2, m3 = st.columns(3)
      m1.metric("إجمالي السيارات المسجلة", len(df))
      m2.metric(
          "مكتملة البيانات",
          df["apartment"].replace("", np.nan).dropna().count(),
      )
      missing_count = df["apartment"].replace("", np.nan).isna().sum()
      m3.metric("بحاجة لإكمال الشقة ⚠️", missing_count)

      # ----------------- قسم التعديل عبر البحث المباشر -----------------
      st.markdown("---")
      st.subheader("✏️ البحث عن سيارة لتعديل أو استكمال معطياتها")
      st.caption("اكتب رقم اللوحة، اسم الساكن، أو رقم العمارة:")

      edit_query = st.text_input(
          "🔎 بحث عن السجل:",
          value="",
          placeholder="",
          label_visibility="collapsed",
          key="edit_search_field",
      )

      if edit_query:
        mask_edit = (
            df["plate_number"].astype(str).str.contains(edit_query)
            | df["building"].astype(str).str.contains(edit_query)
            | df["apartment"].astype(str).str.contains(edit_query)
            | df["resident_name"].astype(str).str.contains(edit_query, case=False)
        )
        res_edit = df[mask_edit]

        if not res_edit.empty:
          st.write(f"تم العثور على ({len(res_edit)}) نتيجة:")
          for _, row_sel in res_edit.iterrows():
            selected_car_id = int(row_sel["id"])
            with st.expander(
                f"📝 تعديل: [{row_sel['full_plate']}] - العمارة:"
                f" {row_sel['building']} | الساكن: {row_sel['resident_name']}",
                expanded=True,
            ):
              c_p1, c_p2, c_p3 = st.columns([2, 1, 1])
              with c_p1:
                edit_p_num = st.text_input(
                    "أرقام اللوحة",
                    value=clean_str(row_sel["plate_number"]),
                    key=f"adm_pnum_{selected_car_id}",
                )
              with c_p2:
                let_val = (
                    row_sel["plate_letter"]
                    if pd.notna(row_sel["plate_letter"])
                    and row_sel["plate_letter"] in letters_list
                    else ""
                )
                edit_p_let = st.selectbox(
                    "الحرف",
                    letters_list,
                    index=letters_list.index(let_val) if let_val else 0,
                    key=f"adm_plet_{selected_car_id}",
                )
              with c_p3:
                edit_p_reg = st.text_input(
                    "العمالة",
                    value=clean_str(row_sel["plate_region"]),
                    key=f"adm_preg_{selected_car_id}",
                )

              curr_type = (
                  str(row_sel["car_type"])
                  if "car_type" in row_sel and pd.notna(row_sel["car_type"])
                  else "مقيم"
              )
              type_idx = 0 if curr_type == "مقيم" else 1
              edit_car_type = st.radio(
                  "صفة السيارة:",
                  ["مقيم", "زائر مؤقت"],
                  index=type_idx,
                  horizontal=True,
                  key=f"adm_type_{selected_car_id}",
              )

              c1, c2 = st.columns(2)
              with c1:
                new_bld = st.text_input(
                    "رقم العمارة",
                    value=clean_str(row_sel["building"]),
                    key=f"adm_bld_{selected_car_id}",
                )
                new_apt = st.text_input(
                    "رقم الشقة",
                    value=clean_str(row_sel["apartment"]),
                    key=f"adm_apt_{selected_car_id}",
                )
              with c2:
                new_name = st.text_input(
                    "اسم الساكن",
                    value=(
                        str(row_sel["resident_name"])
                        if pd.notna(row_sel["resident_name"])
                        else ""
                    ),
                    key=f"adm_name_{selected_car_id}",
                )
                new_phone = st.text_input(
                    "رقم الهاتف",
                    value=clean_str(row_sel["phone"]),
                    key=f"adm_phone_{selected_car_id}",
                )

              c3, c4 = st.columns(2)
              with c3:
                new_car_info = st.text_input(
                    "نوع ولون السيارة",
                    value=(
                        str(row_sel["car_info"])
                        if pd.notna(row_sel["car_info"])
                        else ""
                    ),
                    key=f"adm_car_{selected_car_id}",
                )
              with c4:
                new_notes = st.text_input(
                    "ملاحظات",
                    value=clean_str(row_sel["notes"]),
                    key=f"adm_notes_{selected_car_id}",
                )

              if st.button(
                  "💾 حفظ وتحديث المعطيات فوراً",
                  key=f"btn_save_adm_{selected_car_id}",
                  type="primary",
              ):
                e_p_num = clean_str(edit_p_num)
                e_p_reg = clean_str(edit_p_reg)
                new_full_plate = f"{e_p_num} | {edit_p_let} | {e_p_reg}"
                update_full_record(
                    selected_car_id,
                    new_bld,
                    new_apt,
                    new_name,
                    new_phone,
                    e_p_num,
                    edit_p_let,
                    e_p_reg,
                    new_full_plate,
                    edit_car_type,
                    new_car_info,
                    new_notes,
                )
                st.success("✅ تم تحديث بيانات السيارة بنجاح في قاعدة البيانات!")
                st.rerun()
        else:
          st.info("لم يتم العثور على أي سيارة مطابقة للبحث للتعديل عليها.")

      st.markdown("---")
      st.subheader("📋 الجدول الشامل للسيارات")
      st.dataframe(df, use_container_width=True)

      towrite = io.BytesIO()
      with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="السيارات")
      towrite.seek(0)

      st.download_button(
          label="📥 تنزيل نسخة احتياطية Excel (.xlsx)",
          data=towrite,
          file_name=f"residence_cars_{datetime.now().strftime('%Y%m%d')}.xlsx",
          mime=(
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          ),
          use_container_width=True,
      )

      with st.expander("🗑️ حذف سيارة من النظام"):
        del_id = st.number_input(
            "أدخل معرف السجل (ID):", min_value=1, step=1
        )
        if st.button("تأكيد الحذف نهائياً", use_container_width=True):
          delete_record(del_id)
          st.rerun()
    else:
      st.info("لا توجد سيارات مسجلة بعد.")

    st.markdown("---")
    with st.expander("📤 استعادة أو رفع بيانات سيارات من ملف Excel"):
      uploaded_excel = st.file_uploader(
          "اختر ملف Excel لاسترجاع السيارات المسجلة", type=["xlsx"]
      )
      if uploaded_excel is not None:
        df_up = pd.read_excel(uploaded_excel)
        for _, row in df_up.iterrows():
          p_num = clean_str(row.get("plate_number", ""))
          if p_num and (
              df.empty or df[df["plate_number"].astype(str) == p_num].empty
          ):
            add_record(
                clean_str(row.get("building", "")),
                clean_str(row.get("apartment", "")),
                clean_str(row.get("resident_name", "")),
                clean_str(row.get("phone", "")),
                p_num,
                str(row.get("plate_letter", "")),
                clean_str(row.get("plate_region", "")),
                clean_str(row.get("full_plate", "")),
                str(row.get("car_type", "مقيم")),
                str(row.get("car_info", "")),
                clean_str(row.get("notes", "")),
            )
        st.success("✅ تمت استعادة كافة السيارات وتطهير الأرقام بنجاح!")
        st.rerun()
