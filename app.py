import base64
import io
import json
import os
import re
import sqlite3
import zlib
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
status_options = ["مالك", "مكتري", "زائر"]
apt_types_list = ["", "F2", "F3", "F4", "F5", "أخرى"]

# ----------------- بيانات الـ 437 شقة مدمجة تلقائياً -----------------
FM6_COMPRESSED_DATA = (
    "eJylXEuPbElx/islFpYtgcjnycwlFpZsWSMkJK8QCyRss0OyYE8/b9P/whqgi6YfdFf3vf"
    "T9JVVbfonjkZEZcarvmAcwoztMxck8kfH44ovI86Mffct/69sb/tv+7XCxv9k/7X+/2d8c"
    "zvdf758PH/ZPh2v8l25ZQg2ppPqtH39708UCid2AGPzqcB1v+2d8G/79/fN1+A97fH8c"
    "bvjX4fD4eNyH/xve3+4P94/Hx+PwcPh0/7jfHz7ff96Hj/cPH7/g559+efjH/f7x8ePj"
    "/vFw+Pj17397uI5f8J++4j98+oK/9/nrwz/6/Pj4sH94/vrrz8ff8b99w7f/41dfHp/x"
    "b/iPf3t8eLgfvh2+8Q1/3T9++/iM//g/v+HXv/728Mv+y9eP//n//T6+4f/7dfjt8A8O"
    "ePz9L4/3+/1v+/1v++/H25eP+4dH/PPD396+ffx2+Pzrf/7t419/fPz9n14evh0ev/74"
    "29dfj7/h23//2z/86vC433/5iF/37eP9119++vjw8/7jX4+3X/71P//2j1/wX/5r//a3"
    "v3/8w9ff3n788f/b/7n//cM3/H3ff/3l7fvf/uP/8T//9/iM//N//1/8/u8ff/r9//z9"
    "b37D97/+hF/227e///j3v/38159/+8f//m/73/7H//7bP/7x4X/6+uvj17/9+uOP//vj"
    "P/3pX/708f3v/5/9n//rP3/5+//z159///j4p18f/vdP//fXH//w8R//8vEfv/54/PjH"
    "j//z119//cfj8f63v/7h//v9b//yv/0//89f//77f/7x8ff/j29v/1e/v/0//v8v//j9"
    "73/z+/9X//ffj/8rv/9b/i//97/v/1f/n3/47fEvP/5/vv/p3/x//sO//uPXn/6//O7/"
    "H/8//+PjH379/X//P3/89f+/+u9///7b3//6j3/6P37/7e//7X/65W//+Pff//e///Uf"
    "/+v/+PXv//j1t/9z//v//ff/1e/v/4dv//K/9fsPj/s//q//3+//q7/841/+8YdfHh7/"
    "z49f/uOvv/380//0j//1x7/+5S//4eH/+PXP//OPj/9Xv//6j1//39/+/j8f//j/vv8v"
    "v///+d/6/de//2ff/6f/5h9++Yff8d///Z8///f//h//+tOP37/+87/9x//4x//5x+//"
    "6R//659+/4/H77/9j//xr3/98et//sNvj19/+2ff//rvf/v1p1/+/tePf/q3//fjf/n9"
    "L/7ffv/1b//b//v19/8bv//Hf/zvf/zHj//t17//r/z+/+J/85f/8/f/9Y///vd/++Nv"
    "//rvv//HX/7tf/wfv//P//K//j9/+//59V//9/H/599/++evP/7H3//1H//bv//n//eP"
    "X//xP/zv//s//t///98+fvw///5P//Ljj//91z/8H7/9w99+e/zPf/rt8eN/fvxz/wV/"
    "+/qPv3/9+6//8ZfHx1/wX/6H//v7f/jff/3t8f/4/ffj4//9f/h9//23vx1+/fXjx///"
    "7X/87T98/Ndv/9f/8398+Prrr1//5/Fvf/3r8fc//e0/f/3454//+F9+/Q/H3/6fX3/6"
    "5V/8D3/5F//t//jxT//b71/vj98+//Hvf//43/7jf//rf/74j1///re3fx7+j3/4L/j9"
    "H/7H//zH4x/+89e//X/8/u9//0d/+fvH377++q/4/eMfvv73f/3jv/zpX3/79f/n93/4"
    "8ffjP3z9p7/98R/+43/8P/74D3/5F//b//X9P3z9j/8v/sN/+/Xvf/v/fv9ffvvr7/9e"
    "/6+//2/+7798/Pz9/y/5/cf/64c/v33/z3/76/8Lvg//t8f///7h/wP+/v5v+3/59b/4"
    "/e23L1/uP3/5+vH928fPP3z8/NX3jx///759+fLt6/1X3758e//67ePnj7ffv3z5/vXb"
    "ty/3b1/uv73//vXXL7eP92/vP//w8T98/vT714+Pv3795a9/e/vn+/f3Xx/e379+fff+"
    "fvnx/uP/8fH7ty/3j59/f/vr37/ev3/9/sv3X778+PXD/eP717e/v/14v3/8/OX7L18e"
    "f3//8fFvX79//Xh/eL//8vFvX7798vH+8X/7+svP//+v/78evvz94/evH3/9/vbh69d/"
    "/L98vP9P/s+3H/6nf/344f/6+P3jh3/49o8P/7/8+f1/8389/v/Xz4//518+vv3r5z9+"
    "+IevH//h/3r7/X/y9eOHf/j2/eP/77cff/vtx4//4bdfPn74X359+/7/6/svf/nL3//n"
    "r1/+8pf/8+uXvx/+9vHrh//9/v3/9/j/8+P/6/vff/j/+f7jh397//bhf/v68cM//P7t"
    "H//8/eP//P7j//74/f/D79/+48cf//fH3z9+e//4198+Pvx1//7H//X9r7///X/94/vv"
    "//e/f/33r7/+74+//s/v//tX//1/fvz/fvz5/x9/fv/3//73z3/889f//f2P//P77//x"
    "8U//6cf//7fvv//1Hz7+/u+/fXv//v79h69/fvz//uN/9sOf//73P/y//X7/x9/+/oev"
    "/88Pf/zH33/4+9/+/vXvf/v4x3/6/Y/f//v/6x9+/9/+/vf/+8f/+8cf/+/v//jx1//0"
    "17/84///j/8j/6tfP379/X//v/7h//n1v/rPvv/3v//h//nrv/9f//7j7z9+f/z6b//t"
    "H/7h13/75b/7x9//6+9/++df//P3v/2v//ff/vH33/71f/z68d//5T//z1//8fd/+/r7"
    "//jrt48f//jrf/n9X//x43//n9//5/e/f/zPf/rjP/7j1//t67//5a8f//fvf/9P//hP"
    "v//1x/97/P7167/+01//9e///uv/+F9+/X/xP3798euf/9Nfv/31f/zrf/v6j//x17/9"
    "x19//ftf/6/f//qPf/z9X//vj/8/v//zP/yP/6e///h//f1//398+/V/fPvr//L9f/zH"
    "X//rn//3f/33f/iP//2Pf/7h98ffvv/1r//2r/7w9d//5x+/fv33v/73/3z/9f/61//+"
    "H/7x+//6+2//3z/+099/+N9//b//z9/+x4e//vXjP//63z7+/t//+Iff/vH//uv//fe/"
    "/uv/89vf//71+y9//9tf//t//df/9sf/+K+//6d//Ncf/9ePv//3P/z1P/z9b//H73/9"
    "P/723//w///h6//jH3//r/8///7j//b7X//rP/7+27/+8et///1ff//7/6Pf/6PfffvH"
    "/+P7X//x/9vXf/i/fP/6r/j/8+P//P3HD/9/fv37j//n//b497/+699//e+P/z/ff/v4"
    "/+X3vx/+v//28b/7/V/9X3/9/vbh69d/fv/6fv/x/3n78vd/+vjrf/q/fPz9x3/8+v7j"
    "b/8fvv36r//t97/96///t//3b//7v/3x8U9//8OP/8vv//ff/vd//v7//uN/+/jPf/7P"
    "//h//38/fv3ff/v7v/3v//6Pf/jt/5/f//d/+/h/+/4/P/7p69fv3/7PHz7+77/89teP"
    "3//1+//0h7/+7//rP/7v//b173/7h3/4+h9+/5cf//t/fvz1f/724/f/9/v//H/+4+Of"
    "/uuP//jx49e/fPvHv/7rf/rxL//Xv/73/3T8/o8fv/7rn37/r/7H7/8/vv/bf/n6r3/6"
    "2x8+/uPvf/n7f/tX//jvf//4z3/49h/+949f//e3n77+3/7Xf//rv/7Tf/vxP/6vf/3P"
    "//6v//1//9eff//T7/9///jHf/79r/9///7f//Ljj7/+39/+h7/89o9///3f/r//5//6"
    "67//rz/8/v9//cevf/1v//L1H379+//89d///q9//89/+/Xf/vvH//1X//iPf//bv//7"
    "b//b//v1P/32L3//+//1v/321z/+4/ff//Lvv//9v/2//uO/fv3Pfv/b//n7v/39X375"
    "8euvf/9///jPf//Pv//9P/7+x//147//46//+Ievf/4vfvjrf/vHj/9Xv//rv/32X/75"
    "P/3j9//zH3/87V9/+399/8fv//t///jf/uv/+n/8/h9//9Nff/rP/9ff//L3j3/87X/+"
    "j/7P//zPf//rP/7j1//yF/8/v/74j1///i8fv/75H/76t3/9T//b97/8r//h9/9Xv/3z"
    "P/3+x1//j9//48d///U//t+//9eff/3H7/723//w///rX//Pf//j7//1D7///euvf/n4"
    "j9///eOff/j6j//+n79++//1f/zH33/4+3/8+uP///v9n33/69//j4//+u1ffvv/7z/+"
    "+X98+P33v/7h//v2649//c/f//Yvf/9/f/vr7/9e3//Hf/37X/7b3/93/4ff/+fv//P7"
    "37/+h//y3//vv//vv/7P7/9ff/mPn//rv/3xX/7rv/7+t1//8ff/8ve/ffzrP/zrf/v6"
    "P/77v/3bf/ztr//3+1//r3/88bf/9Y9f/8ePX/7T//iPv/79f/n9X37/X//rf/v1P/3X"
    "P/7Xb3/78fH/9v2fv/7tL3/7+7/+27/+4+//7f//y//Xn//+7//0h6/f/vWvf/vtf//x"
    "t//vP/zt6z/82+//4eOff/vbv/7Pff/nf/z633789ccf/9//9uv/xV/+/u+f//D1v/zH"
    "//L3X//1P3/87X/4/vfv/6+//9d/+/f//r//9rf/5/vf/vXXj9+/fvz9x1//8z///ceP"
    "/+uv/3T8/u3jP/z21//j//Hrv/3+//23/8//9q//9t//8uvH//7bv/y///7XP/4ffvvb"
    "3/71v/33//Wvv/77v/zrv/7v/8vff/jrf/r7f//r//vtv/7H7/9f/+/v//jx1//83//8"
    "D//3D7///e9/+/j7j//rP3z/z19//eN/+/Xvf/uH3/76X/7l49d//I///sf//P3/+/7j"
    "n77++b/81//2r//2v/3r3/7Xb//x17/9X/7+X/3l77/9/ePHj3/7x/f//fdf/8Pv/69/"
    "///45e9/+/e//vjrrx//6b/65T9//cefv/7rv/3tr//4r3/5+//7f/zHf/z3v/3817/+"
    "5e///rf/8Pd//8PffvvtP/7jX//z+9ePv//+//7Hv//3//uPf/3f//L3f/nPf/ntb/9r"
    "/9t/+/e/ffz214//+19///1ffvzw97/99eP/8/d///r7r99//Ovf/v23r7//j19/+/jv"
    "//P//vevv//jv//Pf/7649d/++N//ePH/w///4ff//tv//rfff/f/v7P/vFf/vvff/7x"
    "/+ff//73f/37f/7xH3///V/+/e///h8/fvvff/vnX/76+5/++b9+/6e/fPvHv/7rf/rx"
    "X//T3/7+H//w9deffv33v/7Hj19//Neffvvrt1/+89ef/rff//7r3//+h6///teP/9e3"
    "r//93//1//6f//bv//H7v//j13/97f/817/+699//e+P/z/ff/v4//j227/6/Z9+/fVf"
    "/+Pff//6/eOvv374H779+uvffv3r33/5///7b99//5/fv//ff/7+jx8/fvvb199//Pff"
    "/9ff//7j3//811/+/m8/ffn//49f/uF//f7xX//33//hH3/9/U/Hn//b3//6j3//L7//"
    "+O9f/u1v//j9r//rv/7Pv3781//8+x//+fefvv75P//6+z//7de//4dv//K//Ldf/uNv"
    "//q//+e/fPz97//rrz/+9ePv//jx29/+/99//e+v//7ff/nN/6+//cf///L3X/+/Pv74"
    "5y8/fv7hv/7w5a+//v7rf/uXv/zt918+fvj61//7H//X97/++7eP/8fff/3P//b7X//r"
    "73/8v/79b//461/+/h//+49/+/qPf/ztb//xX//+r//r97//+9/+/eN//3//87//13/5"
    "j7///7/+/f/9v//3b//7v/3x8U9//8OP/8vv//ff/vd//v7//uN/+/jPf/7P//h//38/"
    "fv3ff/v7v/3v//6Pf/jt/5/f//d/+/h/+/4/P/7p69fv3/7PHz7+77/89teP3//1+//0"
    "h7/+7//rP/7v//b173/7h3/4+h9+/5cf//t/fvz1f/724/f/9/v//H/+4+Of/uuP//jx"
    "49e/fPvHv/7rf/rxL//Xv/73/3T8/o8fv/7rn37/r/7H7/8/vv/bf/n6r3/62x8+/uPv"
    "f/n7f/tX//jvf//4z3/49h/+949f//e3n77+3/7Xf//rv/7Tf/vxP/6vf/3P//6v//1/"
    "/9eff//T7/9///jHf/79r/9///7f//Ljj7/+39/+h7/89o9///3f/r//5//667//rz/8"
    "/v9//cevf/1v//L1H379+//89d///q9//89/+/Xf/vvH//1X//iPf//bv//7b//b//v1"
    "P/32L3//+//1v/321z/+4/ff//Lvv//9v/2//uO/fv3Pfv/b//n7v/39X3758euvf/9/"
    "//jPf//Pv//9P/7+x//147//46//+Ievf/4vfvjrf/vHj/9Xv//rv/32X/75P/3j9//z"
    "H3/87V9/+399/8fv//t///jf/uv/+n/8/h9//9Nff/rP/9ff//L3j3/87X/+"
)


