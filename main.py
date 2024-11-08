import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import psycopg2
from sqlalchemy import create_engine
from urllib.parse import urlparse
from datetime import datetime
from dotenv import load_dotenv
import streamlit_authenticator as stauth

st.set_page_config(page_title="BARDOC Dashboard", page_icon="🏥", layout="wide")
load_dotenv()

if 'selected_row_index' not in st.session_state:
        st.session_state.selected_row_index = None
        st.session_state.next_btn = False

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


def connect_to_db():
    db_url = os.getenv("DATABASE_URL")
    engine = create_engine(db_url)
    return engine

    
@st.cache_data(ttl=3600)
def load_case_data(caseno: int):
    conn = connect_to_db()
    case_query = f"""SELECT
                -- Cases table columns
                c.caseno,
                c.active_date,
                c.location,
                c.sex,
                c.age,
                c.call_origin,
                c.clinical_codes,
                c.comfort_call,
                c.dx_outcome,
                c.received_case_type,
                c.finished_case_type,
                c.priority_on_reception,
                c.priority_after_assessment,
                c.priority_on_completion,
                c.od_start_time,
                c.od_finish_time,
                c.ccg,
                c.provider_group,
                c.informational_outcome,
                c.cons_delay,
                c.od_cons_delay,
                c.cons_delayafter_assess,
                -- User personid
                u.personid as clinician_personid,
                -- Consultations table columns
                cons.rslid,
                cons."Case_Type",
                cons."Active_Date" as cons_active_date,
                cons."Call_Origin" as cons_call_origin,
                cons."Location_Name",
                cons."Operator_Who_Received_Case",
                cons."Receive_Time",
                cons."Reported_Condition",
                cons."Priority_On_Reception" as cons_priority_reception,
                cons."Priority_After_Assessment" as cons_priority_assessment,
                cons."Priority_On_Completion" as cons_priority_completion,
                cons."Patient_Audit_Allergy",
                cons."Patient_Audit_Condition",
                cons."Patient_Audit_Medication",
                cons."Cons_Type",
                cons."Next_Cons_Type",
                cons."Cons_Begin_Time",
                cons."Cons_End_Time",
                cons."Cons_Clinicians_Name",
                cons."Cons_History",
                cons."Cons_Examination",
                cons."Cons_Diagnosis",
                cons."Cons_Treatment",
                cons."Clinical_Codes" as cons_clinical_codes,
                cons."Cons_Prescriptions",
                cons."Prescriptions",
                cons."Informational_Outcomes",
                -- Survey information
                s.satisfaction,
                s.comments as survey_comments,
                -- Calculate consultation duration in minutes
                ROUND(EXTRACT(EPOCH FROM (cons."Cons_End_Time" - cons."Cons_Begin_Time"))/60::numeric, 2) as consultation_duration_mins
                FROM cases c
                LEFT JOIN consultations cons ON c.caseno = cons."Caseno"
                LEFT JOIN users u ON cons."Cons_Clinicians_Name" = u.adastra
                LEFT JOIN surveys s ON c.caseno = s.caseno
                WHERE c.caseno = {caseno} -- Parameter to be passed
                ORDER BY cons."Cons_Begin_Time";
"""
    case_df = pd.read_sql_query(case_query, conn)
    return case_df

