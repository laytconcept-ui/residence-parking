import io
import re
import sqlite3
import easyocr
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st

# ضبط الصفحة على layout="wide" لتوسيع مساحة الرؤية والكاميرا
st.set_page_config(
    page_title="تدبير سيارات الإقامة",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----------------- تنسيق مخصص لتكبير حيز الكاميرا -----------------
st.markdown(
    """
<style>
    /* تكبير حيز إطار الكاميرا ليكون عريضاً وواضحاً على الهاتف */
    [data-testid="stCameraInput"] {
        width: 100% !important;
        max-width: 100% !important;
    }
    [data-testid="stCameraInput"] video {
        width: 100% !important;
        height: auto !important;
        border-radius: 14px !important;
        border: 2px solid #0284c7 !important;
        box-shadow: 0 4px 15px rgba(2, 132, 199, 0.15) !important;
    }
    /* تحسين مظهر الأزرار لتكون سهلة اللمس */
    div.stButton > button {
        border-radius: 10px !important;
        font-weight: 700 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

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
            car_info TEXT,
            notes TEXT
        )
    """)
  try:
    c.execute("ALTER TABLE residents_cars ADD COLUMN full_plate TEXT")
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
    car_info,
    notes,
):
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute(
      """
        INSERT INTO residents_cars (building, apartment, resident_name, phone, plate_number, plate_letter, plate_region, full_plate, car_info, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

# ==================== 1. مسح الكاميرا العريض والجرد الذكي ====================
if st.session_state.active_tab == "camera":
  st.subheader("📷 التقاط لوحة السيارة")
  st.caption("تم توسيع مجال الرؤية لالتقاط اللوحة براحة ومن مسافة مناسبة.")

  # حيز كاميرا عريض
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

      # فحص هل الترقيم مسجل مسبقاً لمنع التكرار نهائياً
      df = get_all_records()
      is_duplicate = False

      if not df.empty:
        exist_match = df[df["plate_number"].astype(str) == str(main_num)]
        if not exist_match.empty:
          is_duplicate = True

      if is_duplicate:
        # رسالة تنبيه بلون بارز مع تعطيل الحفظ
        st.error(
            "⛔ تنبيه: هذه السيارة مسجلة مسبقاً في قاعدة البيانات! لن يتم حفظها"
            " مرة ثانية."
        )
        st.info("📋 البيانات المسجلة لهذه اللوحة سابقاً:")
        st.dataframe(
            exist_match[[
                "id",
                "building",
                "apartment",
                "plate_number",
                "plate_letter",
                "plate_region",
                "resident_name",
                "phone",
            ]],
            use_container_width=True,
        )
      else:
        st.success("✅ ترقيم جديد غير مكرر، يمكنك حفظه الآن مباشرة:")
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

          st.caption(
              "👇 الخانات التالية اختيارية (يمكن تركها فارغة وتعبئتها لاحقاً):"
          )
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

          car_desc = st.text_input(
              "نوع ولون السيارة (اختياري)", placeholder="مثال: Dacia رمادية"
          )

          save_now = st.form_submit_button(
              "💾 حفظ الترقيم فوراً في الجدول", use_container_width=True
          )

          if save_now:
            if p_num:
              # تحقق أخير قبل الإدخال
              check_df = get_all_records()
              if (
                  not check_df.empty
                  and not check_df[
                      check_df["plate_number"].astype(str) == str(p_num)
                  ].empty
              ):
                st.error("تم تسجيل هذا الرقم للتو من قبل مستخدم آخر!")
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
                st.success(
                    f"🎉 تم تسجيل الترقيم [{full_plate_str}] في الجدول بنجاح!"
                )
                st.rerun()
            else:
              st.error("يرجى التأكد من وجود رقم اللوحة.")
    else:
      raw_text = " ".join(detected_texts)
      st.warning(
          f"تعذر استخراج رقم واضح. المحتوى المرصود: {raw_text if raw_text else 'لا يوجد'}"
      )
      st.info("يمكنك تدوين الترقيم من تبويب ➕ يدوي.")

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

# ==================== 3. قسم التسجيل اليدوي (مع التحقق من التكرار) ====================
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
        df = get_all_records()
        if (
            not df.empty
            and not df[df["plate_number"].astype(str) == str(p_num)].empty
        ):
          st.error(
              f"⛔ الترقيم ({p_num}) مسجل مسبقاً بالفعل في النظام! يرجى التأكد من"
              " اللوحة."
          )
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
          st.success("تم الحفظ بنجاح!")
          st.rerun()
      else:
        st.error("أدخل أرقام اللوحة على الأقل.")

# ==================== 4. قسم الإدارة وتصدير Excel مع تظليل التكرار ====================
elif st.session_state.active_tab == "admin":
  st.subheader("📊 جدول الترقيمات والسيارات المسجلة")
  df = get_all_records()
  if not df.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("إجمالي السيارات المسجلة", len(df))
    c2.metric(
        "شقق مكتملة البيانات",
        df["apartment"].replace("", np.nan).dropna().count(),
    )
    c3.metric(
        "ترقيمات بدون شقق بعد",
        df["apartment"].replace("", np.nan).isna().sum(),
    )

    # دالة تلوين السجلات لتوضيح أي تكرار بالألوان
    def highlight_duplicates(data):
      dup_mask = data.duplicated(subset=["plate_number"], keep=False)
      return [
          "background-color: #fee2e2; color: #991b1b; font-weight: bold"
          if is_dup
          else ""
          for is_dup in dup_mask
      ]

    styled_df = df.style.apply(highlight_duplicates, axis=0)

    st.write(
        "💡 *ملاحظة:* إذا كان هناك أي ترقيم متكرر، سيظهر مظللاً باللون الأحمر"
        " الخفيف."
    )
    st.dataframe(styled_df, use_container_width=True)

    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
      df.to_excel(writer, index=False, sheet_name="ترقيمات السيارات")
    towrite.seek(0)

    st.download_button(
        label="📥 تنزيل الجدول في ملف Excel (.xlsx)",
        data=towrite,
        file_name="residence_parking_census.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        use_container_width=True,
    )

    with st.expander("🗑️ حذف سطر من الجدول"):
      del_id = st.number_input(
          "أدخل رقم السجل (ID) لحذفه:", min_value=1, step=1
      )
      if st.button("تأكيد الحذف", use_container_width=True):
        delete_record(del_id)
        st.rerun()
  else:
    st.info("الجدول فارغ حتى الآن. ابدأ بالتقاط اللوحات عبر الكاميرا.")
