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
    page_title="تدبير موقف سيارات إقامة نفيس",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ADMIN_PIN = "1234"
DB_FILE = "residence_parking.db"

# ----------------- تصميم واجهة التطبيق الاحترافية (CSS) -----------------
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Cairo', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
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
        letter-spacing: -0.5px;
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

    [data-testid="stCameraInput"] {
        width: 100% !important;
        max-width: 100% !important;
    }
    [data-testid="stCameraInput"] video {
        width: 100% !important;
        height: auto !important;
        min-height: 270px !important;
        border-radius: 16px !important;
        border: 3px solid #3b82f6 !important;
        box-shadow: 0 12px 30px rgba(59, 130, 246, 0.2) !important;
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
    .plate-item {
        font-size: 20px;
        font-weight: 900;
        color: #0f172a;
    }
    .plate-divider {
        width: 2px;
        height: 22px;
        background-color: #cbd5e1;
    }

    .stTextInput > div > div > input, .stSelectbox > div {
        border-radius: 10px !important;
        border: 1px solid #cbd5e1 !important;
        padding: 10px 14px !important;
        font-weight: 600 !important;
    }

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


def render_car_card(row):
  p_num = str(row["plate_number"]) if pd.notna(row["plate_number"]) else ""
  p_let = (
      str(row["plate_letter"])
      if pd.notna(row["plate_letter"]) and row["plate_letter"]
      else "-"
  )
  p_reg = (
      str(row["plate_region"])
      if pd.notna(row["plate_region"]) and row["plate_region"]
      else "-"
  )
  bld = (
      row["building"]
      if pd.notna(row["building"]) and row["building"]
      else "—"
  )
  apt = (
      row["apartment"]
      if pd.notna(row["apartment"]) and row["apartment"]
      else "—"
  )
  c_type = (
      row["car_type"]
      if "car_type" in row and pd.notna(row["car_type"])
      else "مقيم"
  )

  clean_phone = (
      str(row["phone"]).replace(" ", "").replace("-", "")
      if pd.notna(row["phone"]) and row["phone"]
      else ""
  )

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
          f"🏢 **العمارة:** `{bld}` &nbsp;&nbsp;|&nbsp;&nbsp; 🚪 **الشقة:**"
          f" `{apt}`"
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


# ----------------- شريط الملاحة والتنقل -----------------
if "active_tab" not in st.session_state:
  st.session_state.active_tab = "camera"

# ترويسة التطبيق بإسم إقامة نفيس
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

# ==================== 1. قسم الكاميرا ====================
if st.session_state.active_tab == "camera":
  st.caption("🎯 وجّه الكاميرا نحو ترقيم السيارة للتعرف الفوري:")
  camera_file = st.camera_input("")

  if camera_file is not None:
    reader = get_ocr_reader()
    image = Image.open(io.BytesIO(camera_file.getvalue()))
    image_np = np.array(image)

    with st.spinner("⚡ جاري قراءة الترقيم بدقة..."):
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
        st.warning("⚠️ هذه اللوحة مسجلة مسبقاً في النظام:")
        for _, row in exist_match.iterrows():
          render_car_card(row)
      else:
        st.success(f"🎯 ترقيم مرصود: **{full_display}**")
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
              "الصفة:", ["مقيم", "زائر مؤقت"], horizontal=True
          )

          st.caption("👇 الخانات التالية اختيارية لحفظ الترقيم فوراً:")
          c_b, c_a = st.columns(2)
          with c_b:
            bld = st.text_input("العمارة", placeholder="مثال: 12")
          with c_a:
            apt = st.text_input("الشقة", placeholder="مثال: 4")

          name = st.text_input("اسم الساكن (اختياري)")
          phone = st.text_input("الهاتف (اختياري)")
          car_desc = st.text_input("نوع ولون السيارة (اختياري)")

          if st.form_submit_button(
              "💾 حفظ الترقيم فوراً في النظام", use_container_width=True
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
              st.error("يرجى كتابة رقم اللوحة.")
    else:
      st.warning(
          "تعذر قراءة أرقام واضحة، حاول التقاط صورة أقرب للوحة."
      )

# ==================== 2. قسم الاستعلام ====================
elif st.session_state.active_tab == "search":
  st.subheader("🔍 استعلام سريع")
  query = st.text_input(
      "بحث بالترقيم، العمارة، أو اسم الساكن:", placeholder="اكتب للبحث..."
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
          render_car_card(r)
      else:
        st.info("لا توجد سيارة مطابقة لبيانات البحث.")

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
  st.subheader("🔒 إدارة المنظومة")
  admin_pass = st.text_input("أدخل الرمز السري للإدارة:", type="password")

  if admin_pass == ADMIN_PIN:
    st.success("🔓 تم التحقق بنجاح من هوية الإدارة.")
    df = get_all_records()

    if not df.empty:
      m1, m2, m3 = st.columns(3)
      m1.metric("إجمالي السيارات", len(df))
      m2.metric(
          "مكتملة البيانات",
          df["apartment"].replace("", np.nan).dropna().count(),
      )
      missing_count = df["apartment"].replace("", np.nan).isna().sum()
      m3.metric("بحاجة لإكمال الشقة ⚠️", missing_count)

      st.markdown("---")
      st.subheader("⚡ إكمال بيانات الترقيمات المجمعة")

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
        st.success("🎉 كافة السيارات المسجلة مكتملة البيانات.")

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
    with st.expander("📤 استعادة أو رفع بيانات من ملف Excel"):
      uploaded_excel = st.file_uploader(
          "اختر ملف Excel لاسترجاع السيارات", type=["xlsx"]
      )
      if uploaded_excel is not None:
        df_up = pd.read_excel(uploaded_excel)
        for _, row in df_up.iterrows():
          p_num = str(row.get("plate_number", "")).strip()
          if p_num and (
              df.empty or df[df["plate_number"].astype(str) == p_num].empty
          ):
            add_record(
                str(row.get("building", "")),
                str(row.get("apartment", "")),
                str(row.get("resident_name", "")),
                str(row.get("phone", "")),
                p_num,
                str(row.get("plate_letter", "")),
                str(row.get("plate_region", "")),
                str(row.get("full_plate", "")),
                str(row.get("car_type", "مقيم")),
                str(row.get("car_info", "")),
                str(row.get("notes", "")),
            )
        st.success("✅ تمت استعادة كافة السيارات ودمجها بنجاح!")
        st.rerun()

  elif admin_pass:
    st.error("الرمز السري غير صحيح. يرجى المحاولة مجدداً.")