@st.cache_data(ttl=3600)
def load_all_clinicans_data(selected_month_year:str):
    conn = connect_to_db()
    if selected_month_year != '(All)':
        formatted_date = datetime.strptime(selected_month_year, "%B %Y").strftime("%Y-%m-01")
    else:
        formatted_date = '2024-10-01'
    all_clinicians_query = f"""WITH shift_hours AS (
                        -- Calculate hours and costs per clinician without consultation joins
                        SELECT
                            u.fullname AS clinician_name,
                            r.personid,
                            COUNT(DISTINCT r.rslid) as total_shifts,
                            ROUND(SUM(r.durationdecimal)::numeric, 2) as total_hours,
                            ROUND(SUM(CAST(r.value AS numeric))::numeric, 2) as total_cost
                        FROM rotas r
                        LEFT JOIN users u ON r.personid = u.personid
                        WHERE DATE_TRUNC('month', r.truelogin) = '{formatted_date}'::date
                        AND r.truelogin IS NOT NULL
                        AND r.truelogout IS NOT NULL
                        GROUP BY u.fullname, r.personid
                        HAVING u.fullname IS NOT NULL
                        ),
                        consultation_stats AS (
                        -- Calculate detailed consultation statistics
                        SELECT
                            u.fullname AS clinician_name,
                            COUNT(DISTINCT c."Caseno") as total_consultations,
                            -- Total consultation time in hours
                            ROUND(SUM(EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/3600)::numeric, 2) as total_consultation_hours,
                            -- Cost per consultation
                            ROUND((SUM(CAST(r.value AS numeric)) / COUNT(DISTINCT c."Caseno"))::numeric, 2) as avg_consultation_cost,
                            -- Count by type
                            COUNT(DISTINCT CASE WHEN c."Cons_Type" = 'GP Advice' THEN c."Caseno" END) as gp_advice_count,
                            COUNT(DISTINCT CASE WHEN c."Cons_Type" = 'Treatment Centre' THEN c."Caseno" END) as treatment_centre_count,
                            COUNT(DISTINCT CASE WHEN c."Cons_Type" = 'Visit' THEN c."Caseno" END) as visit_count,
                            -- Average duration by type (in minutes)
                            ROUND(AVG(
                                CASE
                                    WHEN c."Cons_Type" = 'GP Advice'
                                    THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                END
                            )::numeric, 2) as avg_gp_advice_duration,
                            ROUND(AVG(
                                CASE
                                    WHEN c."Cons_Type" = 'Treatment Centre'
                                    THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                END
                            )::numeric, 2) as avg_treatment_centre_duration,
                            ROUND(AVG(
                                CASE
                                    WHEN c."Cons_Type" = 'Visit'
                                    THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                END
                            )::numeric, 2) as avg_visit_duration
                        FROM rotas r
                        LEFT JOIN consultations c ON r.rslid = c.rslid
                        LEFT JOIN users u ON r.personid = u.personid
                        WHERE DATE_TRUNC('month', r.truelogin) = '{formatted_date}'::date
                        AND r.truelogin IS NOT NULL
                        AND r.truelogout IS NOT NULL
                        AND c."Cons_Type" IN ('GP Advice', 'Treatment Centre', 'Visit')
                        GROUP BY u.fullname
                        HAVING u.fullname IS NOT NULL
                        )
                        SELECT
                        sh.personid,
                        sh.clinician_name,
                        sh.total_cost,
                        sh.total_shifts,
                        sh.total_hours,
                        cs.total_consultation_hours,
                        ROUND((cs.total_consultation_hours / sh.total_hours * 100)::numeric, 2) as consultation_time_percentage,
                        cs.total_consultations,
                        cs.avg_consultation_cost,
                        -- Consultation counts by type
                        cs.gp_advice_count,
                        cs.treatment_centre_count,
                        cs.visit_count,
                        -- Average durations in minutes
                        cs.avg_gp_advice_duration as avg_gp_advice_mins,
                        cs.avg_treatment_centre_duration as avg_treatment_centre_mins,
                        cs.avg_visit_duration as avg_visit_mins
                        FROM shift_hours sh
                        INNER JOIN consultation_stats cs ON sh.clinician_name = cs.clinician_name
                        ORDER BY sh.total_shifts DESC, sh.clinician_name;
                        """
    all_clinicians_df = pd.read_sql_query(all_clinicians_query, conn)
    return all_clinicians_df

