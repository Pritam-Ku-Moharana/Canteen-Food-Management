import streamlit as st
import pandas as pd
import openpyxl

st.set_page_config(page_title="Hostel Meal Booking")

# ------------- state ------------- #
if "page" not in st.session_state:
    st.session_state.page = "login"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

users = pd.read_excel("users.xlsx")

def login_page():
    st.title("Hostel Meal Booking Login")

    student_id = st.text_input("Student ID")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        match = users[(users["student_id"] == student_id) & (users["password"] == password)]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.student_id = student_id      # <---- IMPORTANT

            if student_id == "admin":
                st.session_state.page = "admin"
            else:
                st.session_state.page = "user"

            st.experimental_rerun()
        else:
            st.error("Invalid ID or Password ❌")


def admin_page():
    st.title("Admin Dashboard")
    st.write("Welcome Admin")

    if st.button("Logout"):
        st.session_state.page = "login"
        st.experimental_rerun()


def user_page():
    st.title("Meal Booking Page")
    st.write("Welcome User", st.session_state.student_id)

    if st.button("Logout"):
        st.session_state.page = "login"
        st.experimental_rerun()


# -------- ROUTING -------- #
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "admin":
    admin_page()
elif st.session_state.page == "user":
    user_page()
