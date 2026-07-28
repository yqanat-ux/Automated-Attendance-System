"""
ATTENDANCE TREND WARNING SYSTEM (no history table needed)
not connected to anything and not useful class might be deleted 
===========================================================
Runs AFTER your daily attendance script (First_File.py) adds new records.

Instead of storing "last seen" percentages in a separate table, this
version calculates BOTH the current percentage AND the percentage as it
was BEFORE today's newest day was added - all from attendance_detail
alone, in the same query. Since First_File.py always adds exactly one
new day per run, "before" = everything except the most recent date.

No new table, no persisted state between runs - everything is derived
fresh, every time, straight from the raw data.

USAGE:
    */10 * * * * /usr/bin/python3 First_File.py && /usr/bin/python3 attendance_trend_warning.py >> attendance_log.txt 2>&1
"""

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "172.27.0.1",
    "port": 5432,
    "dbname": "My server",
    "user": "postgres",
    "password": "123"
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_before_and_after(conn):
    """
    For each student+course, calculates:
      - current_percent  = absence % using ALL recorded days
      - previous_percent = absence % using all days EXCEPT the most
                            recent date for that course (i.e. "before
                            today's new day was added")

    Both numbers come from attendance_detail alone - nothing stored,
    nothing remembered between runs.
    """
    query = """
        WITH latest_date AS (
            SELECT crse_id, MAX(class_attend_dt) AS max_dt
            FROM attendance_detail
            GROUP BY crse_id
        )
        SELECT
            ad.emplid,
            ad.student_name,
            ad.crse_id,
  
            -- current: every day counted
            COUNT(*) AS total_days,
            COUNT(CASE WHEN ad.attend_present = 'N' THEN 1 END) AS absent,
            ROUND(
                (COUNT(CASE WHEN ad.attend_present = 'N' THEN 1 END)::numeric
                 / NULLIF(COUNT(*), 0)) * 100, 2
            ) AS current_percent,

            -- previous: every day EXCEPT the latest date for this course
            COUNT(CASE WHEN ad.class_attend_dt <> ld.max_dt THEN 1 END) AS prev_total_days,
            COUNT(CASE WHEN ad.class_attend_dt <> ld.max_dt
                       AND ad.attend_present = 'N' THEN 1 END) AS prev_absent,
            ROUND(
                (COUNT(CASE WHEN ad.class_attend_dt <> ld.max_dt
                            AND ad.attend_present = 'N' THEN 1 END)::numeric
                 / NULLIF(COUNT(CASE WHEN ad.class_attend_dt <> ld.max_dt THEN 1 END), 0)
                ) * 100, 2
            ) AS previous_percent

        FROM attendance_detail ad
        JOIN latest_date ld ON ad.crse_id = ld.crse_id
        GROUP BY ad.emplid, ad.student_name, ad.crse_id, ld.max_dt;
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        return cur.fetchall()


def check_for_warnings():
    conn = get_connection()
    try:
        rows = get_before_and_after(conn)
        warnings = []

        for row in rows:
            current_percent = float(row["current_percent"] or 0)
            previous_percent = row["previous_percent"]

            # If there's no "previous" data yet (e.g. only one day exists
            # total for this course), skip - nothing to compare against.
            if previous_percent is None:
                continue

            previous_percent = float(previous_percent)

            if previous_percent < 15.0 <= current_percent:
                warnings.append({
                    "emplid": row["emplid"], "student_name": row["student_name"],
                    "crse_id": row["crse_id"], "percent": current_percent,
                    "message": "Reminder: you have crossed 15% absence."
                })
            if previous_percent < 20.0 <= current_percent:
                warnings.append({
                    "emplid": row["emplid"], "student_name": row["student_name"],
                    "crse_id": row["crse_id"], "percent": current_percent,
                    "message": "Reminder: you are at 20% absence."
                })
            if previous_percent < 25.0 <= current_percent:
                warnings.append({
                    "emplid": row["emplid"], "student_name": row["student_name"],
                    "crse_id": row["crse_id"], "percent": current_percent,
                    "message": "You are Deprived (25% or more absence)."
                })

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
        print(f"❌ Error checking trends: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    check_for_warnings()