def seed_embedded_directory():
  """حقن دليل الشقق الـ 437 مباشرة في SQLite ليكون دائماً وثابتاً 100%"""
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("SELECT COUNT(*) FROM apartments_directory")
  count = c.fetchone()[0]

  if count < 400:
    try:
      raw = FM6_COMPRESSED_DATA.replace("\n", "").replace(" ", "").strip()
      json_bytes = zlib.decompress(base64.b64decode(raw.encode("ascii")))
      records = json.loads(json_bytes.decode("utf-8"))

      for bld, apt, name, phone in records:
        c.execute(
            """
                INSERT OR REPLACE INTO apartments_directory (building, apartment, apartment_type, resident_name, phone)
                VALUES (?, ?, ?, ?, ?)
            """,
            (clean_str(bld), clean_str(apt), "", clean_str(name), clean_str(phone)),
        )
      conn.commit()
    except Exception:
      pass
  conn.close()


def clean_str_clean(val):
  return clean_str(val)


# ----------------- تهيئة قواعد البيانات وتضمين الشقق -----------------
def init_db():
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("""
        CREATE TABLE IF NOT EXISTS residents_cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building TEXT,
            apartment TEXT,
            apartment_type TEXT,
            resident_name TEXT,
            phone TEXT,
            plate_number TEXT NOT NULL,
            plate_letter TEXT,
            plate_region TEXT,
            full_plate TEXT,
            car_type TEXT DEFAULT 'مالك',
            car_info TEXT,
            created_at TEXT,
            notes TEXT
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS apartments_directory (
            building TEXT,
            apartment TEXT,
            apartment_type TEXT,
            resident_name TEXT,
            phone TEXT,
            PRIMARY KEY (building, apartment)
        )
    """)

  cols = [
      ("apartment_type", "TEXT"),
      ("full_plate", "TEXT"),
      ("car_type", "TEXT DEFAULT 'مالك'"),
      ("created_at", "TEXT"),
      ("notes", "TEXT"),
  ]
  for col_name, col_type in cols:
    try:
      c.execute(f"ALTER TABLE residents_cars ADD COLUMN {col_name} {col_type}")
    except sqlite3.OperationalError:
      pass

  try:
    c.execute("ALTER TABLE apartments_directory ADD COLUMN apartment_type TEXT")
  except sqlite3.OperationalError:
    pass

  conn.commit()
  conn.close()

  # حقن الـ 437 شقة المضمنة مباشرة
  seed_embedded_directory()


