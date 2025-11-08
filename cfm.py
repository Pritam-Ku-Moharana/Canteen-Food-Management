import streamlit as st
import pandas as pd
import os
from datetime import datetime, date, time, timedelta
import io
import matplotlib.pyplot as plt
from PIL import Image

# ---------------- UI cosmetics ----------------
st.set_page_config(page_title="Hostel Meal Booking")

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ---------------- helper: IST now -----------------
def now_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ---------------- constants / files ----------------
DATA_DIR = "."
USERS_FILE = os.path.join(DATA_DIR, "users.xlsx")
BOOKING_FILE = os.path.join(DATA_DIR, "daily_meal_booking.xlsx")
MENU_IMG_DIR = os.path.join(DATA_DIR, "menu_images")

MEALS = ["breakfast", "lunch", "dinner"]

# TIME WINDOWS (IST)
TIME_WINDOWS = {
    "breakfast": {
        "book_start": time(9, 0),
        "book_end": time(10, 0),
        "cancel_start": time(9, 30),
        "cancel_end": time(10, 30),
    },
    "lunch": {
        "book_start": time(7, 0),
        "book_end": time(8, 0),
        "cancel_start": time(8, 0),
        "cancel_end": time(9, 0),
    },
    "dinner": {
        "book_start": time(13, 0),
        "book_end": time(15, 0),
        "cancel_start": time(15, 0),
        "cancel_end": time(16, 30),
    },
}

EXPECTED_BOOKING_COLS = [
    "booking_date",
    "meal_date",
    "student_id",
    "meal",
    "status",
    "timestamp",
]

