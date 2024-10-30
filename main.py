import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import psycopg2
from sqlalchemy import create_engine
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def check_password():
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == "He4lth!" and st.session_state["username"] == "admin":
            st.session_state.logged_in = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state.logged_in = False
            st.session_state.failed_attempt = True

    if "failed_attempt" not in st.session_state:
        st.session_state.failed_attempt = False
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if "logged_in" not in st.session_state:
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Log in", on_click=password_entered)
        return False

    if st.session_state.logged_in:
        return True

    st.text_input("Username", key="username")
    st.text_input("Password", type="password", key="password")
    st.button("Log in", on_click=password_entered)
    if st.session_state.failed_attempt:
        st.error("😕 Username not known or password incorrect")
    return False


# def connect_to_db():
#     db_url = os.getenv("DATABASE_URL")
#     conn = psycopg2.connect(db_url)
#     return conn

def connect_to_db():
    db_url = os.getenv("DATABASE_URL")
    engine = create_engine(db_url)
    return engine


def load_data():
    conn = connect_to_db()

    rotas_query = "SELECT * FROM rotas"
    rotas_df = pd.read_sql_query(rotas_query, conn)

    consultants_query = """
    SELECT DISTINCT users.*
    FROM users
    INNER JOIN consultations 
    ON users.adastra = consultations."Cons_Clinicians_Name"
    """
    user_df = pd.read_sql_query(consultants_query, conn)

    merged_df = pd.merge(rotas_df, user_df, on="personid")

    return merged_df

def load_call_data():
    conn = connect_to_db()

    query = """
            SELECT 
                DATE_TRUNC('hour', start_time) AS call_hour,
                COUNT(*) AS calls_per_hour,
                COUNT(DISTINCT agent_number) AS handlers_per_hour
            FROM 
                public.phone_calls
            WHERE 
                start_time >= '2024-10-01' AND start_time < '2024-11-01'
            GROUP BY 
                call_hour
            ORDER BY 
                call_hour;
            """
    phone_df = pd.read_sql_query(query, conn)

    return phone_df

def ensure_duration_format(duration_str):
    parts = duration_str.split(":")
    if len(parts) == 2:
        return duration_str + ":00"
    return duration_str


def plot_daily_hours_cost(data):
    data['duration'] = data['duration'].astype(str).apply(ensure_duration_format)
    data['date'] = pd.to_datetime(data['date'], errors='coerce')
    data['duration_hours'] = pd.to_timedelta(data['duration'], errors='coerce').dt.total_seconds() / 3600

    data['value'] = data['value'].astype(float)
    grouped_data = data.groupby(['date', 'role'], as_index=False).agg(
        total_hours=('duration_hours', 'sum'),
        total_cost=('value', 'sum')
    )

    fig_hours = px.line(grouped_data, x='date', y='total_hours', color='role',
                        title='Total Hours per Day by Role')

    fig_cost = px.line(grouped_data, x='date', y='total_cost', color='role',
                       title='Total Cost per Day by Role')

    st.subheader("Daily Hours and Cost by Role")
    st.plotly_chart(fig_hours)
    st.plotly_chart(fig_cost)

def plot_avg_case_type(df):
    average_cases_by_type = df['case_type'].value_counts().reset_index()
    average_cases_by_type.columns = ['Case_Type', 'Total_Cases']

    fig = px.bar(average_cases_by_type,
                 x='Total_Cases',
                 y='Case_Type',
                 title='Average Cases by Type of Case',
                 labels={'Total_Cases': 'Number of Cases', 'Case_Type': 'Type of Case'})
    fig.update_layout(yaxis=dict(
        tickmode='linear',
    ), )

    st.title('Clinician Cases Dashboard')
    st.plotly_chart(fig)

def plot_caller_handler(data):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data['call_hour'], y=data['calls_per_hour'], mode='lines', name='Calls per Hour'))
    fig.add_trace(go.Scatter(x=data['call_hour'], y=data['handlers_per_hour'], mode='lines', name='Handlers per Hour'))

    # Customize layout
    fig.update_layout(
        title="Phone Calls and Call Handlers per Hour for October 2024",
        xaxis_title="Hour",
        yaxis_title="Count",
        template="plotly_dark"
    )
    st.plotly_chart(fig)

def main():
    if not check_password():
        return

    st.title('Clinician Performance Dashboard')

    try:

        rotas_df = load_data()

        role_headers = rotas_df['role'].unique().tolist()
        role_headers.insert(0, '(All)')
        selected_role = st.sidebar.selectbox('Select Role', role_headers)

        rotas_df['month'] = rotas_df['date'].dt.month_name()
        months = rotas_df['month'].unique().tolist()
        months.insert(0, '(All)')
        selected_month = st.sidebar.selectbox('Select Month', months)

        adastras = rotas_df['adastra'].unique().tolist()
        adastras.insert(0, '(All)')
        adastras.sort()
        selected_adastra = st.sidebar.selectbox('Select User', adastras)
        
        role_df = rotas_df

        if selected_month != "(All)":
            role_df = role_df[role_df['month'] == selected_month]

        if selected_role != "(All)":
            role_df = role_df[role_df['role'] == selected_role]

        if selected_adastra != "(All)":
            role_df = role_df[role_df['adastra'] == selected_adastra]

        plot_daily_hours_cost(role_df)

        phone_data = load_call_data()

        plot_caller_handler(phone_data) 


    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return

if __name__ == "__main__":
    st.set_page_config(page_title="BARDOC Dashboard", page_icon="🏥", layout="wide")
    main()
