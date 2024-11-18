import streamlit as st
from time import sleep
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.source_util import get_pages


def get_current_page_name():
    ctx = get_script_run_ctx()
    if ctx is None:
        raise RuntimeError("Couldn't get script context")

    pages = get_pages("")

    return pages[ctx.page_script_hash]["page_name"]

def make_sidebar():
    st.set_page_config(page_title="BARDOC Dashboard", page_icon="🏥", layout="wide")
    with st.sidebar:
        st.sidebar.image("BARDOC-Transparent-LOGO-350-x-100.webp", width=150)
        st.write("")
        st.write("")

        if st.session_state.get("logged_in", False):
            st.page_link("pages/Activity Report.py", label="Activity Report", icon="📈")
            st.page_link("pages/Clinical Report.py", label="Clinical Report", icon="🩺")

            st.write("")
            st.write("")

        elif get_current_page_name() != "main":
            # If anyone tries to access a secret page without being logged in,
            # redirect them to the login page
            st.switch_page("main.py")
