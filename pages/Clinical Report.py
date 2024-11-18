import streamlit as st
from utils import load_clinician_data, load_shift_data, load_case_data, load_all_clinicans_data, load_data, load_hourly_data
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from navigation import make_sidebar

make_sidebar()
st.header("Performance - All Clinicians")

rotas_df = load_data()
role_df = rotas_df

role_headers = rotas_df['role'].unique().tolist()
role_headers.insert(0, '(All)')
selected_role = st.sidebar.selectbox('Select Role', role_headers)

# Add 'year' and 'month' columns to the DataFrame
rotas_df['year'] = rotas_df['date'].dt.year
rotas_df['month'] = rotas_df['date'].dt.strftime('%b')  # Short month name, e.g., Oct

# Create a 'month_year' column that combines the month and year
rotas_df['month_year'] = rotas_df['date'].dt.strftime('%B %Y')

# Get unique month-year combinations, sorted in descending order
month_years = rotas_df['month_year'].unique().tolist()
month_years.sort(key=lambda x: pd.to_datetime(x, format='%B %Y'), reverse=True)  # Sort chronologically descending
month_years.insert(0, '(All)')  # Add option to view all months

# Sidebar options for selecting month-year
selected_month_year = st.sidebar.selectbox('Select Month-Year', month_years)



# st.write(hour_df)

# if selected_month != "(All)":
#     role_df = role_df[role_df['month'] == selected_month]
if selected_month_year != "(All)":
    # Split the selected month-year into month and year
    role_df = role_df[role_df['month_year'] == selected_month_year]


df = load_all_clinicans_data(selected_month_year)
df.insert(0, 'Select', [False for _ in range(df.shape[0])])
edited_df = st.data_editor(df.drop("personid", axis=1), num_rows= "fixed", disabled=df.columns.drop('Select'), hide_index=True)
# Filter to find selected rows based on the 'Select' column
selected_rows = edited_df[edited_df['Select']].index.tolist()

if len(selected_rows) != 1:
    st.error("Please Select One Clinician to Proceed") 

