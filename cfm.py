import streamlit as st
import pandas as pd
import openpyxl

st.set_page_config(page_title="Hostel Meal Booking")

# ------------- state ------------- #
if "page" not in st.session_state:
    st.session_state.page = "login"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = None




# ------------- load users ------------- #
users = pd.read_excel("users.xlsx")        # A/users.xlsx

# ------------- PAGES ------------- #

def login_page():
    st.title("Hostel Meal Booking Login")

    student_id = st.text_input("Student ID")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        match = users[(users["student_id"] == student_id) & (users["password"] == password)]
        if not match.empty:
            st.session_state.logged_in = True
            
            if student_id == "admin":   # admin user
                st.session_state.page = "admin"
                admin_page()
            else:
                st.session_state.page = "user"
                user_page()

        else:
            st.error("Invalid ID or Password ❌")


def admin_page():
    st.title("Admin Dashboard")
    st.write("Welcome Admin")

    if st.button("Logout"):
        login_page()


def user_page():
    st.title("Meal Booking Page")
    st.write("Welcome User",student_id)

    if st.button("Logout"):
        login_page()


# -------- ROUTING -------- #
if st.session_state.page == "login":
    login_page()

elif st.session_state.page == "admin":
    admin_page()

elif st.session_state.page == "user":
    user_page()




