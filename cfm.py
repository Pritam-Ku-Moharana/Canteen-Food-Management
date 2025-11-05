# app.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime, date, time, timedelta
import io
import matplotlib.pyplot as plt
from PIL import Image

# ---------------- UI cosmetics ----------------
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}      /* hides hamburger menu */
    footer {visibility: hidden;}        /* hides "Made with Streamlit" footer */
    header {visibility: hidden;}        /* hides top header */
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ---------------- helper: IST now -----------------
def now_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ---------------- page config ----------------
st.set_page_config(page_title="Hostel Meal Booking", layout="wide")

# ---------------- constants / files ----------------
DATA_DIR = "."
USERS_FILE = os.path.join(DATA_DIR, "users.xlsx")
BOOKING_FILE = os.path.join(DATA_DIR, "daily_meal_booking.xlsx")
MENU_IMG_DIR = os.path.join(DATA_DIR, "menu_images")

MEALS = ["breakfast", "lunch", "dinner"]

# TIME WINDOWS (IST). These windows control when Book/Cancel buttons appear.
TIME_WINDOWS = {
    "breakfast": {
        "book_start":   time(9, 0),
        "book_end":     time(10, 0),
        "cancel_start": time(9, 30),
        "cancel_end":   time(10, 30),
    },
    "lunch": {
        "book_start": time(7, 0),
        "book_end":   time(8, 0),
        "cancel_start": time(8, 0),
        "cancel_end":   time(9, 0),
    },
    "dinner": {
        "book_start": time(13, 0),
        "book_end":   time(15, 0),
        "cancel_start": time(15, 0),
        "cancel_end":   time(16, 30),
    }
}

# FINAL expected columns (new schema)
EXPECTED_BOOKING_COLS = ["booking_date", "meal_date", "student_id", "meal", "status", "timestamp"]

# ---------------- helpers / IO ----------------
def ensure_files_exist():
    os.makedirs(MENU_IMG_DIR, exist_ok=True)

    # ensure users.xlsx exists (do not overwrite if present)
    if not os.path.exists(USERS_FILE):
        rows = []
        for i in range(1, 101):
            rows.append({"student_id": f"H{i:03}", "name": f"Student {i}", "password": f"P{i:03}"})
        rows.append({"student_id": "ADMIN", "name": "Admin", "password": "admin123"})
        pd.DataFrame(rows).to_excel(USERS_FILE, index=False)

    # ensure booking file exists with new header (do not overwrite if present)
    if not os.path.exists(BOOKING_FILE):
        df = pd.DataFrame(columns=EXPECTED_BOOKING_COLS)
        df.to_excel(BOOKING_FILE, index=False)