else:
    p_id = df.iloc[selected_rows]['personid'].values[0]
    indv_clinician_df = load_clinician_data(df.iloc[selected_rows]['personid'].values[0], selected_month_year)
    st.write(indv_clinician_df)
    st.header(f"Performance - {str(indv_clinician_df['clinician_name'][0])}")

    # ---- Summary Metrics ----
    st.subheader("Summary Metrics")
    col1, col2, col3 = st.columns(3)

    col1.metric("Total Consultations", indv_clinician_df['total_consultations'].sum())
    col2.metric("Total Hours", indv_clinician_df['total_hours'].sum())
    col3.metric("Total Cost", indv_clinician_df['total_cost'].sum())

    # colum1, colum2 = st.columns(2)
    # with colum1:
        # st.subheader("Shift Costs Over Time")
        # fig = px.bar(indv_clinician_df, x='shift_date', y='shift_cost', title='Shift Costs Over Time')
        # fig.update_xaxes(tickmode='linear', tickangle=45)
        # st.plotly_chart(fig)


    # Create a pie chart to show shift location distribution
    # with colum2:
    #     st.subheader("Shift Location Distribution")
    #     location_counts = indv_clinician_df['location'].value_counts().reset_index()
    #     location_counts.columns = ['Location', 'Count']
    #     darker_blues = ['#1f77b4', '#2a8dc2', '#3399d6', '#4ba3df', '#5fb6ed']
    #     fig = px.pie(location_counts, values='Count', names='Location', title='Shift Location Distribution', color_discrete_sequence=darker_blues)
    #     st.plotly_chart(fig)

    indv_clinician_df.insert(0, 'Select', [False for _ in range(indv_clinician_df.shape[0])])

    indv_edit_df = st.data_editor(indv_clinician_df.drop(columns=["clinician_name", "personid", "personid"]), num_rows= "fixed", disabled=df.columns.drop('Select'), hide_index=True)
    selected_shift= indv_edit_df[indv_edit_df['Select']].index.tolist()

    if len(selected_shift) != 1:
        st.error("Please Select One Shift to Proceed") 
    else:
        indv_shift_df = load_shift_data(indv_clinician_df.iloc[selected_shift]['rslid'].values[0])
        st.header(f"Performance - {str(indv_shift_df['shift_start_time'][0])} : {str(indv_shift_df['shift_end_time'][0])} ")

        # ---- Summary Metrics ----
        st.subheader("Key Metrics")

        # Calculate summary statistics
        total_cases = indv_shift_df['case_number'].nunique()
        total_consultation_duration = indv_shift_df['consultation_duration_mins'].sum()
        avg_consultation_duration = indv_shift_df['consultation_duration_mins'].mean()
        consultation_type_counts = indv_shift_df['consultation_type'].value_counts()

        # Display summary metrics using columns for better layout
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Cases", total_cases)
        col2.metric("Total Consultation Duration (mins)", f"{total_consultation_duration:.2f}")
        col3.metric("Average Consultation Duration (mins)", f"{avg_consultation_duration:.2f}")

        # Consultation Type Breakdown
        st.subheader("Consultation Type Breakdown")
        darker_blues = ['#1f77b4', '#2a8dc2', '#3399d6', '#4ba3df', '#5fb6ed']

        fig = px.pie(values=consultation_type_counts, names=consultation_type_counts.index, title='Consultation Type Distribution', color_discrete_sequence=darker_blues)
        st.plotly_chart(fig)

        indv_shift_df.insert(0, 'Select', [False for _ in range(indv_shift_df.shape[0])])

        indv_caseedit_df = st.data_editor(indv_shift_df, num_rows= "fixed", disabled=df.columns.drop('Select'), hide_index=True)
        selected_case= indv_caseedit_df[indv_caseedit_df['Select']].index.tolist()

        if len(selected_case) != 1:
            st.error("Please Select One Case to Proceed") 
        else:
            # pass
            caseno = indv_shift_df.iloc[selected_case]['case_number'].values[0]
            indv_case_df = load_case_data(caseno)
            st.header(f"Performance - {str(indv_case_df['caseno'][0])}")                            
            
            co1, co2, co3 = st.columns(3)
            co1.metric("Consultation Duration (mins)", indv_case_df["consultation_duration_mins"][0])
            co2.metric("Age", indv_case_df["age"][0])
            co3.metric("Location", indv_case_df["location"][0])

            # General Information
            st.subheader("Patient Information")
            st.write("**Sex:**", indv_case_df["sex"][0])
            st.write("**Diagnosis Outcome:**", indv_case_df["dx_outcome"][0])
            st.write("**Received Case Type:**", indv_case_df["received_case_type"][0])
            st.write("**Finished Case Type:**", indv_case_df["finished_case_type"][0])

            # Case Priority Information
            st.subheader("Priority Information")
            st.write("**Priority on Reception:**", indv_case_df["priority_on_reception"][0])
            st.write("**Priority after Assessment:**", indv_case_df["priority_after_assessment"][0])
            st.write("**Priority on Completion:**", indv_case_df["priority_on_completion"][0])

            # Consultation Information
            for i in range(indv_case_df.shape[0]):
                st.subheader(f"Consultation Details {i+1}")
                st.write("**Start Time:**", indv_case_df["Cons_Begin_Time"][i])
                st.write("**End Time:**", indv_case_df["Cons_End_Time"][i])
                st.write("**Diagnosis:**", indv_case_df["Cons_Diagnosis"][i])
                st.write("**Treatment:**", indv_case_df["Cons_Treatment"][i])
            
                # Satisfaction Score (if available)
                if pd.notna(indv_case_df["satisfaction"][i]):
                    st.metric("Satisfaction Score", indv_case_df["satisfaction"][i])

                # Comments (if available)
                if pd.notna(indv_case_df["survey_comments"][i]):
                    st.subheader("Survey Comments")
                    st.write(indv_case_df["survey_comments"][i])