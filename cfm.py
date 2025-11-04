import streamlit as st
import pandas as pd
import os
from datetime import datetime, time, timedelta
import io
import matplotlib.pyplot as plt
from PIL import Image
import time as pytime  # for sleep in clock

# ----------------- helper: IST now -----------------
def now_ist():
    """Return current datetime in IST (UTC+5:30)."""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ---------------- page config ----------------
st.set_page_config(page_title="Hostel Meal Booking", layout="wide")

# ---------------- constants ----------------
DATA_DIR = "."
USERS_FILE = os.path.join(DATA_DIR, "users.xlsx")
BOOKING_FILE = os.path.join(DATA_DIR, "daily_meal_booking.xlsx")
MENU_IMG_DIR = os.path.join(DATA_DIR, "menu_images")

MEALS = ["breakfast", "lunch", "dinner"]

# TIME WINDOWS (IST). Booking is for TOMORROW.
TIME_WINDOWS = {
    "breakfast": {
        "book_start":   time(10, 0),   # 10:00 IST
        "book_end":     time(11, 0),   # 11:00 IST
        "cancel_start": time(10, 30),  # 10:30 IST
        "cancel_end":   time(11, 30),  # 11:30 IST
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

# ---------------- helpers ----------------
def ensure_files_exist():
    os.makedirs(MENU_IMG_DIR, exist_ok=True)
    # booking file
    if not os.path.exists(BOOKING_FILE):
        df = pd.DataFrame(columns=["date", "student_id", "name", "meal", "status", "timestamp"])
        df.to_excel(BOOKING_FILE, index=False)
    # users file (create sample if missing)
    if not os.path.exists(USERS_FILE):
        rows = []
        for i in range(1, 101):
            rows.append({"student_id": f"H{i:03}", "name": f"Student {i}", "password": f"P{i:03}"})
        rows.append({"student_id": "ADMIN", "name": "Admin", "password": "admin123"})
        pd.DataFrame(rows).to_excel(USERS_FILE, index=False)

def load_users():
    return pd.read_excel(USERS_FILE, dtype=str)

def load_bookings():
    return pd.read_excel(BOOKING_FILE, dtype=str)

def append_booking_row(date_str, student_id, name, meal, status):
    timestamp = now_ist().strftime("%Y-%m-%d %H:%M:%S")
    row = {"date": date_str, "student_id": student_id, "name": name, "meal": meal, "status": status, "timestamp": timestamp}
    df = load_bookings()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_excel(BOOKING_FILE, index=False)

def get_tomorrow_date():
    return (now_ist() + timedelta(days=1)).date()

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

def user_has_active_booking(date_str, student_id, meal):
    df = load_bookings()
    sel = df[(df["date"] == date_str) & (df["student_id"] == student_id) & (df["meal"] == meal)]
    if sel.empty:
        return False, None
    last_status = sel.iloc[-1]["status"]
    return (str(last_status).lower() == "booked"), last_status

def save_menu_image(uploaded_file, date_str):
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

# ---------------- session state / routing ----------------
if "page" not in st.session_state:
    st.session_state.page = "login"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "student_id" not in st.session_state:
    st.session_state.student_id = ""
if "role" not in st.session_state:
    st.session_state.role = None
if "clock_running" not in st.session_state:
    st.session_state.clock_running = True

def goto(page):
    st.session_state.page = page
    st.rerun()

# ---------------- UI: Login ----------------
def login_page():
    st.title("Hostel Meal Booking - Login")
    col1, col2 = st.columns([2,1])
    with col1:
        student_id = st.text_input("Student ID")
        password = st.text_input("Password", type="password")
    with col2:
        st.write("")
        login_btn = st.button("Login")

    if login_btn:
        match = users_df[(users_df["student_id"] == str(student_id)) & (users_df["password"] == str(password))]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.student_id = str(student_id)
            if str(student_id).upper() == "ADMIN":
                st.session_state.role = "admin"
                goto("admin")
            else:
                st.session_state.role = "user"
                goto("user")
        else:
            st.error("Invalid ID or Password ❌")

    st.info("Demo users created if missing. Admin: ADMIN / admin123")

# ---------------- UI: Admin ----------------
def admin_page():
    st.title("Admin Dashboard")
    # SHOW LIVE IST CLOCK on admin too
    clock_col = st.columns([1,3])[0]
    with clock_col:
        show_clock()

    st.write("Welcome Admin")

    # Upload menu image for TOMORROW
    tomorrow = get_tomorrow_date().isoformat()
    st.subheader(f"Upload Menu Image for {tomorrow}")
    uploaded = st.file_uploader("Menu image (png/jpg)", type=["png","jpg","jpeg"], key="menu_upload_admin")
    if uploaded:
        saved = save_menu_image(uploaded, tomorrow)
        st.success(f"Menu saved: {saved}")
        st.image(saved, caption=f"Menu for {tomorrow}", use_column_width=True)

    st.markdown("---")
    st.subheader("View / Export Bookings")
    date_sel = st.date_input("Select date to view", value=get_tomorrow_date())
    date_str = date_sel.isoformat()

    df = load_bookings()
    df_date = df[df["date"] == date_str]
    st.write(f"Total records for {date_str}: {len(df_date)}")
    st.dataframe(df_date)

    if not df_date.empty:
        counts = df_date[df_date["status"].str.lower() == "booked"].groupby("meal").size()
        fig, ax = plt.subplots()
        counts.plot.pie(autopct="%1.0f%%", ax=ax)
        ax.set_ylabel("")
        st.pyplot(fig)

    # Download buttons
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

# ---------------- Live Clock helper ----------------
def show_clock():
    """Displays a live IST clock. Use st.session_state.clock_running to control."""
    placeholder = st.empty()
    # control buttons
    col_a, col_b = st.columns([1,1])
    with col_a:
        if st.button("Stop Clock", key="stop_clock"):
            st.session_state.clock_running = False
    with col_b:
        if st.button("Start Clock", key="start_clock"):
            st.session_state.clock_running = True
            st.rerun()

    # show always current IST time
    now = now_ist()
    placeholder.markdown(f"**IST Time:** `{now.strftime('%Y-%m-%d %H:%M:%S')}`")

    # if running, schedule a rerun after 1 second
    if st.session_state.clock_running:
        pytime.sleep(1)
        st.rerun()

# ---------------- UI: User ----------------
def user_page():
    st.title("Meal Booking Page")
    # show live clock for user as well
    show_clock()

    uid = st.session_state.student_id
    user_row = users_df[users_df["student_id"] == uid]
    name = user_row.iloc[0]["name"] if not user_row.empty else ""

    st.write(f"Welcome, **{name}** ({uid})")
    st.write(f"Booking is always for **{get_tomorrow_date().isoformat()}**")

    # show menu image for tomorrow if present
    menu_img = get_menu_image_path(get_tomorrow_date().isoformat())
    if menu_img:
        st.image(menu_img, caption=f"Menu for {get_tomorrow_date().isoformat()}", use_column_width=True)

    st.markdown("---")
    st.subheader("Book / Cancel (buttons appear only in allowed windows)")

    for meal in MEALS:
        st.markdown(f"### {meal.capitalize()}")
        bs = can_book(meal)
        cs = can_cancel(meal)

        booked, last_status = user_has_active_booking(get_tomorrow_date().isoformat(), uid, meal)

        cols = st.columns([1,1,1])
        with cols[0]:
            if bs:
                if not booked:
                    if st.button(f"Book {meal.capitalize()}", key=f"book_{meal}_{uid}"):
                        append_booking_row(get_tomorrow_date().isoformat(), uid, name, meal, "booked")
                        st.success(f"{meal.capitalize()} booked for {get_tomorrow_date().isoformat()}")
                        st.rerun()
                else:
                    st.info(f"Already booked ({last_status})")
            else:
                st.write("Booking not open")

        with cols[1]:
            if cs:
                if booked:
                    if st.button(f"Cancel {meal.capitalize()}", key=f"cancel_{meal}_{uid}"):
                        append_booking_row(get_tomorrow_date().isoformat(), uid, name, meal, "cancelled")
                        st.success(f"{meal.capitalize()} cancelled for {get_tomorrow_date().isoformat()}")
                        st.rerun()
                else:
                    st.write("No active booking to cancel")
            else:
                st.write("Cancel not open")

        with cols[2]:
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
        st.rerun()
elif st.session_state.page == "user":
    if st.session_state.logged_in and st.session_state.role == "user":
        user_page()
    else:
        st.warning("Please login")
        st.session_state.page = "login"
        st.rerun()