def normalize_and_load_bookings():
    """
    Load booking excel robustly and migrate old schema if necessary.

    - Supports old file format where column name was 'date' (booking date).
      We treat old 'date' as booking_date (per your confirmation).
      We then create meal_date = booking_date + 1 day.
    - Ensures both booking_date and meal_date are ISO strings YYYY-MM-DD.
    - Returns dataframe with EXPECTED_BOOKING_COLS (strings).
    """
    if not os.path.exists(BOOKING_FILE):
        df = pd.DataFrame(columns=EXPECTED_BOOKING_COLS)
        df.to_excel(BOOKING_FILE, index=False)
        return df

    # Try reading file
    try:
        df = pd.read_excel(BOOKING_FILE, dtype=str)
    except Exception:
        # If reading fails, return empty normalized df
        return pd.DataFrame(columns=EXPECTED_BOOKING_COLS)

    # If old schema: single column "date" exists but "booking_date" does not
    if "date" in df.columns and "booking_date" not in df.columns:
        # treat old 'date' as booking_date
        df = df.rename(columns={"date": "booking_date"})
        # create meal_date as booking_date + 1 day (handle parsing)
        df["booking_date"] = pd.to_datetime(df["booking_date"], errors="coerce")
        # If there are any NaT, keep as NaT; next lines will coerce to string 'NaT' -> handle later
        df["meal_date"] = (df["booking_date"] + pd.Timedelta(days=1))
        # keep other columns if present, else create
        if "student_id" not in df.columns:
            df["student_id"] = ""
        if "meal" not in df.columns:
            df["meal"] = ""
        if "status" not in df.columns:
            df["status"] = ""
        if "timestamp" not in df.columns:
            df["timestamp"] = ""
        # ensure order and columns
        df = df[["booking_date", "meal_date", "student_id", "meal", "status", "timestamp"]]

    # If already in new-ish schema but maybe with different names, attempt to standardize
    if "booking_date" in df.columns:
        # Normalize booking_date and meal_date to ISO strings
        df["booking_date"] = pd.to_datetime(df["booking_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        # If meal_date exists, normalize; if not, create meal_date = booking_date + 1
        if "meal_date" in df.columns:
            df["meal_date"] = pd.to_datetime(df["meal_date"], errors="coerce").dt.strftime("%Y-%m-%d")
            # For rows where meal_date is NaT, attempt to set from booking_date
            mask_meal_na = df["meal_date"].isnull() | df["meal_date"].isin(["NaT", "None", "nan"])
            if mask_meal_na.any():
                # convert booking_date to datetime then +1
                temp = pd.to_datetime(df.loc[mask_meal_na, "booking_date"], errors="coerce") + pd.Timedelta(days=1)
                df.loc[mask_meal_na, "meal_date"] = temp.dt.strftime("%Y-%m-%d")
        else:
            # create meal_date as booking_date + 1 day
            temp = pd.to_datetime(df["booking_date"], errors="coerce") + pd.Timedelta(days=1)
            df["meal_date"] = temp.dt.strftime("%Y-%m-%d")
    else:
        # If neither 'date' nor 'booking_date' exist, try headerless load below
        pass

    # Final enforcement: ensure all expected columns exist
    for col in EXPECTED_BOOKING_COLS:
        if col not in df.columns:
            df[col] = ""

    # Keep only expected columns and ensure string types
    df = df[EXPECTED_BOOKING_COLS].astype(str).fillna("")

    # Save normalized back to excel (this will upgrade old files automatically)
    try:
        df.to_excel(BOOKING_FILE, index=False)
    except Exception:
        # don't crash if save fails (permissions etc)
        pass

    return df

def load_users():
    if not os.path.exists(USERS_FILE):
        ensure_files_exist()
    try:
        return pd.read_excel(USERS_FILE, dtype=str).fillna("")
    except Exception:
        ensure_files_exist()
        return pd.read_excel(USERS_FILE, dtype=str).fillna("")

def append_booking_row(booking_date_obj, student_id, name, meal, status):
    """
    booking_date_obj: a date or date-like (we will treat as booking_date, not meal_date)
    We store:
      - booking_date = ISO of booking_date_obj (YYYY-MM-DD)
      - meal_date = booking_date + 1 day (ISO)
    """
    # make booking_date and meal_date ISO strings
    booking_dt = pd.to_datetime(booking_date_obj).date()
    meal_dt = booking_dt + timedelta(days=1)

    booking_iso = booking_dt.strftime("%Y-%m-%d")
    meal_iso = meal_dt.strftime("%Y-%m-%d")
    ts = now_ist().strftime("%Y-%m-%d %H:%M:%S")

    row = {
        "booking_date": booking_iso,
        "meal_date": meal_iso,
        "student_id": str(student_id),
        "meal": str(meal),
        "status": str(status),
        "timestamp": ts
    }

    df = normalize_and_load_bookings()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    # enforce proper order & types
    df = df[EXPECTED_BOOKING_COLS].astype(str).fillna("")
    # write back
    df.to_excel(BOOKING_FILE, index=False)

def get_booking_file_dates_sample():
    df = normalize_and_load_bookings()
    return sorted(list(set(df["booking_date"].tolist())))

# ---------------- small helpers ----------------
def get_today_booking_date_str():
    # booking_date (the date the student pressed booking) → use IST date
    return now_ist().date().strftime("%Y-%m-%d")

def get_tomorrow_meal_date_str():
    return (now_ist().date() + timedelta(days=1)).strftime("%Y-%m-%d")

def in_time_window(window_start: time, window_end: time, now_time: time):
    return (now_time >= window_start) and (now_time <= window_end)

def can_book(meal):
    now = now_ist().time()
    w = TIME_WINDOWS[meal]
    return in_time_window(w["book_start"], w["book_end"], now)

def can_cancel(meal):
    now = now_ist().time()
    w = TIME_WINDOWS[meal]
    return in_time_window(w["cancel_start"], w["cancel_end"], now)

def user_has_active_booking(booking_date_str, student_id, meal):
    """
    Check if student already has active booking for this booking_date and meal.
    booking_date_str is ISO string YYYY-MM-DD of booking date (when they pressed Book).
    """
    df = normalize_and_load_bookings()
    if df.empty:
        return False, None
    sel = df[(df["booking_date"] == str(booking_date_str)) &
             (df["student_id"] == str(student_id)) &
             (df["meal"] == str(meal))]
    if sel.empty:
        return False, None
    last_status = sel.iloc[-1]["status"]
    return (str(last_status).lower() == "booked"), last_status

def save_menu_image(uploaded_file, date_str):
    os.makedirs(MENU_IMG_DIR, exist_ok=True)
    filename = os.path.join(MENU_IMG_DIR, f"menu_{date_str}.png")
    image = Image.open(uploaded_file)
    image.save(filename)
    return filename

def get_menu_image_path(date_str):
    p = os.path.join(MENU_IMG_DIR, f"menu_{date_str}.png")
    return p if os.path.exists(p) else None

# ---------------- initialization ----------------
ensure_files_exist()
users_df = load_users()

# ---------------- session state ----------------
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
    st.experimental_rerun()

# ---------------- UI: Login ----------------
def login_page():
    st.title("Hostel Meal Booking - Login")
    col1, col2 = st.columns([2,1])
    with col1:
        sid = st.text_input("Student ID")
        pwd = st.text_input("Password", type="password")
    with col2:
        st.write("")
        btn = st.button("Login")
    if btn:
        match = users_df[(users_df["student_id"] == str(sid)) & (users_df["password"] == str(pwd))]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.student_id = str(sid)
            if str(sid).upper() == "ADMIN":
                st.session_state.role = "admin"
                goto("admin")
            else:
                st.session_state.role = "user"
                goto("user")
        else:
            st.error("Invalid ID or Password ❌")
    st.info(
        "Enter your username and password to log in.\n\n"
        "If you are a new user, contact the administrator to create your account."
    )

# ---------------- UI: Admin ----------------
def admin_page():
    st.title("Admin Dashboard")
    st.write("Welcome Admin")

    # show menu image upload for meal_date (tomorrow by default)
    tomorrow = (now_ist().date() + timedelta(days=1)).isoformat()
    st.subheader(f"Upload menu photo for meal date {tomorrow}")
    uploaded = st.file_uploader("Menu image (png/jpg)", type=["png","jpg","jpeg"], key="menu_admin")
    if uploaded:
        saved = save_menu_image(uploaded, tomorrow)
        st.success(f"Saved: {saved}")
        st.image(saved, caption=f"Menu {tomorrow}", use_column_width=True)

    st.markdown("---")
    st.subheader("View / Export Bookings (filter by booking date)")
    # Admin filters by booking_date (default = today in IST)
    date_sel = st.date_input("Booking date", value=now_ist().date())
    date_str = pd.to_datetime(date_sel).strftime("%Y-%m-%d")

    df = normalize_and_load_bookings()
    # ensure normalized
    df["booking_date"] = pd.to_datetime(df["booking_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["meal_date"] = pd.to_datetime(df["meal_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    df_date = df[df["booking_date"] == date_str]

    st.write(f"Total rows for booking date {date_str}: {len(df_date)}")
    st.dataframe(df_date)

    if not df_date.empty:
        counts = df_date[df_date["status"].str.lower() == "booked"].groupby("meal").size()
        if not counts.empty:
            fig, ax = plt.subplots()
            counts.plot.pie(autopct="%1.0f%%", ax=ax)
            ax.set_ylabel("")
            st.pyplot(fig)

    csv_bytes = df_date.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv_bytes, file_name=f"bookings_{date_str}.csv", mime="text/csv")
    towrite = io.BytesIO()
    df_date.to_excel(towrite, index=False, engine="openpyxl")
    st.download_button("Download Excel", data=towrite.getvalue(), file_name=f"bookings_{date_str}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("---")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.student_id = ""
        st.session_state.role = None
        goto("login")

# ---------------- UI: User ----------------
def user_page():
    st.title("Meal Booking Page")

    # show IST time once
    st.info("Current IST time: " + now_ist().strftime("%Y-%m-%d %H:%M:%S"))

    uid = st.session_state.student_id
    user_row = users_df[users_df["student_id"] == uid]
    name = user_row.iloc[0]["name"] if not user_row.empty else ""

    st.write(f"Welcome, **{name}** ({uid})")

    # booking_date = TODAY (IST), meal_date = tomorrow
    booking_date = now_ist().date().strftime("%Y-%m-%d")
    meal_date = (now_ist().date() + timedelta(days=1)).strftime("%Y-%m-%d")
    st.write(f"Booking date (when you press Book): **{booking_date}**")
    st.write(f"This booking is for meal date: **{meal_date}**")

    menu_img = get_menu_image_path(meal_date)
    if menu_img:
        st.image(menu_img, caption=f"Menu for {meal_date}", use_column_width=True)

    st.markdown("---")
    st.subheader("Book / Cancel (buttons appear only in allowed windows)")

    for meal in MEALS:
        st.markdown(f"### {meal.capitalize()}")
        bs = can_book(meal)
        cs = can_cancel(meal)

        booked, last_status = user_has_active_booking(booking_date, uid, meal)

        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            if bs:
                if not booked:
                    if st.button(f"Book {meal.capitalize()}", key=f"book_{meal}_{uid}"):
                        append_booking_row(booking_date, uid, name, meal, "booked")
                        st.success(f"{meal.capitalize()} booked (booking_date={booking_date}) for meal_date={meal_date}")
                        st.experimental_rerun()
                else:
                    st.info(f"Already booked ({last_status})")
            else:
                st.write("Booking not open")
        with c2:
            if cs:
                if booked:
                    if st.button(f"Cancel {meal.capitalize()}", key=f"cancel_{meal}_{uid}"):
                        append_booking_row(booking_date, uid, name, meal, "cancelled")
                        st.success(f"{meal.capitalize()} cancelled (booking_date={booking_date}) for meal_date={meal_date}")
                        st.experimental_rerun()
                else:
                    st.write("No active booking")
            else:
                st.write("Cancel not open")
        with c3:
            if last_status:
                st.write(f"Last status: **{last_status}**")
            else:
                st.write("No record yet")
        st.markdown("---")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.student_id = ""
        st.session_state.role = None
        goto("login")

# ---------------- routing ----------------
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "admin":
    if st.session_state.logged_in and st.session_state.role == "admin":
        admin_page()
    else:
        st.warning("Please login as admin")
        st.session_state.page = "login"
        st.experimental_rerun()
elif st.session_state.page == "user":
    if st.session_state.logged_in and st.session_state.role == "user":
        user_page()
    else:
        st.warning("Please login")
        st.session_state.page = "login"
        st.experimental_rerun()
