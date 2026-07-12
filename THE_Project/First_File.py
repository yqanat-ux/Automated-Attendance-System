"""
Connects to PostgreSQL and adds ONE new day's attendance record
for every student, in every course, each time this script runs.

Uses Faker to randomly decide Present ('Y') / Absent ('N') per student,
weighted ~85% present / 15% absent (matching the original data pattern).

Run this once per "day" you want to simulate/add real attendance for.
"""

import psycopg2
from psycopg2.extras import execute_values
from faker import Faker
from datetime import date

# ============================================================
# CONNECTION SETTINGS - update to match your server
# ============================================================
DB_CONFIG = {
    "host": "172.27.0.1",       # or "127.0.0.1"
    "port": 5432,
    "dbname": "My server",   # <-- CHANGE THIS to your actual database name
    "user": "postgres",
    "password": "123"        # <-- CHANGE THIS to your actual password
}

fake = Faker()


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_student_courses(conn):
    """
    Returns every unique student+course combination currently tracked,
    pulled from existing attendance_detail records (so we know exactly
    who to generate a new day's record for).
    """
    query = """
        SELECT DISTINCT 
            institution, acad_career, emplid, student_name, campus_id,
            acad_prog, strm, campus, crse_id, course_title_long,
            subject, catalog_nbr, class_nbr, descr, class_section,
            start_dt, descrshort
        FROM attendance_detail;
    """
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def get_next_attendance_date(conn, crse_id):
    """
    Finds the most recent recorded date for a course and returns
    the next day after it, so we never duplicate an existing date.
    """
    query = """
        SELECT MAX(class_attend_dt) 
        FROM attendance_detail 
        WHERE crse_id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(query, (crse_id,))
        last_date = cur.fetchone()[0]
    if last_date is None:
        return date.today()
    from datetime import timedelta
    return last_date + timedelta(days=1)


def add_daily_attendance():
    """
    Main function: adds one new attendance record per student per course,
    for the next date after the latest one currently on file.
    """
    conn = get_connection()
    try:
        rows = get_student_courses(conn)
        print(f"Found {len(rows)} student-course combinations.")

        # Group by crse_id to determine the next date per course
        # (in case courses have different numbers of days recorded)
        courses = {}
        for r in rows:
            crse_id = r[8]
            courses.setdefault(crse_id, []).append(r)

        new_records = []
        for crse_id, student_rows in courses.items():
            next_date = get_next_attendance_date(conn, crse_id)
            print(f"Adding attendance for {crse_id} on {next_date}")

            for r in student_rows:
                (institution, acad_career, emplid, student_name, campus_id,
                 acad_prog, strm, campus, crse_id_val, course_title_long,
                 subject, catalog_nbr, class_nbr, descr, class_section,
                 start_dt, descrshort) = r

                # Faker generates True/False, weighted 85% True (Present)
                is_present = fake.boolean(chance_of_getting_true=85)
                attend_present = 'Y' if is_present else 'N'

                new_records.append((
                    institution, acad_career, emplid, student_name, campus_id,
                    acad_prog, strm, campus, crse_id_val, course_title_long,
                    subject, catalog_nbr, class_nbr, descr, class_section,
                    start_dt, descrshort, next_date, attend_present
                ))

        insert_query = """
            INSERT INTO attendance_detail (
                institution, acad_career, emplid, student_name, campus_id,
                acad_prog, strm, campus, crse_id, course_title_long,
                subject, catalog_nbr, class_nbr, descr, class_section,
                start_dt, descrshort, class_attend_dt, attend_present
            ) VALUES %s;
        """

        with conn.cursor() as cur:
            execute_values(cur, insert_query, new_records)
        conn.commit()

        present_count = sum(1 for r in new_records if r[-1] == 'Y')
        absent_count = len(new_records) - present_count

        print(f"\n✅ Added {len(new_records)} new attendance records.")
        print(f"   Present: {present_count} | Absent: {absent_count}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    add_daily_attendance()