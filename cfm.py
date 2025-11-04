import streamlit as st
import pandas as pd
import openpyxl


st.set_page_config(page_title="Hostel Meal Booking")

# load users
users_df = pd.read_excel("users.xlsx")

st.title("Hostel Meal Booking Login")

student_id = st.text_input("Student ID")
password = st.text_input("Password", type="password")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = None

if st.button("Login"):
    match = users_df[(users_df["student_id"] == student_id) & (users_df["password"] == password)]
    if not match.empty:
        st.session_state.logged_in = True
        
        if student_id == "ADMIN":
            st.session_state.role = "admin"
        else:
            st.session_state.role = "user"

        st.success("Login Successful ✅")
    else:
        st.error("Invalid ID or Password ❌")


# redirect if logged in
if st.session_state.logged_in:
    if st.session_state.role == "admin":
        st.page_link("pages/admin_page.py", label="Go to Admin Dashboard →")
    else:
        st.page_link("pages/user_page.py", label="Go to Booking Page →")


