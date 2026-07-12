"""
ATTENDANCE TREND WARNING SYSTEM
================================
Runs AFTER your daily attendance script (First_File.py) adds new records.
Compares each student's CURRENT absent_percent (calculated live from
attendance_detail's raw daily Y/N records) to their PREVIOUS run's
absent_percent, and prints/logs a warning if it increased meaningfully.

Requires a small tracking table to remember "last seen" percentages
between runs, since the database itself doesn't store history otherwise.

SETUP (run once):
    Creates a table called attendance_trend_history automatically
    the first time this script runs.

USAGE:
    Run this right after First_File.py in your cron job, e.g.:

    */10 * * * * /usr/bin/python3 First_File.py && /usr/bin/python3 attendance_trend_warning.py >> attendance_log.txt 2>&1
"""

import psycopg2
from psycopg2.extras import RealDictCursor

# ============================================================
# CONNECTION SETTINGS - match First_File.py
# ============================================================
DB_CONFIG = {
    "host": "172.27.0.1",
    "port": 5432,
    "dbname": "My server",
    "user": "postgres",
    "password": "123"
}

# Specific thresholds and their exact messages:
#   15% -> "Reminder: you have crossed 15% absence."
#   20% -> "Reminder: you are at 20% absence."
#   25%+ -> "You are Deprived (25% or more absence)."


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def ensure_history_table(conn):
    """Creates the tracking table if it doesn't already exist."""
    query = """
        CREATE TABLE IF NOT EXISTS attendance_trend_history (
            emplid varchar(50),
            crse_id varchar(50),
            last_absent_percent numeric,
            PRIMARY KEY (emplid, crse_id)
        );
    """
    with conn.cursor() as cur:
        cur.execute(query)
    conn.commit()


def get_current_summary(conn):
    """
    Pulls the current absent_percent for every student+course,
    calculated LIVE from attendance_detail (raw day-by-day records),
    not from the attendance_summary view.
    """
    query = """
        SELECT
            emplid,
            student_name,
            crse_id,
            COUNT(*) AS total_days,
            COUNT(CASE WHEN attend_present = 'N' THEN 1 END) AS absent,
            ROUND(
                (COUNT(CASE WHEN attend_present = 'N' THEN 1 END)::numeric
                 / NULLIF(COUNT(*), 0)) * 100, 2
            ) AS absent_percent
        FROM attendance_detail
        GROUP BY emplid, student_name, crse_id;
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        return cur.fetchall()


def get_previous_percentages(conn):
    """Pulls what each student's absent_percent was last time we checked."""
    query = "SELECT emplid, crse_id, last_absent_percent FROM attendance_trend_history;"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        rows = cur.fetchall()
    return {(r["emplid"], r["crse_id"]): r["last_absent_percent"] for r in rows}


def update_history(conn, emplid, crse_id, new_percent):
    """Saves the current percentage so next run can compare against it."""
    query = """
        INSERT INTO attendance_trend_history (emplid, crse_id, last_absent_percent)
        VALUES (%s, %s, %s)
        ON CONFLICT (emplid, crse_id)
        DO UPDATE SET last_absent_percent = EXCLUDED.last_absent_percent;
    """
    with conn.cursor() as cur:
        cur.execute(query, (emplid, crse_id, new_percent))


def check_for_warnings():
    conn = get_connection()
    try:
        ensure_history_table(conn)

        current_rows = get_current_summary(conn)
        previous = get_previous_percentages(conn)

        warnings = []

        for row in current_rows:
            emplid = row["emplid"]
            crse_id = row["crse_id"]
            student_name = row["student_name"]
            current_percent = float(row["absent_percent"] or 0)

            key = (emplid, crse_id)
            old_percent = previous.get(key)

            if old_percent is not None:
                old_percent = float(old_percent)

                # Check each threshold in order - only fire the message the
                # first time the student crosses INTO that band, based on
                # comparing old_percent (before) vs current_percent (now).

                # 15% -> reminder they've crossed the first warning line
                if old_percent < 15.0 <= current_percent:
                    warnings.append({
                        "emplid": emplid,
                        "student_name": student_name,
                        "crse_id": crse_id,
                        "percent": current_percent,
                        "message": "Reminder: you have crossed 15% absence."
                    })

                # 20% -> second reminder
                if old_percent < 20.0 <= current_percent:
                    warnings.append({
                        "emplid": emplid,
                        "student_name": student_name,
                        "crse_id": crse_id,
                        "percent": current_percent,
                        "message": "Reminder: you are at 20% absence."
                    })

                # 25% and above -> Deprived status message
                # (fires ONLY ONCE - the moment they cross into 25%+ - not
                # repeated every run while they stay there)
                if old_percent < 25.0 <= current_percent:
                    warnings.append({
                        "emplid": emplid,
                        "student_name": student_name,
                        "crse_id": crse_id,
                        "percent": current_percent,
                        "message": "You are Deprived (25% or more absence)."
                    })

            # Always update history with the latest value for next time
            update_history(conn, emplid, crse_id, current_percent)

        conn.commit()

        if warnings:
            print(f"\n⚠️  {len(warnings)} ATTENDANCE WARNING(S) DETECTED:")
            for w in warnings:
                print(
                    f"   {w['student_name']} ({w['emplid']}) - {w['crse_id']}: "
                    f"{w['percent']}% absence -> {w['message']}"
                )
        else:
            print("No threshold crossings detected this run.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error checking trends: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    check_for_warnings()