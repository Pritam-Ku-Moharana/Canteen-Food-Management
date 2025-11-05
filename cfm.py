# app.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime, time, timedelta
import io
import matplotlib.pyplot as plt
from PIL import Image


# Hide Streamlit menu and footer
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
st.set_page_config(page_title="Hostel Meal Booking")

# ---------------- constants ----------------
DATA_DIR = "."
USERS_FILE = os.path.join(DATA_DIR, "users.xlsx")
BOOKING_FILE = os.path.join(DATA_DIR, "daily_meal_booking.xlsx")
MENU_IMG_DIR = os.path.join(DATA_DIR, "menu_images")

MEALS = ["breakfast", "lunch", "dinner"]

# TIME WINDOWS (IST). Booking is for TOMORROW.
TIME_WINDOWS = {
    "breakfast": {
        "book_start":   time(11, 0),
        "book_end":     time(12, 0),
        "cancel_start": time(11, 30),
        "cancel_end":   time(12, 30),
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

EXPECTED_BOOKING_COLS = ["date", "student_id", "meal", "status", "timestamp"]

# ---------------- helpers / IO ----------------
def ensure_files_exist():
    os.makedirs(MENU_IMG_DIR, exist_ok=True)

    # ensure users.xlsx exists (create sample if missing)
    if not os.path.exists(USERS_FILE):
        rows = []
        for i in range(1, 101):
            rows.append({"student_id": f"H{i:03}", "name": f"Student {i}", "password": f"P{i:03}"})
        rows.append({"student_id": "ADMIN", "name": "Admin", "password": "admin123"})
        pd.DataFrame(rows).to_excel(USERS_FILE, index=False)

    # ensure booking file exists; if missing create with header
    if not os.path.exists(BOOKING_FILE):
        df = pd.DataFrame(columns=EXPECTED_BOOKING_COLS)
        df.to_excel(BOOKING_FILE, index=False)

def normalize_and_load_bookings():
    """
    Load booking excel robustly.
    If file has expected header -> return as-is.
    If file has no header (or wrong header), treat file as headerless and assign expected columns,
    preserving rows, then overwrite file with normalized headers for future ease.
    """
    if not os.path.exists(BOOKING_FILE):
        df = pd.DataFrame(columns=EXPECTED_BOOKING_COLS)
        df.to_excel(BOOKING_FILE, index=False)
        return df

    # try reading with header=0 (default)
    try:
        df = pd.read_excel(BOOKING_FILE, dtype=str)
    except Exception:
        # fallback safe empty dataframe
        return pd.DataFrame(columns=EXPECTED_BOOKING_COLS)

    # if expected columns present -> return
    if all(col in df.columns for col in EXPECTED_BOOKING_COLS):
        # ensure dtype str and fill NaN with ""
        df = df.astype(str).fillna("")
        return df

    # If not, try read as headerless and assign columns (this preserves data rows)
    try:
        df_no_header = pd.read_excel(BOOKING_FILE, header=None, dtype=str)
    except Exception:
        return pd.DataFrame(columns=EXPECTED_BOOKING_COLS)

    # If df_no_header has fewer columns than expected, pad with empty values
    if df_no_header.shape[1] < len(EXPECTED_BOOKING_COLS):
        for _ in range(len(EXPECTED_BOOKING_COLS) - df_no_header.shape[1]):
            df_no_header[len(df_no_header.columns)] = ""

    df_no_header.columns = EXPECTED_BOOKING_COLS[: df_no_header.shape[1]]
    # If there are extra columns beyond expected, drop them
    df_no_header = df_no_header.loc[:, EXPECTED_BOOKING_COLS]
    # Save normalized file back (preserves rows, adds header)
    df_no_header.to_excel(BOOKING_FILE, index=False)
    return df_no_header

def load_users():
    if not os.path.exists(USERS_FILE):
        ensure_files_exist()
    try:
        return pd.read_excel(USERS_FILE, dtype=str).fillna("")
    except Exception:
        # if read error, create sample
        ensure_files_exist()
        return pd.read_excel(USERS_FILE, dtype=str).fillna("")

def append_booking_row(date_str, student_id, name, meal, status):
    ts = now_ist().strftime("%Y-%m-%d %H:%M:%S")
    row = {"date": date_str, "student_id": student_id, "meal": meal, "status": status, "timestamp": ts}
    df = normalize_and_load_bookings()
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
    df = normalize_and_load_bookings()
    if df.empty:
        return False, None
    sel = df[(df["date"] == str(date_str)) & (df["student_id"] == str(student_id)) & (df["meal"] == str(meal))]
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

# ---------------- session state / routing ----------------
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
    tomorrow = get_tomorrow_date().isoformat()

    st.subheader(f"Upload menu photo for {tomorrow}")
    uploaded = st.file_uploader("Menu image (png/jpg)", type=["png","jpg","jpeg"], key="menu_admin")
    if uploaded:
        saved = save_menu_image(uploaded, tomorrow)
        st.success(f"Saved: {saved}")
        st.image(saved, caption=f"Menu {tomorrow}", use_column_width=True)

    st.markdown("---")
    st.subheader("View / Export Bookings (select date)")
    date_sel = st.date_input("Date", value=get_tomorrow_date())
    date_str = date_sel.isoformat()

    df = normalize_and_load_bookings()
    df_date = df[df["date"] == date_str]
    st.write(f"Total rows for {date_str}: {len(df_date)}")
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
    tomorrow = get_tomorrow_date().isoformat()
    st.write(f"Booking is always for **{tomorrow}**")

    menu_img = get_menu_image_path(tomorrow)
    if menu_img:
        st.image(menu_img, caption=f"Menu for {tomorrow}", use_column_width=True)

    st.markdown("---")
    st.subheader("Book / Cancel (buttons appear only in allowed windows)")

    for meal in MEALS:
        st.markdown(f"### {meal.capitalize()}")
        bs = can_book(meal)
        cs = can_cancel(meal)

        booked, last_status = user_has_active_booking(tomorrow, uid, meal)

        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            if bs:
                if not booked:
                    if st.button(f"Book {meal.capitalize()}", key=f"book_{meal}_{uid}"):
                        append_booking_row(tomorrow, uid, name, meal, "booked")
                        st.success(f"{meal.capitalize()} booked for {tomorrow}")
                        st.rerun()
                else:
                    st.info(f"Already booked ({last_status})")
            else:
                st.write("Booking not open")
        with c2:
            if cs:
                if booked:
                    if st.button(f"Cancel {meal.capitalize()}", key=f"cancel_{meal}_{uid}"):
                        append_booking_row(tomorrow, uid, name, meal, "cancelled")
                        st.success(f"{meal.capitalize()} cancelled for {tomorrow}")
                        st.rerun()
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
        st.rerun()
elif st.session_state.page == "user":
    if st.session_state.logged_in and st.session_state.role == "user":
        user_page()
    else:
        st.warning("Please login")
        st.session_state.page = "login"
        st.rerun()