@st.cache_data(ttl=3600)
def load_shift_data(rslid: int):
    conn = connect_to_db()
    shift_query = f"""SELECT
                    r.personid,
                    r.rslid,
                    r.truelogin as shift_start_time,
                    r.truelogout as shift_end_time,
                    c."Caseno" as case_number,
                    c."Cons_Type" as consultation_type,
                    c."Next_Cons_Type" as next_consultation_type,
                    c."Cons_Begin_Time" as consultation_start,
                    c."Cons_End_Time" as consultation_end,
                    -- Calculate consultation duration in minutes
                    ROUND(EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60::numeric, 2) as consultation_duration_mins
                    FROM rotas r
                    LEFT JOIN consultations c ON r.rslid = c.rslid
                    WHERE r.rslid = {rslid}  -- Parameter to be passed
                    ORDER BY c."Cons_Begin_Time";
                    """
    shift_df = pd.read_sql_query(shift_query, conn)
    return shift_df

@st.cache_data(ttl=3600)
def load_clinician_data(personid: int, selected_month_year:str):
    conn = connect_to_db()
    if selected_month_year != '(All)':
        formatted_date = datetime.strptime(selected_month_year, "%B %Y").strftime("%Y-%m-01")
    else:
        formatted_date = '2024-10-01'
    clinician_query = f"""WITH shift_consultation_stats AS (
                        -- Calculate consultation statistics per shift
                        SELECT
                            r.rslid,
                            COUNT(DISTINCT c."Caseno") as shift_consultations,
                            -- Consultation time for this shift
                            ROUND(SUM(EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/3600)::numeric, 2) as shift_consultation_hours,
                            -- Count by type for this shift
                            COUNT(DISTINCT CASE WHEN c."Cons_Type" = 'GP Advice' THEN c."Caseno" END) as shift_gp_advice_count,
                            COUNT(DISTINCT CASE WHEN c."Cons_Type" = 'Treatment Centre' THEN c."Caseno" END) as shift_treatment_centre_count,
                            COUNT(DISTINCT CASE WHEN c."Cons_Type" = 'Visit' THEN c."Caseno" END) as shift_visit_count,
                            -- Average duration by type for this shift (in minutes)
                            ROUND(AVG(
                                CASE
                                    WHEN c."Cons_Type" = 'GP Advice'
                                    THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                END
                            )::numeric, 2) as shift_avg_gp_advice_duration,
                            ROUND(AVG(
                                CASE
                                    WHEN c."Cons_Type" = 'Treatment Centre'
                                    THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                END
                            )::numeric, 2) as shift_avg_treatment_centre_duration,
                            ROUND(AVG(
                                CASE
                                    WHEN c."Cons_Type" = 'Visit'
                                    THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                END
                            )::numeric, 2) as shift_avg_visit_duration
                        FROM rotas r
                        LEFT JOIN consultations c ON r.rslid = c.rslid
                        WHERE DATE_TRUNC('month', r.truelogin) = '{formatted_date}'::date
                        AND r.truelogin IS NOT NULL
                        AND r.truelogout IS NOT NULL
                        AND c."Cons_Type" IN ('GP Advice', 'Treatment Centre', 'Visit')
                        AND r.personid = {personid}
                        GROUP BY r.rslid
                        )
                        SELECT
                        u.fullname AS clinician_name,
                        u.personid,
                        r.rslid,
                        DATE(r.date) as shift_date,
                        r.truelogin as shift_start,
                        r.truelogout as shift_end,
                        CAST(NULLIF(r.value, '') AS numeric) as shift_cost,
                        r.durationdecimal as shift_hours,
                        cs.shift_consultation_hours,
                        ROUND((cs.shift_consultation_hours / r.durationdecimal * 100)::numeric, 2) as consultation_time_percentage,
                        cs.shift_consultations as total_consultations,
                        ROUND((CAST(NULLIF(r.value, '') AS numeric) / NULLIF(cs.shift_consultations, 0))::numeric, 2) as cost_per_consultation,
                        -- Consultation counts by type
                        cs.shift_gp_advice_count,
                        cs.shift_treatment_centre_count,
                        cs.shift_visit_count,
                        -- Average durations in minutes
                        cs.shift_avg_gp_advice_duration as avg_gp_advice_mins,
                        cs.shift_avg_treatment_centre_duration as avg_treatment_centre_mins,
                        cs.shift_avg_visit_duration as avg_visit_mins,
                        -- Additional shift details
                        r.role as shift_role,
                        r.dutystation as location,
                        r.status as shift_status
                        FROM rotas r
                        LEFT JOIN users u ON r.personid = u.personid
                        LEFT JOIN shift_consultation_stats cs ON r.rslid = cs.rslid
                        WHERE DATE_TRUNC('month', r.truelogin) = '{formatted_date}'::date
                        AND r.truelogin IS NOT NULL
                        AND r.truelogout IS NOT NULL
                        AND r.personid = {personid}
                        AND EXISTS (
                        SELECT 1
                        FROM consultations c
                        WHERE c.rslid = r.rslid
                        AND c."Cons_Type" IN ('GP Advice', 'Treatment Centre', 'Visit')
                        )
                        ORDER BY r.date, r.truelogin;
                        """
    clinician_df = pd.read_sql_query(clinician_query, conn)
    return clinician_df