# ---------------- file setup ----------------
def ensure_files_exist():
    os.makedirs(MENU_IMG_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        rows = [{"student_id": f"H{i:03}", "name": f"Student {i}", "password": f"P{i:03}"} for i in range(1, 101)]
        rows.append({"student_id": "ADMIN", "name": "Admin", "password": "admin123"})
        pd.DataFrame(rows).to_excel(USERS_FILE, index=False)
    if not os.path.exists(BOOKING_FILE):
        pd.DataFrame(columns=EXPECTED_BOOKING_COLS).to_excel(BOOKING_FILE, index=False)

# normalize old schema
def normalize_and_load_bookings():
    ensure_files_exist()
    try:
        df = pd.read_excel(BOOKING_FILE, dtype=str)
    except Exception:
        return pd.DataFrame(columns=EXPECTED_BOOKING_COLS)

    # migrate old "date" → "booking_date"
    if "date" in df.columns and "booking_date" not in df.columns:
        df.rename(columns={"date": "booking_date"}, inplace=True)

    # ensure required columns exist
    for col in EXPECTED_BOOKING_COLS:
        if col not in df.columns:
            df[col] = ""

    # compute meal_date if missing
    df["booking_date"] = pd.to_datetime(df["booking_date"], errors="coerce")
    df["meal_date"] = pd.to_datetime(df["meal_date"], errors="coerce")

    missing_meal = df["meal_date"].isna()
    df.loc[missing_meal, "meal_date"] = df.loc[missing_meal, "booking_date"] + timedelta(days=1)

    # format ISO
    df["booking_date"] = df["booking_date"].dt.strftime("%Y-%m-%d")
    df["meal_date"] = df["meal_date"].dt.strftime("%Y-%m-%d")

    df = df[EXPECTED_BOOKING_COLS].astype(str).fillna("")
    try:
        df.to_excel(BOOKING_FILE, index=False)
    except Exception:
        pass
    return df

def load_users():
    ensure_files_exist()
    try:
        return pd.read_excel(USERS_FILE, dtype=str).fillna("")
    except Exception:
        ensure_files_exist()
        return pd.read_excel(USERS_FILE, dtype=str).fillna("")

def append_booking_row(booking_date_obj, student_id, name, meal, status):
    booking_dt = pd.to_datetime(booking_date_obj).date()
    meal_dt = booking_dt + timedelta(days=1)

    row = {
        "booking_date": booking_dt.strftime("%Y-%m-%d"),
        "meal_date": meal_dt.strftime("%Y-%m-%d"),
        "student_id": str(student_id),
        "meal": str(meal),
        "status": str(status),
        "timestamp": now_ist().strftime("%Y-%m-%d %H:%M:%S"),
    }

    df = normalize_and_load_bookings()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df = df[EXPECTED_BOOKING_COLS].astype(str)
    df.to_excel(BOOKING_FILE, index=False)

def save_menu_image(uploaded_file, date_str):
    os.makedirs(MENU_IMG_DIR, exist_ok=True)
    filename = os.path.join(MENU_IMG_DIR, f"menu_{date_str}.png")
    Image.open(uploaded_file).save(filename)
    return filename

def get_menu_image_path(date_str):
    p = os.path.join(MENU_IMG_DIR, f"menu_{date_str}.png")
    return p if os.path.exists(p) else None

# ---------------- state ----------------
ensure_files_exist()
users_df = load_users()

if "page" not in st.session_state:
    st.session_state.page = "login"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "student_id" not in st.session_state:
    st.session_state.student_id = ""
if "role" not in st.session_state:
    st.session_state.role = None

def goto(page):
    st.session_state.page = page
    st.rerun()

# ---------------- logic ----------------
def in_time_window(start, end, now_t):
    return start <= now_t <= end

def can_book(meal):
    now_t = now_ist().time()
    w = TIME_WINDOWS[meal]
    return in_time_window(w["book_start"], w["book_end"], now_t)

def can_cancel(meal):
    now_t = now_ist().time()
    w = TIME_WINDOWS[meal]
    return in_time_window(w["cancel_start"], w["cancel_end"], now_t)

def user_has_active_booking(booking_date, student_id, meal):
    df = normalize_and_load_bookings()
    if df.empty:
        return False, None
    sel = df[
        (df["booking_date"] == str(booking_date))
        & (df["student_id"] == str(student_id))
        & (df["meal"] == str(meal))
    ]
    if sel.empty:
        return False, None
    last_status = sel.iloc[-1]["status"].lower()
    return (last_status == "booked"), last_status

# ---------------- pages ----------------
def login_page():
    st.title("Hostel Meal Booking - Login")
    sid = st.text_input("Student ID")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        match = users_df[(users_df["student_id"] == sid) & (users_df["password"] == pwd)]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.student_id = sid
            st.session_state.role = "admin" if sid.upper() == "ADMIN" else "user"
            goto(st.session_state.role)
        else:
            st.error("Invalid ID or Password ❌")
    st.info("Enter your credentials. Contact Admin if you need help.")

def admin_page():
    st.title("Admin Dashboard")

    tomorrow = (now_ist().date() + timedelta(days=1)).strftime("%Y-%m-%d")
    st.subheader(f"Upload Menu Image for {tomorrow}")
    uploaded = st.file_uploader("Upload Menu (png/jpg)", type=["png", "jpg", "jpeg"])
    if uploaded:
        saved = save_menu_image(uploaded, tomorrow)
        st.success(f"Menu saved: {saved}")
        st.image(saved, caption=f"Menu {tomorrow}", use_column_width=True)

    st.markdown("---")
    st.subheader("View / Export Bookings by MEAL Date")
    
    date_sel = st.date_input("Select MEAL date", value=now_ist().date() + timedelta(days=1))
    date_str = pd.to_datetime(date_sel).strftime("%Y-%m-%d")
    
    df_date = df[df["meal_date"] == date_str]


    st.write(f"Total rows for booking date {date_str}: {len(df_date)}")
    st.dataframe(df_date)

    if not df_date.empty:
        counts = df_date[df_date["status"].str.lower() == "booked"].groupby("meal").size()
        if not counts.empty:
            fig, ax = plt.subplots()
            counts.plot.pie(autopct="%1.0f%%", ax=ax)
            ax.set_ylabel("")
            st.pyplot(fig)

        st.download_button(
            "Download CSV",
            data=df_date.to_csv(index=False).encode("utf-8"),
            file_name=f"bookings_{date_str}.csv",
            mime="text/csv",
        )
        towrite = io.BytesIO()
        df_date.to_excel(towrite, index=False, engine="openpyxl")
        st.download_button(
            "Download Excel",
            data=towrite.getvalue(),
            file_name=f"bookings_{date_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if st.button("Logout"):
        st.session_state.clear()
        goto("login")

def user_page():
    st.title("Meal Booking")
    st.info("Current IST time: " + now_ist().strftime("%Y-%m-%d %H:%M:%S"))

    uid = st.session_state.student_id
    user_row = users_df[users_df["student_id"] == uid]
    name = user_row.iloc[0]["name"] if not user_row.empty else uid

    st.write(f"Welcome, **{name}** ({uid})")

    booking_date = now_ist().date().strftime("%Y-%m-%d")
    meal_date = (now_ist().date() + timedelta(days=1)).strftime("%Y-%m-%d")

    st.write(f"Booking Date: **{booking_date}**")
    st.write(f"Meal Date: **{meal_date}**")

    menu_img = get_menu_image_path(meal_date)
    if menu_img:
        st.image(menu_img, caption=f"Menu for {meal_date}", use_column_width=True)

    st.markdown("---")
    st.subheader("Book / Cancel Meals")

    for meal in MEALS:
        st.markdown(f"### {meal.capitalize()}")
        can_b = can_book(meal)
        can_c = can_cancel(meal)
        booked, last_status = user_has_active_booking(booking_date, uid, meal)

        c1, c2, c3 = st.columns(3)
        with c1:
            if can_b:
                if not booked:
                    if st.button(f"Book {meal}", key=f"book_{meal}"):
                        append_booking_row(booking_date, uid, name, meal, "booked")
                        st.success(f"{meal.capitalize()} booked for {meal_date}")
                        st.rerun()
                else:
                    st.info("Already booked")
            else:
                st.write("Booking not open")

        with c2:
            if can_c:
                if booked:
                    if st.button(f"Cancel {meal}", key=f"cancel_{meal}"):
                        append_booking_row(booking_date, uid, name, meal, "cancelled")
                        st.success(f"{meal.capitalize()} cancelled for {meal_date}")
                        st.rerun()
                else:
                    st.write("No active booking")
            else:
                st.write("Cancel not open")

        with c3:
            st.write(f"Last status: **{last_status or 'None'}**")
        st.markdown("---")

    if st.button("Logout"):
        st.session_state.clear()
        goto("login")

# ---------------- routing ----------------
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "admin":
    if st.session_state.logged_in and st.session_state.role == "admin":
        admin_page()
    else:
        goto("login")
elif st.session_state.page == "user":
    if st.session_state.logged_in and st.session_state.role == "user":
        user_page()
    else:
        goto("login")


