def auto_load_fm6():
  """تحميل دليل الشقق تلقائياً من ملف fm6.xlsx الموجود في المستودع"""
  # فحص وجود الجدول أولاً
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("SELECT COUNT(*) FROM apartments_directory")
  current_count = c.fetchone()[0]
  conn.close()

  # إذا كانت القاعدة فارغة والملف موجود في المستودع
  if current_count == 0 and os.path.exists("fm6.xlsx"):
    try:
      df = pd.read_excel("fm6.xlsx")
      first_row_vals = [str(v).lower().strip() for v in df.iloc[0].values]
      if any(
          x in first_row_vals
          for x in ["apartment", "شقة", "immeuble", "building"]
      ):
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)

      col_map = {}
      for col in df.columns:
        c_lower = str(col).lower().strip()
        if any(k in c_lower for k in ["apt", "apartment", "شقة", "شقه"]):
          col_map[col] = "apartment"
        elif any(
            k in c_lower for k in ["bld", "building", "عمارة", "عماره", "imm"]
        ):
          col_map[col] = "building"
        elif any(
            k in c_lower
            for k in [
                "type",
                "نوع",
                "صنف",
                "f2",
                "f3",
                "f4",
                "typologie",
                "modèle",
            ]
        ):
          col_map[col] = "apartment_type"
        elif any(
            k in c_lower
            for k in ["name", "resident", "nom", "اسم", "قاطن", "ساكن"]
        ):
          col_map[col] = "resident_name"
        elif any(k in c_lower for k in ["phone", "tel", "هاتف", "جوال", "نقال"]):
          col_map[col] = "phone"

      df = df.rename(columns=col_map)
      df = df.loc[:, ~df.columns.duplicated()]

      if "apartment" in df.columns and "building" in df.columns:
        for _, row in df.iterrows():
          apt = clean_str(row.get("apartment", ""))
          bld = clean_str(row.get("building", ""))
          apt_type = clean_str(row.get("apartment_type", ""))
          name = clean_str(row.get("resident_name", ""))
          phone = clean_str(row.get("phone", ""))
          if apt and bld:
            add_or_update_apartment_dir(bld, apt, apt_type, name, phone)
    except Exception:
      pass


auto_load_fm6()
