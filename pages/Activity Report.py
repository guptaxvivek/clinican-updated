import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta
from dotenv import load_dotenv
from utils import load_data, ensure_duration_format, load_hourly_data
from streamlit_extras.mandatory_date_range import date_range_picker
from navigation import make_sidebar

make_sidebar()

def plot_daily_hours_cost(data, start_date, end_date): 
    data.loc[:, 'duration'] = data['duration'].astype(str).apply(ensure_duration_format)
    data.loc[:, 'date'] = pd.to_datetime(data['date'], errors='coerce')
    data.loc[:, 'duration_hours'] = pd.to_timedelta(data['duration'], errors='coerce').dt.total_seconds() / 3600
    data.loc[:, 'value'] = data['value'].astype(float)

    filtered_data = data.query("@start_date <= date <= @end_date")

    grouped_data = filtered_data.groupby(['date', 'role'], as_index=False).agg(
        total_hours=('duration_hours', 'sum'),
        total_cost=('value', 'sum')
    )

    fig_hours = px.line(grouped_data, x='date', y='total_hours', color='role',
                        title='Total Hours per Day by Role', color_discrete_sequence=px.colors.sequential.Blues)

    fig_cost = px.line(grouped_data, x='date', y='total_cost', color='role',
                       title='Total Cost per Day by Role', color_discrete_sequence=px.colors.sequential.Blues)

    # Display in Streamlit
    st.subheader("Daily Hours and Cost by Role")
    st.plotly_chart(fig_hours)
    st.plotly_chart(fig_cost)


st.title('Clinician Performance Dashboard')
try:
    rotas_df = load_data()
    curr_day = datetime.now()

    rotas_df['year'] = rotas_df['date'].dt.year
    rotas_df['month'] = rotas_df['date'].dt.strftime('%b')

    rotas_df['month_year'] = rotas_df['date'].dt.strftime('%B %Y')


    adastras = rotas_df['adastra'].unique().tolist()
    adastras.insert(0, '(All)')
    adastras.sort()
    # selected_adastra = st.sidebar.selectbox('Select User', adastras)

    # role_df = rotas_df 
    with st.sidebar:
        result = date_range_picker("Select a date range", default_start=(curr_day-timedelta(days=1)).date(), default_end=curr_day.date())
        if isinstance(result, tuple):
            hour_df = load_hourly_data(result[0], result[1])

    hour_df['hour'] = pd.to_datetime(hour_df['hour'])

    st.title("Activity by Hour Graph")

    fig = go.Figure()

    fig.add_trace(go.Scatter(x=hour_df['hour'], y=hour_df['num_calls'], mode='lines+markers', name='Num Calls'))
    fig.add_trace(go.Scatter(x=hour_df['hour'], y=hour_df['gp_advice_consults'], mode='lines+markers', name='GP Advice Consults'))
    fig.add_trace(go.Scatter(x=hour_df['hour'], y=hour_df['advice_consults'], mode='lines+markers', name='Advice Consults'))
    fig.add_trace(go.Scatter(x=hour_df['hour'], y=hour_df['visit'], mode='lines+markers', name='Visit'))
    fig.add_trace(go.Scatter(x=hour_df['hour'], y=hour_df['treatment_centre'], mode='lines+markers', name='Treatment Centre'))

    fig.update_layout(
        title="Activity by Hour Chart",
        xaxis_title="Hour",
        yaxis_title="Count",
        legend_title="Metrics",
        xaxis=dict(tickformat="%H:%M"),
        template="plotly_white"
    )

    st.plotly_chart(fig)
    plot_daily_hours_cost(rotas_df, result[0], result[1])

except Exception as e:
    st.error(f"An error occurred: {str(e)}")