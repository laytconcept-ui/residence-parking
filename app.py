import io
import re
import sqlite3
from datetime import datetime
import easyocr
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st

st.set_page_config(
    page_title="منظومة تدبير سيارات الإقامة",
    page_icon="🚗",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# رمز الحماية الخاص بقسم الإدارة
ADMIN_PIN = "1234"
DB_FILE = "residence_parking.db"

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
  columns_to_check = [
      ("full_plate", "TEXT"),
      ("car_type", "TEXT DEFAULT 'مقيم'"),
      ("created_at", "TEXT"),
      ("notes", "TEXT"),
  ]
  for col_name, col_type in columns_to_check:
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
    car_type,
    car_info,
    notes,
):
  now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
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


def update_record_details(record_id, building, apartment, name, phone, notes):
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute(
      """
        UPDATE residents_cars
        SET building = ?, apartment = ?, resident_name = ?, phone = ?, notes = ?
        WHERE id = ?
    """,
      (building, apartment, name, phone, notes, record_id),
  )
  conn.commit()
  conn.close()


def delete_record(record_id):
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("DELETE FROM residents_cars WHERE id = ?", (record_id,))
  conn.commit()
  conn.close()


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
  main_num = ""
  region = ""
  detected_letter = ""

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


# ----------------- دالة عرض بطاقة السيارة -----------------
def render_car_card(row):
  with st.container(border=True):
    p_full = (
        row["full_plate"]
        if pd.notna(row["full_plate"]) and row["full_plate"]
        else f"{row['plate_number']} | {row['plate_letter']} | {row['plate_region']}"
    )
    bld = (
        row["building"]
        if pd.notna(row["building"]) and row["building"]
        else "غير محددة"
    )
    apt = (
        row["apartment"]
        if pd.notna(row["apartment"]) and row["apartment"]
        else "غير محددة"
    )
    c_type = (
        row["car_type"]
        if "car_type" in row and pd.notna(row["car_type"])
        else "مقيم"
    )

    badge = "🟢" if c_type == "مقيم" else "🟡"
    st.markdown(f"### {badge} لوحة: `{p_full}` ({c_type})")
    st.write(f"🏢 **العمارة:** {bld}  |  🚪 **الشقة:** {apt}")
    st.write(
        f"👤 **الساكن:** {row['resident_name'] if pd.notna(row['resident_name']) and row['resident_name'] else 'غير محدد'}"
    )
    st.write(
        f"🚘 **السيارة:** {row['car_info'] if pd.notna(row['car_info']) and row['car_info'] else 'غير مسجل'}"
    )

    clean_phone = (
        str(row["phone"]).replace(" ", "").replace("-", "")
        if pd.notna(row["phone"]) and row["phone"]
        else ""
    )
    if clean_phone and clean_phone.lower() != "nan":
      c_call, c_wa = st.columns(2)
      with c_call:
        st.link_button(
            "📞 اتصال هاتفي", f"tel:{clean_phone}", use_container_width=True
        )
      with c_wa:
        wa_phone = (
            clean_phone[1:] if clean_phone.startswith("0") else clean_phone
        )
        wa_msg = f"السلام عليكم، سيارتكم رقم ({p_full}) متوقفة حالياً بشكل يعرقل المرور في موقف الإقامة، يرجى التكرم بتحريكها وشكراً."
        wa_link = f"https://wa.me/212{wa_phone}?text={wa_msg.replace(' ', '%20')}"
        st.link_button(
            "⚠️ تنبيه بالعرقلة (واتساب)", wa_link, use_container_width=True
        )


# ----------------- أزرار التنقل الرئيسية -----------------
if "active_tab" not in st.session_state:
  st.session_state.active_tab = "camera"

st.title("🚗 مواقف سيارات الإقامة")

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

# ==================== 1. قسم الكاميرا المباشرة ====================
if st.session_state.active_tab == "camera":
  st.subheader("📷 التقاط لوحة السيارة")

  # كاميرا التطبيق المباشرة
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
      df = get_all_records()
      exist_match = (
          df[df["plate_number"].astype(str) == str(main_num)]
          if not df.empty
          else pd.DataFrame()
      )

      if not exist_match.empty:
        st.warning("⚠️ هذه السيارة مسجلة مسبقاً في النظام:")
        for _, row in exist_match.iterrows():
          render_car_card(row)
      else:
        st.success(f"🎯 ترقيم جديد: **{full_display}**")
        with st.form("census_form"):
          c_p1, c_p2, c_p3 = st.columns([2, 1, 1])
          with c_p1:
            p_num = st.text_input("الأرقام *", value=main_num)
          with c_p2:
            idx = (
                letters_list.index(detected_let)
                if detected_let in letters_list
                else 0
            )
            p_let = st.selectbox("الحرف", letters_list, index=idx)
          with c_p3:
            p_reg = st.text_input("العمالة", value=region_num, placeholder="26")

          car_type = st.radio(
              "صفة السيارة:", ["مقيم", "زائر مؤقت"], horizontal=True
          )

          st.caption("👇 الخانات التالية اختيارية لحفظ الترقيم فوراً:")
          c_b, c_a = st.columns(2)
          with c_b:
            bld = st.text_input("رقم العمارة", placeholder="مثال: 12")
          with c_a:
            apt = st.text_input("رقم الشقة", placeholder="مثال: 4")

          name = st.text_input("اسم الساكن (اختياري)")
          phone = st.text_input("الهاتف (اختياري)")
          car_desc = st.text_input("نوع ولون السيارة (اختياري)")

          if st.form_submit_button(
              "💾 حفظ الترقيم فوراً في المنظومة", use_container_width=True
          ):
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
                  car_type,
                  car_desc,
                  "",
              )
              st.success("تم الحفظ بنجاح!")
              st.rerun()
            else:
              st.error("يرجى التأكد من كتابة أرقام اللوحة.")
    else:
      st.warning(
          "تعذر قراءة أرقام واضحة، حاول تقريب الكاميرا أو سجلها يدوياً."
      )