@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
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
    # data['duration'] = data['duration'].astype(str).apply(ensure_duration_format)
    data.loc[:, 'duration'] = data['duration'].astype(str).apply(ensure_duration_format)
    data.loc[:, 'date'] = pd.to_datetime(data['date'], errors='coerce')
    data.loc[:, 'duration_hours'] = pd.to_timedelta(data['duration'], errors='coerce').dt.total_seconds() / 3600

    data.loc[:,'value'] = data['value'].astype(float)
    grouped_data = data.groupby(['date', 'role'], as_index=False).agg(
        total_hours=('duration_hours', 'sum'),
        total_cost=('value', 'sum')
    )

    fig_hours = px.line(grouped_data, x='date', y='total_hours', color='role',
                        title='Total Hours per Day by Role', color_discrete_sequence=px.colors.sequential.Blues)

    fig_cost = px.line(grouped_data, x='date', y='total_cost', color='role',
                       title='Total Cost per Day by Role', color_discrete_sequence=px.colors.sequential.Blues)

    st.subheader("Daily Hours and Cost by Role")
    st.plotly_chart(fig_hours)
    st.plotly_chart(fig_cost)


# def plot_caller_handler(data):
#     fig = go.Figure()
#     fig.add_trace(go.Scatter(x=data['call_hour'], y=data['calls_per_hour'], mode='lines', name='Calls per Hour'))
#     fig.add_trace(go.Scatter(x=data['call_hour'], y=data['handlers_per_hour'], mode='lines', name='Handlers per Hour'))

#     # Customize layout
#     fig.update_layout(
#         title="Phone Calls and Call Handlers per Hour for October 2024",
#         xaxis_title="Hour",
#         yaxis_title="Count",
#         template="plotly_dark"
#     )
#     st.plotly_chart(fig)

