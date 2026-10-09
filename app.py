import io
import os
import re
import sqlite3
from datetime import datetime
import easyocr
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st

st.set_page_config(
    page_title="تدبير سيارات الإقامة",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----------------- تنسيق واجهة الهاتف والكاميرا -----------------
st.markdown(
    """
<style>
    [data-testid="stCameraInput"] {
        width: 100% !important;
        max-width: 100% !important;
    }
    [data-testid="stCameraInput"] video {
        width: 100% !important;
        height: auto !important;
        border-radius: 14px !important;
        border: 2px solid #0284c7 !important;
    }
    div.stButton > button {
        border-radius: 10px !important;
        font-weight: 700 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

DB_FILE = "residence_parking.db"
EXCEL_FILE = "residence_archive.xlsx"

# ----------------- تهيئة EasyOCR وقاعدة البيانات وملف الإكسيل -----------------


@st.cache_resource
def get_ocr_reader():
  return easyocr.Reader(["ar", "en"], gpu=False)


def init_storage():
  # 1. تهيئة SQLite
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
            created_at TEXT,
            notes TEXT
        )
    """)
  try:
    c.execute("ALTER TABLE residents_cars ADD COLUMN full_plate TEXT")
  except sqlite3.OperationalError:
    pass
  try:
    c.execute("ALTER TABLE residents_cars ADD COLUMN created_at TEXT")
  except sqlite3.OperationalError:
    pass
  conn.commit()
  conn.close()

  # 2. تهيئة ملف Excel الأرشيفي إن لم يكن موجوداً
  if not os.path.exists(EXCEL_FILE):
    df_init = pd.DataFrame(columns=[
        "id",
        "building",
        "apartment",
        "resident_name",
        "phone",
        "plate_number",
        "plate_letter",
        "plate_region",
        "full_plate",
        "car_info",
        "created_at",
        "notes",
    ])
    df_init.to_excel(EXCEL_FILE, index=False)


init_storage()


def get_all_records():
  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query("SELECT * FROM residents_cars ORDER BY id DESC", conn)
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
    full_plate,
    car_info,
    notes,
):
  now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

  # 1. الحفظ في قاعدة البيانات
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute(
      """
        INSERT INTO residents_cars (building, apartment, resident_name, phone, plate_number, plate_letter, plate_region, full_plate, car_info, created_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
          car_info,
          now_str,
          notes,
      ),
  )
  rec_id = c.lastrowid
  conn.commit()
  conn.close()

  # 2. الحفظ التلقائي الفوري في ملف Excel للأرشفة الدائمة
  new_row = {
      "id": rec_id,
      "building": building,
      "apartment": apartment,
      "resident_name": name,
      "phone": phone,
      "plate_number": plate_num,
      "plate_letter": plate_let,
      "plate_region": plate_reg,
      "full_plate": full_plate,
      "car_info": car_info,
      "created_at": now_str,
      "notes": notes,
  }

  if os.path.exists(EXCEL_FILE):
    df_excel = pd.read_excel(EXCEL_FILE)
    df_excel = pd.concat([df_excel, pd.DataFrame([new_row])], ignore_index=True)
  else:
    df_excel = pd.DataFrame([new_row])

  df_excel.to_excel(EXCEL_FILE, index=False)


def delete_record(record_id):
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("DELETE FROM residents_cars WHERE id = ?", (record_id,))
  conn.commit()
  conn.close()

  if os.path.exists(EXCEL_FILE):
    df_excel = pd.read_excel(EXCEL_FILE)
    df_excel = df_excel[df_excel["id"] != record_id]
    df_excel.to_excel(EXCEL_FILE, index=False)


def parse_moroccan_plate(text_list):
  arabic_letters = [
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
  ]
  combined = " ".join(text_list)
  nums = re.findall(r"\d+", combined)
  main_num, region, detected_letter = "", "", ""

  if nums:
    main_num = max(nums, key=len)
    remaining_nums = [n for n in nums if n != main_num]
    if remaining_nums:
      region = remaining_nums[0]

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


# ----------------- شريط أزرار التنقل -----------------
if "active_tab" not in st.session_state:
  st.session_state.active_tab = "camera"

st.title("🚗 جرد وتدبير سيارات الإقامة")

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
  if st.button("🔍 استعلام", type=btn_type, use_container_width=True):
    st.session_state.active_tab = "search"
    st.rerun()

with col3:
  btn_type = "primary" if st.session_state.active_tab == "add" else "secondary"
  if st.button("➕ يدوي", type=btn_type, use_container_width=True):
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
    "",
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

# ==================== 1. قسم الكاميرا والجرد ====================
if st.session_state.active_tab == "camera":
  st.subheader("📷 التقاط لوحة السيارة")
  camera_file = st.camera_input("التقاط صورة اللوحة")

  if camera_file is not None:
    reader = get_ocr_reader()
    image = Image.open(io.BytesIO(camera_file.getvalue()))
    image_np = np.array(image)

    with st.spinner("جاري قراءة اللوحة بدقة..."):
      results = reader.readtext(image_np)
      detected_texts = [res[1] for res in results]

    main_num, detected_let, region_num, full_display = parse_moroccan_plate(
        detected_texts
    )

    if main_num:
      st.write(f"### 🎯 الترقيم المقروء: **`{full_display}`**")

      df = get_all_records()
      is_duplicate = False
      if not df.empty:
        exist_match = df[df["plate_number"].astype(str) == str(main_num)]
        if not exist_match.empty:
          is_duplicate = True

      if is_duplicate:
        st.error(
            "⛔ تنبيه: هذه السيارة مسجلة مسبقاً في النظام! لن يتم تسجيلها مرتين."
        )
        st.info("بيانات اللوحة المسجلة مسبقاً:")
        st.dataframe(
            exist_match[[
                "id",
                "building",
                "apartment",
                "plate_number",
                "plate_letter",
                "plate_region",
                "resident_name",
            ]],
            use_container_width=True,
        )
      else:
        st.success("✅ ترقيم جديد، يمكنك تسجيله فوراً في الجدول والإكسيل:")
        with st.form("quick_census_form"):
          col_p1, col_p2, col_p3 = st.columns([2, 1, 1])
          with col_p1:
            p_num = st.text_input("الأرقام *", value=main_num)
          with col_p2:
            idx = (
                letters_list.index(detected_let)
                if detected_let in letters_list
                else 0
            )
            p_let = st.selectbox("الحرف", letters_list, index=idx)
          with col_p3:
            p_reg = st.text_input("العمالة", value=region_num, placeholder="26")

          st.caption("الخانات التالية اختيارية:")
          c_bld, c_apt = st.columns(2)
          with c_bld:
            bld = st.text_input("رقم العمارة", placeholder="مثال: 14")
          with c_apt:
            apt = st.text_input("رقم الشقة", placeholder="مثال: 3")

          c_name, c_phone = st.columns(2)
          with c_name:
            name = st.text_input("اسم الساكن")
          with c_phone:
            phone = st.text_input("الهاتف")

          car_desc = st.text_input(
              "نوع ولون السيارة", placeholder="مثال: Dacia رمادية"
          )

          save_now = st.form_submit_button(
              "💾 حفظ وأرشفة فورية في Excel", use_container_width=True
          )

          if save_now:
            if p_num:
              full_plate_str = f"{p_num} | {p_let} | {p_reg}"
              add_record(
                  bld,
                  apt,
                  name,
                  phone,
                  p_num,
                  p_let,
                  p_reg,
                  full_plate_str,
                  car_desc,
                  "",
              )
              st.success(
                  f"🎉 تم تسجيل الترقيم [{full_plate_str}] وأرشفته بنجاح!"
              )
              st.rerun()
            else:
              st.error("يرجى التأكد من كتابة أرقام اللوحة.")
    else:
      st.warning("تعذر استخراج رقم واضح. يمكنك كتابة اللوحة يدوياً.")

# ==================== 2. قسم الاستعلام ====================
elif st.session_state.active_tab == "search":
  st.subheader("🔍 استعلام سريع")
  query = st.text_input("ابحث برقم اللوحة، العمارة، أو الشقة:")
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
        st.write(f"النتائج ({len(res)}):")
        st.dataframe(
            res[[
                "id",
                "building",
                "apartment",
                "plate_number",
                "plate_letter",
                "plate_region",
                "resident_name",
                "phone",
                "car_info",
            ]],
            use_container_width=True,
        )
      else:
        st.warning("لا توجد نتائج مطابقة.")

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

    c_b, c_a = st.columns(2)
    with c_b:
      bld = st.text_input("العمارة (اختياري)")
    with c_a:
      apt = st.text_input("الشقة (اختياري)")

    name = st.text_input("اسم الساكن (اختياري)")
    phone = st.text_input("رقم الهاتف (اختياري)")
    car_desc = st.text_input("نوع ولون السيارة (اختياري)")

    if st.form_submit_button("💾 حفظ في الأرشيف", use_container_width=True):
      if p_num:
        df = get_all_records()
        if (
            not df.empty
            and not df[df["plate_number"].astype(str) == str(p_num)].empty
        ):
          st.error(f"⛔ الترقيم ({p_num}) مسجل مسبقاً في النظام!")
        else:
          full_plate_str = f"{p_num} | {p_let} | {p_reg}"
          add_record(
              bld,
              apt,
              name,
              phone,
              p_num,
              p_let,
              p_reg,
              full_plate_str,
              car_desc,
              "",
          )
          st.success("تم الحفظ والأرشفة بنجاح!")
          st.rerun()
      else:
        st.error("أدخل أرقام اللوحة على الأقل.")

# ==================== 4. قسم الإدارة والتحميل ورفع الأرشيف ====================
elif st.session_state.active_tab == "admin":
  st.subheader("📊 لوحة الإدارة وملف Excel المؤرشف")
  df = get_all_records()

  if not df.empty:
    c1, c2 = st.columns(2)
    c1.metric("إجمالي الترقيمات المحفوظة", len(df))
    c2.metric(
        "شقق مكتملة", df["apartment"].replace("", np.nan).dropna().count()
    )

    st.dataframe(df, use_container_width=True)

    # قراءة وتنزيل ملف Excel الأرشيفي المحفوظ دائماً
    if os.path.exists(EXCEL_FILE):
      with open(EXCEL_FILE, "rb") as f:
        excel_bytes = f.read()

      st.download_button(
          label="📥 تحميل الأرشيف الكامل بصيغة Excel (.xlsx)",
          data=excel_bytes,
          file_name="residence_archive.xlsx",
          mime=(
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          ),
          use_container_width=True,
      )

    with st.expander("🗑️ حذف سطر من الأرشيف"):
      del_id = st.number_input(
          "أدخل معرف السجل (ID) لحذفه:", min_value=1, step=1
      )
      if st.button("تأكيد الحذف", use_container_width=True):
        delete_record(del_id)
        st.rerun()
  else:
    st.info("لا توجد بيانات مسجلة في الأرشيف حالياً.")

  # ميزة استرجاع البيانات المسبقة في حال إعادة تشغيل السيرفر
  st.markdown("---")
  with st.expander("📤 استيراد بيانات سابقة من ملف Excel (في حال التحديث)"):
    uploaded_excel = st.file_uploader(
        "ارفع ملف residence_archive.xlsx لاستعادة البيانات دفعة واحدة",
        type=["xlsx"],
    )
    if uploaded_excel is not None:
      df_upload = pd.read_excel(uploaded_excel)
      for _, row in df_upload.iterrows():
        p_num = str(row.get("plate_number", ""))
        if p_num and (df.empty or df[df["plate_number"].astype(str) == p_num].empty):
          add_record(
              str(row.get("building", "")),
              str(row.get("apartment", "")),
              str(row.get("resident_name", "")),
              str(row.get("phone", "")),
              p_num,
              str(row.get("plate_letter", "")),
              str(row.get("plate_region", "")),
              str(row.get("full_plate", "")),
              str(row.get("car_info", "")),
              str(row.get("notes", "")),
          )
      st.success("✅ تمت استعادة كافة البيانات ودمجها بنجاح!")
      st.rerun()
