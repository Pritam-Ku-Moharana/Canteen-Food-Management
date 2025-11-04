import streamlit as st
import pandas as pd
import os
from datetime import datetime, time, timedelta
import io
import matplotlib.pyplot as plt
from PIL import Image

# ---------------- page config ----------------
st.set_page_config(page_title="Hostel Meal Booking")

# ---------------- constants ----------------
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.xlsx")
BOOKING_FILE = os.path.join(DATA_DIR, "daily_meal_booking.xlsx")
MENU_IMG_DIR = os.path.join(DATA_DIR, "menu_images")

MEALS = ["breakfast", "lunch", "dinner"]

# Time windows (all bookings are for TOMORROW)
TIME_WINDOWS = {
    "breakfast": {
        "book_start": time(19, 0),   # 19:00 prev day
        "book_end":   time(21, 0),   # 21:00 prev day
        "cancel_start": time(21, 0), # 21:00 prev day
        "cancel_end":   time(22, 0), # 22:00 prev day
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
def ensure_data_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MENU_IMG_DIR, exist_ok=True)
    # create booking file if missing
    if not os.path.exists(BOOKING_FILE):
        df = pd.DataFrame(columns=["date", "student_id", "name", "meal", "status", "timestamp"])
        df.to_excel(BOOKING_FILE, index=False)
    # users file must exist (you created it earlier). If not, create sample small file.
    if not os.path.exists(USERS_FILE):
        sample = []
        for i in range(1, 11):
            sample.append({"student_id": f"H{i:03}", "name": f"Student {i}", "password": f"P{i:03}"})
        sample.append({"student_id": "ADMIN", "name": "Admin", "password": "admin123"})
        pd.DataFrame(sample).to_excel(USERS_FILE, index=False)

def load_users():
    return pd.read_excel(USERS_FILE, dtype=str)

def load_bookings():
    return pd.read_excel(BOOKING_FILE, dtype=str)

def append_booking_row(date_str, student_id, name, meal, status):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = {"date": date_str, "student_id": student_id, "name": name, "meal": meal, "status": status, "timestamp": timestamp}
    df = load_bookings()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_excel(BOOKING_FILE, index=False)

def get_tomorrow_date():
    return (datetime.now() + timedelta(days=1)).date()

def in_time_window(window_start: time, window_end: time, now_time: time):
    # simple inclusive check (window in same day)
    return (now_time >= window_start) and (now_time <= window_end)

def can_book(meal):
    now = datetime.now().time()
    w = TIME_WINDOWS[meal]
    return in_time_window(w["book_start"], w["book_end"], now)

def can_cancel(meal):
    now = datetime.now().time()
    w = TIME_WINDOWS[meal]
    return in_time_window(w["cancel_start"], w["cancel_end"], now)

def user_has_active_booking(date_str, student_id, meal):
    df = load_bookings()
    # find last status for that meal for that date & user (consider last row)
    sel = df[(df["date"] == date_str) & (df["student_id"] == student_id) & (df["meal"] == meal)]
    if sel.empty:
        return False, None  # not booked
    last_status = sel.iloc[-1]["status"]
    return (last_status.lower() == "booked"), last_status

def save_menu_image(uploaded_file, date_str):
    filename = os.path.join(MENU_IMG_DIR, f"menu_{date_str}.png")
    image = Image.open(uploaded_file)
    image.save(filename)
    return filename

def get_menu_image_path(date_str):
    p = os.path.join(MENU_IMG_DIR, f"menu_{date_str}.png")
    return p if os.path.exists(p) else None

# ---------------- initialization ----------------
ensure_data_dirs()
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

# ---------------- UI: login ----------------
def login_page():
    st.title("Hostel Meal Booking - Login")

    col1, col2 = st.columns([2,1])
    with col1:
        student_id = st.text_input("Student ID")
        password = st.text_input("Password", type="password")
    with col2:
        st.write("")  # spacing
        login_btn = st.button("Login", key="login_btn")

    if login_btn:
        # match in users
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

    st.info("For demo: use student IDs from data/users.xlsx. Admin: ADMIN / admin123")

# ---------------- UI: admin ----------------
def admin_page():
    st.title("Admin Dashboard")
    st.write("Welcome Admin")

    # upload menu photo for tomorrow
    st.subheader("Upload Today's Menu Photo (for Tomorrow's meals)")
    tomorrow = get_tomorrow_date().isoformat()
    uploaded = st.file_uploader("Upload menu image (png/jpg)", type=["png","jpg","jpeg"], key="menu_upload")
    if uploaded:
        saved_path = save_menu_image(uploaded, tomorrow)
        st.success(f"Menu image saved for {tomorrow}")
        st.image(saved_path, caption=f"Menu for {tomorrow}", use_column_width=True)

    st.markdown("---")
    st.subheader("View / Export Bookings")
    # date filter
    date_sel = st.date_input("Select date to view bookings", value=get_tomorrow_date())
    date_str = date_sel.isoformat()

    df = load_bookings()
    df_date = df[df["date"] == date_str]

    st.write(f"Total records for {date_str}: {len(df_date)}")
    st.dataframe(df_date)

    # pie chart by meal & status (booked count)
    if not df_date.empty:
        counts = df_date[df_date["status"].str.lower() == "booked"].groupby("meal").size()
        fig, ax = plt.subplots()
        counts.plot.pie(autopct="%1.0f%%", ax=ax)
        ax.set_ylabel("")
        st.pyplot(fig)

    # export CSV / Excel of filtered data
    csv_bytes = df_date.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv_bytes, file_name=f"bookings_{date_str}.csv", mime="text/csv")
    # excel
    towrite = io.BytesIO()
    df_date.to_excel(towrite, index=False, engine="openpyxl")
    st.download_button("Download Excel", data=towrite.getvalue(), file_name=f"bookings_{date_str}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("---")
    if st.button("Logout", key="admin_logout"):
        st.session_state.logged_in = False
        st.session_state.student_id = ""
        st.session_state.role = None
        goto("login")

# ---------------- UI: user ----------------
def user_page():
    st.title("Meal Booking Page")
    uid = st.session_state.student_id
    user_row = users_df[users_df["student_id"] == uid]
    name = user_row.iloc[0]["name"] if not user_row.empty else ""

    st.write(f"Welcome, **{name}** ({uid})")
    st.write(f"Booking is always for **{get_tomorrow_date().isoformat()}**")

    # show menu image for tomorrow (if exists)
    menu_img = get_menu_image_path(get_tomorrow_date().isoformat())
    if menu_img:
        st.image(menu_img, caption=f"Menu for {get_tomorrow_date().isoformat()}", use_column_width=True)

    st.markdown("---")
    st.subheader("Book / Cancel options (buttons appear only in allowed time windows)")

    # show each meal block
    for meal in MEALS:
        st.markdown(f"### {meal.capitalize()}")
        bs = can_book(meal)
        cs = can_cancel(meal)

        booked, last_status = user_has_active_booking(get_tomorrow_date().isoformat(), uid, meal)

        row = st.columns([1,1,1])
        with row[0]:
            if bs:
                if not booked:
                    if st.button(f"Book {meal.capitalize()}", key=f"book_{meal}"):
                        append_booking_row(get_tomorrow_date().isoformat(), uid, name, meal, "booked")
                        st.success(f"{meal.capitalize()} booked for {get_tomorrow_date().isoformat()}")
                        st.experimental_rerun()
                else:
                    st.info(f"Already booked ({last_status})")
            else:
                st.write("Booking not Open")

        with row[1]:
            if cs:
                if booked:
                    if st.button(f"Cancel {meal.capitalize()}", key=f"cancel_{meal}"):
                        append_booking_row(get_tomorrow_date().isoformat(), uid, name, meal, "cancelled")
                        st.success(f"{meal.capitalize()} cancelled for {get_tomorrow_date().isoformat()}")
                        st.experimental_rerun()
                else:
                    st.write("No active booking to cancel")
            else:
                st.write("Cancel not Open")

        with row[2]:
            # show last status
            if last_status:
                st.write(f"Last status: **{last_status}**")
            else:
                st.write("No record yet")

        st.markdown("---")

    if st.button("Logout", key="user_logout"):
        st.session_state.logged_in = False
        st.session_state.student_id = ""
        st.session_state.role = None
        goto("login")


# ---------------- routing ----------------
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "admin":
    # protect admin route
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

