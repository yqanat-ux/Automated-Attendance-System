# Automated Attendance & Warning System

An automated Python and PostgreSQL data pipeline that simulates, tracks, and monitors student attendance records. The system generates realistic daily attendance data, calculates real-time absence percentages, and triggers progressive warnings for students at risk of deprivation.

**Author:** Yasser Qanat

## 🚀 Features

* **Automated Data Generation:** Connects to PostgreSQL and adds ONE new day's attendance record for every student, in every course, each time the script runs[cite: 1].
* **Realistic Simulation:** Uses the `Faker` library to randomly decide if a student is Present ('Y') or Absent ('N'), weighted at approximately 85% present and 15% absent to match original data patterns[cite: 1].
* **Live Threshold Monitoring:** Compares each student's current absent percentage (calculated live from raw daily records) to their previous run's percentage.
* **Progressive Warnings:** Automatically logs specific warnings when students cross critical absence thresholds:
  * **15%** -> "Reminder: you have crossed 15% absence."[cite: 2]
  * **20%** -> "Reminder: you are at 20% absence."[cite: 2]
  * **25%+** -> "You are Deprived (25% or more absence)." (Fires only once upon crossing)[cite: 2].
* **Robust Error Handling:** Designed to catch database connection issues (such as password authentication failures) and roll back incomplete transactions[cite: 1, 2, 3].

## 🛠️ Technology Stack

* **Language:** Python 3
* **Database:** PostgreSQL
* **Libraries:** `psycopg2`, `Faker`
* **Automation:** Linux Cron / Windows Subsystem for Linux (WSL)

## 📂 File Structure Overview

1. `First_File.py`: The data ingestion script. It queries the database for every unique student/course combination, finds the most recent attendance date, and inserts a new daily record for the next sequential day[cite: 1].
2. `attendance_trend_warning.py`: The monitoring engine. It pulls live absence percentages, compares them against a tracking table (`attendance_trend_history`), and logs any threshold crossings[cite: 2]. 
3. `attendance_log.txt` (Generated): The output log file that records successful insertions and triggered warnings[cite: 2].

## ⚙️ Setup & Installation

**1. Install Dependencies**
Ensure you have Python installed, then install the required modules. *(Note: Failing to install Faker will result in a `ModuleNotFoundError`)*:
```bash
pip install psycopg2-binary faker
