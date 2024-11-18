import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv
import streamlit_authenticator as stauth
from utils import load_data, ensure_duration_format, load_hourly_data
from streamlit_extras.mandatory_date_range import date_range_picker
from navigation import make_sidebar
from time import sleep

make_sidebar()
load_dotenv()

# if 'selected_row_index' not in st.session_state:
#         st.session_state.selected_row_index = None
#         st.session_state.next_btn = False

names = ["Admin User"]
usernames = ["admin"]
passwords = ["He4lth!"]
hashed_passwords = stauth.Hasher(passwords).generate()

authenticator = stauth.Authenticate(
    names=names,
    usernames=usernames,
    passwords=hashed_passwords,
    cookie_name="bardoc_dashboard",
    key="abcdef",
    cookie_expiry_days=0
)


name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status:
    st.session_state.logged_in = True
    st.success("Logged in successfully!")
    sleep(0.5)
    st.switch_page("pages/Activity Report.py")

elif authentication_status == False:
    st.error("Username or password is incorrect")
elif authentication_status == None:
    st.warning("Please enter your username and password")