def main():
    # Streamlit Authenticator Login
    name, authentication_status, username = authenticator.login("Login", "main")

    if authentication_status:
        st.title('Clinician Performance Dashboard')

        try:
            rotas_df = load_data()

            role_headers = rotas_df['role'].unique().tolist()
            role_headers.insert(0, '(All)')
            selected_role = st.sidebar.selectbox('Select Role', role_headers)

            # Add 'year' and 'month' columns to the DataFrame
            rotas_df['year'] = rotas_df['date'].dt.year
            rotas_df['month'] = rotas_df['date'].dt.strftime('%b')  # Short month name, e.g., Oct

            # Create a 'month_year' column that combines the month and year
            rotas_df['month_year'] = rotas_df['date'].dt.strftime('%B %Y')  # Full month name + year, e.g., October 2024

            # Get unique month-year combinations, sorted in descending order
            month_years = rotas_df['month_year'].unique().tolist()
            month_years.sort(key=lambda x: pd.to_datetime(x, format='%B %Y'), reverse=True)  # Sort chronologically descending
            month_years.insert(0, '(All)')  # Add option to view all months

            # Sidebar options for selecting month-year
            selected_month_year = st.sidebar.selectbox('Select Month-Year', month_years)

            # rotas_df['month'] = rotas_df['date'].dt.month_name()
            # months = rotas_df['month'].unique().tolist()
            # months.insert(0, '(All)')
            # selected_month = st.sidebar.selectbox('Select Month', months)

            adastras = rotas_df['adastra'].unique().tolist()
            adastras.insert(0, '(All)')
            adastras.sort()
            selected_adastra = st.sidebar.selectbox('Select User', adastras)

            role_df = rotas_df
            df = load_all_clinicans_data(selected_month_year)

            # if selected_month != "(All)":
            #     role_df = role_df[role_df['month'] == selected_month]
            if selected_month_year != "(All)":
                # Split the selected month-year into month and year
                role_df = role_df[role_df['month_year'] == selected_month_year]


            if selected_role != "(All)":
                role_df = role_df[role_df['role'] == selected_role]

            if selected_adastra != "(All)":
                role_df = role_df[role_df['adastra'] == selected_adastra]

            plot_daily_hours_cost(role_df)

            # phone_data = load_call_data()

            # plot_caller_handler(phone_data)

            if st.button("NEXT", use_container_width=True):
                st.session_state.next_btn = True

            if st.session_state.next_btn:
                st.header("Performance - All Clinicians")
                # df['Select'] = False
                df.insert(0, 'Select', [False for _ in range(df.shape[0])])
                edited_df = st.data_editor(df, num_rows= "fixed", disabled=df.columns.drop('Select'), hide_index=True)
                # Filter to find selected rows based on the 'Select' column
                selected_rows = edited_df[edited_df['Select']].index.tolist()

                if len(selected_rows) != 1:
                    st.error("Please Select One Clinician to Proceed") 
                
                else:
                    p_id = df.iloc[selected_rows]['personid'].values[0]
                    indv_clinician_df = load_clinician_data(df.iloc[selected_rows]['personid'].values[0], selected_month_year)
                    
                    st.header(f"Performance - {str(indv_clinician_df['clinician_name'][0])}")

                    # ---- Summary Metrics ----
                    st.subheader("Summary Metrics")
                    col1, col2, col3 = st.columns(3)

                    col1.metric("Total Consultations", indv_clinician_df['total_consultations'].sum())
                    col2.metric("Total Shift Hours", indv_clinician_df['shift_hours'].sum())
                    col3.metric("Total Cost", indv_clinician_df['shift_cost'].sum())

                    colum1, colum2 = st.columns(2)
                    with colum1:
                        st.subheader("Shift Costs Over Time")
                        fig = px.bar(indv_clinician_df, x='shift_date', y='shift_cost', title='Shift Costs Over Time')
                        fig.update_xaxes(tickmode='linear', tickangle=45)
                        st.plotly_chart(fig)


                    # Create a pie chart to show shift location distribution
                    with colum2:
                        st.subheader("Shift Location Distribution")
                        location_counts = indv_clinician_df['location'].value_counts().reset_index()
                        location_counts.columns = ['Location', 'Count']
                        darker_blues = ['#1f77b4', '#2a8dc2', '#3399d6', '#4ba3df', '#5fb6ed']
                        fig = px.pie(location_counts, values='Count', names='Location', title='Shift Location Distribution', color_discrete_sequence=darker_blues)
                        st.plotly_chart(fig)

                    indv_clinician_df.insert(0, 'Select', [False for _ in range(indv_clinician_df.shape[0])])

                    indv_edit_df = st.data_editor(indv_clinician_df, num_rows= "fixed", disabled=df.columns.drop('Select'), hide_index=True)
                    selected_shift= indv_edit_df[indv_edit_df['Select']].index.tolist()
                    # st.write("SELECTED SHIFT", selected_shift)

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


        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
    elif authentication_status == False:
        st.error("Username or password is incorrect")
    elif authentication_status == None:
        st.warning("Please enter your username and password")

if __name__ == "__main__":
    st.sidebar.image("BARDOC-Transparent-LOGO-350-x-100.webp", width=150)
    main()