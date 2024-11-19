import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

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
                        -- This CTE is correct, keep as is
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
                        SELECT
                            u.fullname AS clinician_name,
                            COUNT(DISTINCT c."Caseno") as total_consultations,
                            ROUND(SUM(EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/3600)::numeric, 2) as total_consultation_hours,
                            -- Fixed cost calculation using correlated subquery
                            ROUND((
                                SELECT total_cost
                                FROM shift_hours sh
                                WHERE sh.clinician_name = u.fullname
                            ) / NULLIF(COUNT(DISTINCT c."Caseno"), 0)::numeric, 2) as avg_consultation_cost,
                            -- Rest of the counts remain the same
                            COUNT(DISTINCT CASE WHEN c."Cons_Type" IN ('GP Advice', 'Advice') THEN c."Caseno" END) as gp_advice_count,
                            COUNT(DISTINCT CASE WHEN c."Cons_Type" IN ('Treatment Centre','CAS Treatment Centre - BARDOC') THEN c."Caseno" END) as treatment_centre_count,
                            COUNT(DISTINCT CASE WHEN c."Cons_Type" IN ('Visit','HMR VH Visit') THEN c."Caseno" END) as visit_count,
                            COUNT(DISTINCT CASE
                                WHEN (c."Cons_Type" IN ('GP Advice', 'Advice') AND c."Next_Cons_Type" IN ('GP Advice', 'Advice'))
                                THEN c."Caseno"
                            END) as same_advice_type_count,
                            COUNT(DISTINCT CASE
                                WHEN c."Cons_Type" IN ('GP Advice', 'Advice')
                                THEN c."Caseno"
                            END) as total_advice_count,
                            ROUND(AVG(
                                CASE
                                    WHEN c."Cons_Type" IN ('GP Advice', 'Advice','NWAS Triage')
                                    THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                END
                            )::numeric, 2) as avg_gp_advice_duration,
                            ROUND(AVG(
                                CASE
                                    WHEN c."Cons_Type" IN ('Treatment Centre','CAS Treatment Centre - BARDOC')
                                    THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                END
                            )::numeric, 2) as avg_treatment_centre_duration,
                            ROUND(AVG(
                                CASE
                                    WHEN c."Cons_Type" IN ('Visit','HMR VH Visit')
                                    THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                END
                            )::numeric, 2) as avg_visit_duration
                        FROM rotas r
                        LEFT JOIN consultations c ON r.rslid = c.rslid
                        LEFT JOIN users u ON r.personid = u.personid
                        WHERE DATE_TRUNC('month', r.truelogin) = '{formatted_date}'::date
                        AND r.truelogin IS NOT NULL
                        AND r.truelogout IS NOT NULL
                        AND c."Cons_Type" IN ('GP Advice', 'Advice', 'NWAS Triage','Treatment Centre','CAS Treatment Centre - BARDOC', 'Visit', 'HMR VH Visit' )
                        GROUP BY u.fullname
                        HAVING u.fullname IS NOT NULL
                        )
                        -- Rest of the query remains the same
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
                        cs.gp_advice_count,
                        cs.treatment_centre_count,
                        cs.visit_count,
                        ROUND((cs.same_advice_type_count::numeric / NULLIF(cs.total_advice_count, 0) * 100)::numeric, 2) as advice_closed_percentage,
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
                                COUNT(DISTINCT CASE WHEN c."Cons_Type" IN ('GP Advice', 'Advice') THEN c."Caseno" END) as shift_gp_advice_count,
                                COUNT(DISTINCT CASE WHEN c."Cons_Type" IN ('Treatment Centre','CAS Treatment Centre - BARDOC') THEN c."Caseno" END) as shift_treatment_centre_count,
                                COUNT(DISTINCT CASE WHEN c."Cons_Type" IN ('Visit','HMR VH Visit') THEN c."Caseno" END) as shift_visit_count,
                                -- New: Count advice consultations that remain as advice
                                COUNT(DISTINCT CASE
                                    WHEN (c."Cons_Type" IN ('GP Advice', 'Advice') AND c."Next_Cons_Type" IN ('GP Advice', 'Advice'))
                                    THEN c."Caseno"
                                END) as same_advice_type_count,
                                -- New: Total advice consultations
                                COUNT(DISTINCT CASE
                                    WHEN c."Cons_Type" IN ('GP Advice', 'Advice')
                                    THEN c."Caseno"
                                END) as total_advice_count,
                                -- Average duration by type for this shift (in minutes)
                                ROUND(AVG(
                                    CASE
                                        WHEN c."Cons_Type" IN ('GP Advice', 'Advice','NWAS Triage')
                                        THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                    END
                                )::numeric, 2) as shift_avg_gp_advice_duration,
                                ROUND(AVG(
                                    CASE
                                        WHEN c."Cons_Type" IN ('Treatment Centre','CAS Treatment Centre - BARDOC')
                                        THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                    END
                                )::numeric, 2) as shift_avg_treatment_centre_duration,
                                ROUND(AVG(
                                    CASE
                                        WHEN c."Cons_Type" IN ('Visit','HMR VH Visit')
                                        THEN EXTRACT(EPOCH FROM (c."Cons_End_Time" - c."Cons_Begin_Time"))/60
                                    END
                                )::numeric, 2) as shift_avg_visit_duration
                            FROM rotas r
                            LEFT JOIN consultations c ON r.rslid = c.rslid
                            WHERE DATE_TRUNC('month', r.truelogin) = '{formatted_date}'::date
                            AND r.truelogin IS NOT NULL
                            AND r.truelogout IS NOT NULL
                            AND c."Cons_Type" IN ('GP Advice', 'Advice', 'NWAS Triage','Treatment Centre','CAS Treatment Centre - BARDOC', 'Visit', 'HMR VH Visit')
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
                            -- New: Advice retention percentage
                            ROUND((cs.same_advice_type_count::numeric / NULLIF(cs.total_advice_count, 0) * 100)::numeric, 2) as advice_closed_percentage,
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
                            AND c."Cons_Type" IN ('GP Advice', 'Advice', 'NWAS Triage','Treatment Centre','CAS Treatment Centre - BARDOC', 'Visit', 'HMR VH Visit')
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