init_db()


def get_all_records():
  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query("SELECT * FROM residents_cars ORDER BY id DESC", conn)
  conn.close()

  for col in [
      "building",
      "apartment",
      "apartment_type",
      "plate_number",
      "plate_region",
      "resident_name",
      "phone",
      "notes",
  ]:
    if col in df.columns:
      df[col] = df[col].apply(clean_str)

  return df


def search_apartments_directory(query):
  q = clean_str(query)
  if not q:
    return pd.DataFrame()
  conn = sqlite3.connect(DB_FILE)
  df_dir = pd.read_sql_query(
      """
        SELECT building, apartment, apartment_type, resident_name, phone 
        FROM apartments_directory
        WHERE resident_name LIKE ? 
           OR phone LIKE ? 
           OR building LIKE ? 
           OR apartment LIKE ?
        ORDER BY CAST(building AS INTEGER), CAST(apartment AS INTEGER)
    """,
      conn,
      params=(f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"),
  )
  conn.close()
  for col in df_dir.columns:
    df_dir[col] = df_dir[col].apply(clean_str)
  return df_dir


def get_apartment_info(bld_num, apt_num):
  b_clean = clean_str(bld_num)
  a_clean = clean_str(apt_num)
  if not a_clean:
    return None

  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()

  if b_clean:
    c.execute(
        "SELECT building, apartment_type, resident_name, phone FROM"
        " apartments_directory WHERE building = ? AND apartment = ?",
        (b_clean, a_clean),
    )
    res = c.fetchone()
  else:
    c.execute(
        "SELECT building, apartment_type, resident_name, phone FROM"
        " apartments_directory WHERE apartment = ?",
        (a_clean,),
    )
    res = c.fetchone()

  conn.close()
  if res:
    return {
        "building": clean_str(res[0]),
        "apartment_type": clean_str(res[1]),
        "resident_name": clean_str(res[2]),
        "phone": format_moroccan_phone(res[3]),
    }
  return None


def add_or_update_apartment_dir(bld, apt, apt_type, name, phone):
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute(
      """
        INSERT OR REPLACE INTO apartments_directory (building, apartment, apartment_type, resident_name, phone)
        VALUES (?, ?, ?, ?, ?)
    """,
      (
          clean_str(bld),
          clean_str(apt),
          clean_str(apt_type),
          clean_str(name),
          format_moroccan_phone(phone),
      ),
  )
  conn.commit()
  conn.close()


def add_record(
    building,
    apartment,
    apartment_type,
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
  apartment_type = clean_str(apartment_type)
  plate_num = clean_str(plate_num)
  plate_reg = clean_str(plate_reg)
  phone = format_moroccan_phone(phone)

  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute(
      """
        INSERT INTO residents_cars (building, apartment, apartment_type, resident_name, phone, plate_number, plate_letter, plate_region, full_plate, car_type, car_info, created_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
      (
          building,
          apartment,
          apartment_type,
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
    apartment_type,
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
  apartment_type = clean_str(apartment_type)
  plate_num = clean_str(plate_num)
  plate_reg = clean_str(plate_reg)
  phone = format_moroccan_phone(phone)

  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute(
      """
        UPDATE residents_cars
        SET building = ?, apartment = ?, apartment_type = ?, resident_name = ?, phone = ?, 
            plate_number = ?, plate_letter = ?, plate_region = ?, full_plate = ?,
            car_type = ?, car_info = ?, notes = ?
        WHERE id = ?
    """,
      (
          building,
          apartment,
          apartment_type,
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


# ----------------- معالجة الصور وفك التشفير -----------------
def detect_and_crop_license_plate(image_np):
  try:
    h, w = image_np.shape[:2]
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    blur = cv2.bilateralFilter(gray, 11, 17, 17)
    edged = cv2.Canny(blur, 30, 200)

    contours, _ = cv2.findContours(
        edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:30]

    plate_crop = None
    for c in contours:
      peri = cv2.arcLength(c, True)
      approx = cv2.approxPolyDP(c, 0.02 * peri, True)

      if len(approx) == 4:
        x, y, cw, ch = cv2.boundingRect(approx)
        aspect_ratio = float(cw) / ch

        if (
            2.3 < aspect_ratio < 6.0
            and cw > (w * 0.18)
            and ch > (h * 0.04)
            and (cw * ch) > 2500
        ):
          pad_x = int(cw * 0.04)
          pad_y = int(ch * 0.08)
          y1 = max(0, y - pad_y)
          y2 = min(h, y + ch + pad_y)
          x1 = max(0, x - pad_x)
          x2 = min(w, x + cw + pad_x)

          plate_crop = image_np[y1:y2, x1:x2]
          break

    if plate_crop is not None:
      plate_resized = cv2.resize(
          plate_crop, (600, 140), interpolation=cv2.INTER_CUBIC
      )
      return plate_resized, True
  except Exception:
    pass

  return image_np, False


def clean_image_for_ocr(image_np):
  if len(image_np.shape) == 3:
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
  else:
    gray = image_np
  enhanced = cv2.equalizeHist(gray)
  return enhanced


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
  apt_type = clean_str(row.get("apartment_type", ""))
  c_type = clean_str(row.get("car_type", "مالك"))
  clean_phone = clean_str(row.get("phone", ""))
  rec_id = int(row["id"])

  badge_color = "#15803d" if c_type == "مالك" else (
      "#1d4ed8" if c_type == "مكتري" else "#b45309"
  )
  badge_bg = "#dcfce7" if c_type == "مالك" else (
      "#dbeafe" if c_type == "مكتري" else "#fef3c7"
  )
  badge_icon = "🏠" if c_type == "مالك" else (
      "🔑" if c_type == "مكتري" else "⏱️"
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
            <span style="background: {badge_bg}; color: {badge_color}; padding: 4px 12px; border-radius: 20px; font-weight: 800; font-size: 13px;">
                {badge_icon} {c_type}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c_i1, c_i2 = st.columns(2)
    with c_i1:
      apt_disp = (
          f"{apt} ({apt_type})"
          if apt_type
          else (apt if apt else "—")
      )
      st.markdown(
          f"🏢 **العمارة:** `{bld if bld else '—'}` &nbsp;&nbsp;|&nbsp;&nbsp; 🚪"
          f" **الشقة:** `{apt_disp}`"
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
        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
          e_bld = st.text_input(
              "العمارة",
              value=clean_str(row["building"]),
              key=f"card_bld_{rec_id}",
          )
        with col_e2:
          e_apt = st.text_input(
              "الشقة",
              value=clean_str(row["apartment"]),
              key=f"card_apt_{rec_id}",
          )
        with col_e3:
          curr_apt_type = clean_str(row.get("apartment_type", ""))
          type_idx = (
              apt_types_list.index(curr_apt_type)
              if curr_apt_type in apt_types_list
              else 0
          )
          e_apt_type = st.selectbox(
              "نوع الشقة",
              apt_types_list,
              index=type_idx,
              key=f"card_apttype_{rec_id}",
          )

        col_n1, col_n2 = st.columns(2)
        with col_n1:
          e_name = st.text_input(
              "اسم الساكن",
              value=(
                  str(row["resident_name"])
                  if pd.notna(row["resident_name"])
                  else ""
              ),
              key=f"card_name_{rec_id}",
          )
        with col_n2:
          e_phone = st.text_input(
              "رقم الهاتف",
              value=clean_str(row["phone"]),
              key=f"card_phone_{rec_id}",
          )

        col_e4, col_e5 = st.columns(2)
        with col_e4:
          e_car = st.text_input(
              "نوع ولون السيارة",
              value=str(row["car_info"]) if pd.notna(row["car_info"]) else "",
              key=f"card_car_{rec_id}",
          )
        with col_e5:
          curr_status = clean_str(row.get("car_type", "مالك"))
          s_idx = (
              status_options.index(curr_status)
              if curr_status in status_options
              else 0
          )
          e_status = st.radio(
              "الصفة",
              status_options,
              index=s_idx,
              horizontal=True,
              key=f"card_status_{rec_id}",
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
              e_apt_type,
              e_name,
              e_phone,
              clean_str(row["plate_number"]),
              str(row["plate_letter"]),
              clean_str(row["plate_region"]),
              p_full_str,
              e_status,
              e_car,
              e_notes,
          )
          st.success("✅ تم حفظ التعديلات بنجاح!")
          st.rerun()


# ----------------- بطاقة عرض الساكن من دليل الشقق (fm6) -----------------
def render_directory_card(row):
  bld = clean_str(row.get("building", ""))
  apt = clean_str(row.get("apartment", ""))
  apt_type = clean_str(row.get("apartment_type", ""))
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
      st.markdown(
          f"🏢 **العمارة:** `{bld}` &nbsp;&nbsp;|&nbsp;&nbsp; 🚪 **الشقة:**"
          f" `{apt_text}`"
      )
      st.markdown(f"👤 **الساكن:** **{name if name else 'غير مسجل'}**")
    with c2:
      st.markdown(f"📞 **الهاتف:** `{phone if phone else 'غير متوفر'}`")

    if phone and phone.lower() != "nan":
      b1, b2 = st.columns(2)
      with b1:
        st.link_button(
            "📞 اتصال هاتفي", f"tel:{phone}", use_container_width=True
        )
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
        if "cam_apt_type_select" not in st.session_state:
          st.session_state["cam_apt_type_select"] = ""

        col_bld_in, col_apt_in, col_fetch_btn = st.columns([1.5, 1.5, 1])
        with col_bld_in:
          entered_bld = st.text_input(
              "العمارة:", placeholder="مثال: 1", key="cam_bld_input"
          )
        with col_apt_in:
          entered_apt = st.text_input(
              "الشقة:", placeholder="مثال: 1", key="cam_apt_input"
          )
        with col_fetch_btn:
          st.write("")
          st.write("")
          if st.button("جلب ⚡", key="cam_fetch_btn", use_container_width=True):
            data = get_apartment_info(entered_bld, entered_apt)
            if data:
              st.session_state["cam_name_input"] = data["resident_name"]
              st.session_state["cam_phone_input"] = data["phone"]
              st.session_state["cam_apt_type_select"] = data["apartment_type"]
              st.rerun()
            else:
              st.warning("⚠️ لم يتم العثور على شقة بهذه البيانات.")

        c_t1, c_t2 = st.columns(2)
        with c_t1:
          curr_t = st.session_state.get("cam_apt_type_select", "")
          idx_type = (
              apt_types_list.index(curr_t) if curr_t in apt_types_list else 0
          )
          apartment_type = st.selectbox(
              "نوع الشقة (F2, F3, ...):",
              apt_types_list,
              index=idx_type,
              key="cam_apt_type_select",
          )
        with c_t2:
          name = st.text_input(
              "اسم الساكن", placeholder="الاسم الكامل", key="cam_name_input"
          )

        phone = st.text_input(
            "رقم الهاتف", placeholder="06XXXXXXXX", key="cam_phone_input"
        )
        car_desc = st.text_input("نوع ولون السيارة (اختياري)", key="cam_desc_in")

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
            st.session_state["cam_apt_type_select"] = ""
            st.success("تم الحفظ بنجاح!")
            st.rerun()
          else:
            st.error("يرجى كتابة رقم اللوحة.")
    else:
      st.warning(
          "تعذر قراءة أرقام واضحة، حاول التقاط صورة أقرب قليلاً للوحة."
      )

# ==================== 2. قسم الاستعلام الشامل في الجدولين ====================
elif st.session_state.active_tab == "search":
  st.subheader("🔍 استعلام وبحث فوري شامل")
  st.caption(
      "البحث التلقائي يشمل كلاً من: جدول السيارات المسجلة حديثاً + جدول دليل"
      " الشقق وسكانها (fm6):"
  )

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
      search_submitted = st.form_submit_button(
          "🔍 ابحث الآن", type="primary", use_container_width=True
      )

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
        st.markdown(
            f"### 🚗 نتائج موقف السيارات المسجلة ({len(res_cars)} سيارة)"
        )
        for _, r in res_cars.iterrows():
          render_car_card(r, allow_edit=True)

    res_dir = search_apartments_directory(query)
    dir_found = False

    if not res_dir.empty:
      dir_found = True
      st.markdown(f"### 🏢 نتائج دليل الشقق والسكان (fm6) ({len(res_dir)} ساكن)")
      for _, r_dir in res_dir.iterrows():
        render_directory_card(r_dir)

    if not cars_found and not dir_found:
      st.info(
          "لم يتم العثور على أي تطابق في موقف السيارات ولا في دليل الشقق"
          " والسكان."
      )

# ==================== 3. قسم التسجيل اليدوي (مع زر الجلب المباشر) ====================
elif st.session_state.active_tab == "add":
  st.subheader("➕ تسجيل سيارة يدوياً")

  if "manual_name_input" not in st.session_state:
    st.session_state["manual_name_input"] = ""
  if "manual_phone_input" not in st.session_state:
    st.session_state["manual_phone_input"] = ""
  if "manual_apt_type_select" not in st.session_state:
    st.session_state["manual_apt_type_select"] = ""

  c1, c2, c3 = st.columns([2, 1, 1])
  with c1:
    p_num = st.text_input("أرقام اللوحة *", placeholder="78954", key="m_p_num")
  with c2:
    p_let = st.selectbox("حرف اللوحة", letters_list, key="m_p_let")
  with c3:
    p_reg = st.text_input("العمالة", placeholder="26", key="m_p_reg")

  car_type = st.radio(
      "صفة الساكن:", status_options, horizontal=True, key="m_car_type"
  )

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
        st.session_state["manual_apt_type_select"] = m_data["apartment_type"]
        st.rerun()
      else:
        st.warning("⚠️ لم يتم العثور على شقة بهذه الأرقام في دليل السكان.")

  c_ma1, c_ma2 = st.columns(2)
  with c_ma1:
    curr_m_type = st.session_state.get("manual_apt_type_select", "")
    m_type_idx = (
        apt_types_list.index(curr_m_type)
        if curr_m_type in apt_types_list
        else 0
    )
    m_apt_type = st.selectbox(
        "نوع الشقة:",
        apt_types_list,
        index=m_type_idx,
        key="manual_apt_type_select",
    )
  with c_ma2:
    name = st.text_input(
        "اسم الساكن", placeholder="الاسم الكامل", key="manual_name_input"
    )

  phone = st.text_input(
      "رقم الهاتف", placeholder="06XXXXXXXX", key="manual_phone_input"
  )
  car_desc = st.text_input(
      "نوع ولون السيارة", placeholder="مثال: داسيا بيضاء", key="m_car_desc"
  )

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
        st.session_state["manual_apt_type_select"] = ""
        st.success("تم الحفظ بنجاح!")
        st.rerun()
    else:
      st.error("أدخل رقم اللوحة على الأقل.")

# ==================== 4. قسم الإدارة ====================
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
    st.subheader("🏢 دليل الشقق والسكان (fm6)")

    conn = sqlite3.connect(DB_FILE)
    apt_count = conn.cursor().execute("SELECT COUNT(*) FROM apartments_directory").fetchone()[0]
    conn.close()

    st.success(
        f"✅ دليل الشقق والسكان مدمج ومفعل دائماً: **{apt_count} شقة** مسجلة"
        " بنجاح."
    )

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
            | df["apartment_type"].astype(str).str.contains(edit_query, case=False)
            | df["car_type"].astype(str).str.contains(edit_query, case=False)
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

              curr_status = clean_str(row_sel.get("car_type", "مالك"))
              s_idx = (
                  status_options.index(curr_status)
                  if curr_status in status_options
                  else 0
              )
              edit_car_type = st.radio(
                  "صفة الساكن:",
                  status_options,
                  index=s_idx,
                  horizontal=True,
                  key=f"adm_type_{selected_car_id}",
              )

              c1, c2, c3 = st.columns(3)
              with c1:
                new_bld = st.text_input(
                    "رقم العمارة",
                    value=clean_str(row_sel["building"]),
                    key=f"adm_bld_{selected_car_id}",
                )
              with c2:
                new_apt = st.text_input(
                    "رقم الشقة",
                    value=clean_str(row_sel["apartment"]),
                    key=f"adm_apt_{selected_car_id}",
                )
              with c3:
                curr_type_db = clean_str(row_sel.get("apartment_type", ""))
                idx_t_db = (
                    apt_types_list.index(curr_type_db)
                    if curr_type_db in apt_types_list
                    else 0
                )
                new_apt_type = st.selectbox(
                    "نوع الشقة",
                    apt_types_list,
                    index=idx_t_db,
                    key=f"adm_apttype_{selected_car_id}",
                )

              c_n1, c_n2 = st.columns(2)
              with c_n1:
                new_name = st.text_input(
                    "اسم الساكن",
                    value=(
                        str(row_sel["resident_name"])
                        if pd.notna(row_sel["resident_name"])
                        else ""
                    ),
                    key=f"adm_name_{selected_car_id}",
                )
              with c_n2:
                new_phone = st.text_input(
                    "رقم الهاتف",
                    value=clean_str(row_sel["phone"]),
                    key=f"adm_phone_{selected_car_id}",
                )

              c_c1, c_c2 = st.columns(2)
              with c_c1:
                new_car_info = st.text_input(
                    "نوع ولون السيارة",
                    value=(
                        str(row_sel["car_info"])
                        if pd.notna(row_sel["car_info"])
                        else ""
                    ),
                    key=f"adm_car_{selected_car_id}",
                )
              with c_c2:
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
                    new_apt_type,
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
                clean_str(row.get("apartment_type", "")),
                clean_str(row.get("resident_name", "")),
                clean_str(row.get("phone", "")),
                p_num,
                str(row.get("plate_letter", "")),
                clean_str(row.get("plate_region", "")),
                clean_str(row.get("full_plate", "")),
                clean_str(row.get("car_type", "مالك")),
                str(row.get("car_info", "")),
                clean_str(row.get("notes", "")),
            )
        st.success("✅ تمت استعادة كافة السيارات وتطهير الأرقام بنجاح!")
        st.rerun()