# ==================== 2. قسم الاستعلام ====================
elif st.session_state.active_tab == "search":
  st.subheader("🔍 استعلام سريع عن سيارة")
  query = st.text_input("ابحث بالترقيم، العمارة، أو اسم الساكن:")
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
          render_car_card(r)
      else:
        st.warning("لا توجد سيارة مطابقة لبيانات البحث.")

# ==================== 3. قسم التسجيل اليدوي ====================
elif st.session_state.active_tab == "add":
  st.subheader("➕ تسجيل سيارة يدوياً")
  with st.form("manual_add"):
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
      p_num = st.text_input("أرقام اللوحة *", placeholder="78954")
    with c2:
      p_let = st.selectbox("حرف اللوحة", letters_list)
    with c3:
      p_reg = st.text_input("العمالة", placeholder="26")

    car_type = st.radio("الصفة:", ["مقيم", "زائر مؤقت"], horizontal=True)

    c_b, c_a = st.columns(2)
    with c_b:
      bld = st.text_input("العمارة (اختياري)")
    with c_a:
      apt = st.text_input("الشقة (اختياري)")

    name = st.text_input("اسم الساكن (اختياري)")
    phone = st.text_input("رقم الهاتف (اختياري)")
    car_desc = st.text_input("نوع ولون السيارة")

    if st.form_submit_button("💾 حفظ في المنظومة", use_container_width=True):
      if p_num:
        df = get_all_records()
        if (
            not df.empty
            and not df[df["plate_number"].astype(str) == str(p_num)].empty
        ):
          st.error(f"⛔ اللوحة ({p_num}) مسجلة مسبقاً بالفعل في المنظومة!")
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
              car_type,
              car_desc,
              "",
          )
          st.success("تم الحفظ بنجاح!")
          st.rerun()
      else:
        st.error("أدخل رقم اللوحة على الأقل.")

# ==================== 4. قسم الإدارة وتحديث البيانات ====================
elif st.session_state.active_tab == "admin":
  st.subheader("🔒 إدارة المنظومة وقاعدة البيانات")

  admin_pass = st.text_input(
      "أدخل الرمز السري للإدارة للوصول للبيانات:", type="password"
  )

  if admin_pass == ADMIN_PIN:
    st.success("🔓 تم التحقق بنجاح من هوية الإدارة.")
    df = get_all_records()

    if not df.empty:
      m1, m2, m3 = st.columns(3)
      m1.metric("إجمالي السيارات", len(df))
      m2.metric(
          "البيانات المكتملة",
          df["apartment"].replace("", np.nan).dropna().count(),
      )
      missing_count = df["apartment"].replace("", np.nan).isna().sum()
      m3.metric("تحتاج إكمال الشقة ⚠️", missing_count)

      # قسم استكمال البيانات التي جمعت أولاً
      st.markdown("---")
      st.subheader("⚡ إكمال بيانات الترقيمات المجمعة بدون شقق")

      missing_df = df[df["apartment"].replace("", np.nan).isna()]
      if not missing_df.empty:
        st.info(f"يوجد ({len(missing_df)}) سيارة بحاجة لتحديد العمارة والشقة.")
        selected_car_id = st.selectbox(
            "اختر اللوحة المراد إكمال بياناتها:",
            options=missing_df["id"].tolist(),
            format_func=lambda x: (
                f"معرف [{x}] - لوحة:"
                f" {missing_df[missing_df['id']==x]['full_plate'].values[0]}"
            ),
        )

        row_sel = missing_df[missing_df["id"] == selected_car_id].iloc[0]
        with st.form("complete_data_form"):
          st.write(f"تعديل بيانات اللوحة: **{row_sel['full_plate']}**")
          c1, c2 = st.columns(2)
          with c1:
            new_bld = st.text_input("رقم العمارة *", value=row_sel["building"])
            new_name = st.text_input(
                "اسم الساكن", value=row_sel["resident_name"]
            )
          with c2:
            new_apt = st.text_input("رقم الشقة *", value=row_sel["apartment"])
            new_phone = st.text_input("رقم الهاتف", value=row_sel["phone"])
          new_notes = st.text_input("ملاحظات", value=row_sel["notes"])

          if st.form_submit_button(
              "💾 حفظ وتحديث البيانات", use_container_width=True
          ):
            update_record_details(
                selected_car_id,
                new_bld,
                new_apt,
                new_name,
                new_phone,
                new_notes,
            )
            st.success("تم تحديث بيانات السيارة بنجاح!")
            st.rerun()
      else:
        st.success("🎉 ممتاز! كافة السيارات المسجلة مكتملة البيانات.")

      st.markdown("---")
      st.subheader("📋 الجدول الشامل للسيارات")
      st.dataframe(df, use_container_width=True)

      towrite = io.BytesIO()
      with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="السيارات")
      towrite.seek(0)

      st.download_button(
          label="📥 تنزيل كافة البيانات في ملف Excel (.xlsx)",
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
  elif admin_pass:
    st.error("الرمز السري غير صحيح. يرجى المحاولة مجدداً.")