def load_hourly_data(start_date, end_date):
    conn = connect_to_db()
    hourly_query = f"""WITH hours_series AS (
                    -- Generate all hours for October 2024
                    SELECT generate_series(
                        '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'::timestamp,
                        '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'::timestamp,
                        '1 hour'::interval
                    ) AS hour_start
                    ),
                    call_stats AS (
                    -- Phone calls statistics
                    SELECT
                        DATE_TRUNC('hour', start_time) AS hour_start,
                        COUNT(*) AS num_calls,
                        ROUND(SUM(CASE
                            WHEN direction = 'INBOUND' THEN duration_talk::decimal / 60
                            ELSE 0
                        END), 2) AS total_inbound_minutes,
                        ROUND(SUM(duration_talk)::decimal / 60, 2) AS total_minutes
                    FROM phone_calls
                    WHERE start_time >= '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'
                        AND start_time < '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'
                    GROUP BY DATE_TRUNC('hour', start_time)
                    ),
                    staff_per_hour AS (
                    -- Count Call Handlers on shift for each hour
                    SELECT
                        h.hour_start,
                        COUNT(DISTINCT r.personid) as num_staff
                    FROM hours_series h
                    LEFT JOIN rotas r ON
                        r.role = 'Call Handler'
                        AND (r.truelogin + interval '1 minute') <= h.hour_start + interval '1 hour'
                        AND (r.truelogout + interval '1 minute') > h.hour_start
                        -- AND r.status = 'Confirmed'
                    GROUP BY h.hour_start
                    ),
                    consultation_stats AS (
                    -- Count consultations by type per hour
                    SELECT
                        DATE_TRUNC('hour', "Cons_Begin_Time") AS hour_start,
                        COUNT(CASE WHEN "Cons_Type" = 'GP Advice' THEN 1 END) as gp_advice_consults,
                        COUNT(CASE WHEN "Cons_Type" = 'Advice' THEN 1 END) as advice_consults,
                        COUNT(CASE WHEN "Cons_Type" = 'Visit' THEN 1 END) as visit,
                        COUNT(CASE WHEN "Cons_Type" = 'Treatment Centre' THEN 1 END) as treatment_centre,
                        COUNT(CASE WHEN "Cons_Type" = 'NWAS Triage' THEN 1 END) as nwas_triage
                    FROM consultations
                    WHERE "Cons_Begin_Time" >= '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'
                        AND "Cons_Begin_Time" < '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'
                    GROUP BY DATE_TRUNC('hour', "Cons_Begin_Time")
                    )
                    SELECT
                    to_char(h.hour_start, 'YYYY-MM-DD HH24:00') AS hour,
                    COALESCE(cs.num_calls, 0) AS num_calls,
                    COALESCE(cs.total_minutes, 0) AS total_minutes,
                    COALESCE(cs.total_inbound_minutes, 0) AS total_inbound_minutes,
                    COALESCE(sph.num_staff, 0) AS num_call_handlers,
                    CASE
                        WHEN COALESCE(sph.num_staff, 0) = 0 THEN 0
                        ELSE ROUND(COALESCE(cs.total_inbound_minutes, 0)::decimal / COALESCE(sph.num_staff, 1), 2)
                    END AS inbound_minutes_per_handler,
                    COALESCE(con.gp_advice_consults, 0) AS gp_advice_consults,
                    COALESCE(con.advice_consults, 0) AS advice_consults,
                    COALESCE(con.visit, 0) AS visit,
                    COALESCE(con.treatment_centre, 0) AS treatment_centre,
                    COALESCE(con.nwas_triage, 0) AS nwas_triage
                    FROM hours_series h
                    LEFT JOIN call_stats cs ON h.hour_start = cs.hour_start
                    LEFT JOIN staff_per_hour sph ON h.hour_start = sph.hour_start
                    LEFT JOIN consultation_stats con ON h.hour_start = con.hour_start
                    ORDER BY h.hour_start;
                    """

    hourly_df = pd.read_sql_query(hourly_query, conn)
    return hourly_df

def ensure_duration_format(duration_str):
    parts = duration_str.split(":")
    if len(parts) == 2:
        return duration_str + ":00"
    return duration_str
