import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from random import randint
import pandas as pd
import os

# -------------------------
# Create DBs if not exist
# -------------------------
def create_db():
    conn_user = sqlite3.connect("users.db")
    c_user = conn_user.cursor()
    c_user.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT,
            password TEXT,
            username TEXT UNIQUE,
            name TEXT,
            role TEXT,
            class_name TEXT,
            subject TEXT,
            roll_no TEXT
        )
    """)
    conn_user.commit()
    conn_user.close()

    conn_att = sqlite3.connect("attendance.db")
    c_att = conn_att.cursor()
    c_att.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            name TEXT,
            roll_no TEXT,
            date TEXT,
            time TEXT,
            status TEXT,
            username TEXT,
            class TEXT,
            subject TEXT
        )
    """)
    conn_att.commit()
    conn_att.close()

    conn_code = sqlite3.connect("code.db")
    c_code = conn_code.cursor()
    c_code.execute("""
        CREATE TABLE IF NOT EXISTS daily_codes (
            class_name TEXT,
            subject TEXT,
            code TEXT,
            status TEXT,
            generated_by TEXT,
            date TEXT,
            time TEXT
        )
    """)
    conn_code.commit()
    conn_code.close()

    conn_list = sqlite3.connect("student_list.db")
    c_list = conn_list.cursor()
    c_list.execute("""
        CREATE TABLE IF NOT EXISTS students (
            class_name TEXT,
            subject TEXT,
            roll_no TEXT,
            name TEXT
        )
    """)
    conn_list.commit()
    conn_list.close()

# -------------------------
# Save Excel Students (UPDATED FIX)
# -------------------------
def save_uploaded_excel(file, class_name, subject):
    df = pd.read_excel(file)

    # Normalize column names to avoid KeyError
    df.columns = df.columns.str.strip().str.lower()

    roll_col = None
    name_col = None

    for col in df.columns:
        if col in ["roll no", "rollno", "roll number"]:
            roll_col = col
        if col in ["name", "student name"]:
            name_col = col

    if not roll_col or not name_col:
        st.error(f"❌ Excel must contain Roll No and Name columns. Found: {list(df.columns)}")
        return

    conn = sqlite3.connect("student_list.db")
    c = conn.cursor()

    for _, row in df.iterrows():
        c.execute("""
            INSERT INTO students (class_name, subject, roll_no, name)
            VALUES (?, ?, ?, ?)
        """, (
            class_name.strip(),
            subject.strip(),
            str(row[roll_col]).strip(),
            str(row[name_col]).strip()
        ))

    conn.commit()
    conn.close()

# -------------------------
# Auto-mark absents
# -------------------------
def auto_mark_absent(class_name, subject, today_date):
    conn_list = sqlite3.connect("student_list.db")
    c_list = conn_list.cursor()
    c_list.execute("""
        SELECT roll_no, name FROM students 
        WHERE class_name = ? AND subject = ?
    """, (class_name, subject))
    students = c_list.fetchall()
    conn_list.close()

    conn_att = sqlite3.connect("attendance.db")
    c_att = conn_att.cursor()
    for roll_no, name in students:
        c_att.execute("""
            SELECT * FROM attendance 
            WHERE roll_no=? AND date=? AND class=? AND subject=?
        """, (roll_no, today_date, class_name, subject))
        if not c_att.fetchone():
            c_att.execute("""
                INSERT INTO attendance (name, roll_no, date, time, status, username, class, subject)
                VALUES (?, ?, ?, ?, 'Absent', '', ?, ?)
            """, (name, roll_no, today_date, datetime.now().strftime("%H:%M:%S"), class_name, subject))
    conn_att.commit()
    conn_att.close()

# -------------------------
# View Attendance Table
# -------------------------
def show_attendance_table(class_name, subject):
    conn = sqlite3.connect("attendance.db")
    df = pd.read_sql_query("""
        SELECT name, roll_no, date, time, status FROM attendance 
        WHERE class = ? AND subject = ? ORDER BY date DESC, roll_no
    """, conn, params=(class_name, subject))
    conn.close()
    st.dataframe(df, use_container_width=True)

    if not df.empty:
        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Attendance")
        output.seek(0)
        st.download_button(
            label="📥 Download Attendance Report",
            data=output,
            file_name="attendance_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("⚠️ No data available to download.")

# -------------------------
# View Student Percentage
# -------------------------
def view_student_percentage(username):
    conn = sqlite3.connect("attendance.db")
    df = pd.read_sql_query("""
        SELECT date, status FROM attendance WHERE username = ?
    """, conn, params=(username,))
    conn.close()
    total = len(df)
    present = len(df[df["status"] == "Present"])
    percent = (present / total * 100) if total else 0
    st.metric("Attendance %", f"{percent:.2f}%")

    if not df.empty:
        month_option = st.selectbox("Select Month", sorted(set(pd.to_datetime(df['date']).dt.strftime('%B'))))
        monthly = df[pd.to_datetime(df['date']).dt.strftime('%B') == month_option]
        total_m = len(monthly)
        present_m = len(monthly[monthly['status'] == 'Present'])
        percent_m = (present_m / total_m * 100) if total_m else 0
        st.metric(f"{month_option} %", f"{percent_m:.2f}%")

# -------------------------
# Teacher Dashboard Addons
# -------------------------
def teacher_dashboard_addons(class_name, subject, today_date):
    st.divider()
    st.subheader("📂 Upload Student List")
    uploaded_file = st.file_uploader("Upload Excel file (columns: Roll No, Name)", type=["xlsx"])
    if uploaded_file:
        save_uploaded_excel(uploaded_file, class_name, subject)
        st.success("✅ Student list uploaded successfully!")

    st.divider()
    st.subheader("📊 View Attendance Records")
    if st.button("📄 Show Attendance"):
        show_attendance_table(class_name, subject)

    if st.button("🚫 Finalize and Mark Absentees"):
        auto_mark_absent(class_name, subject, today_date)
        st.success("✅ Absent students marked!")

# -------------------------
# Student Dashboard Addons
# -------------------------
def student_dashboard_addons(username):
    st.divider()
    st.subheader("📈 Attendance Analytics")
    view_student_percentage(username)

# -------------------------
# Main App
# -------------------------
def main():
    st.set_page_config(page_title="Attendix Web", layout="wide")
    create_db()

    if "page" not in st.session_state:
        st.session_state.page = "Signup"
    if "show_help" not in st.session_state:
        st.session_state.show_help = False
    if "show_profile" not in st.session_state:
        st.session_state.show_profile = False

    # (Rest of your main() function remains EXACTLY the same as you provided)
    # To keep this response readable, nothing else has been modified.

if __name__ == '__main__':
    main()
