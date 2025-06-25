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
# Save Excel Students
# -------------------------
def save_uploaded_excel(file, class_name, subject):
    df = pd.read_excel(file)
    conn = sqlite3.connect("student_list.db")
    c = conn.cursor()
    for _, row in df.iterrows():
        c.execute("""
            INSERT INTO students (class_name, subject, roll_no, name)
            VALUES (?, ?, ?, ?)
        """, (class_name.strip(), subject.strip(), str(row['Roll No']), row['Name']))
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

    col1, col2, _, _, col5 = st.columns([1, 1, 4, 4, 2])
    with col1:
        if st.button("Signup", key="nav_signup"):
            st.session_state.page = "Signup"
            st.rerun()
    with col2:
        if st.button("Login", key="nav_login"):
            st.session_state.page = "Login"
            st.rerun()
    with col5:
        if st.button("❓", key="help_toggle"):
            st.session_state.show_help = not st.session_state.show_help
            st.rerun()

        if st.session_state.show_help:
            st.markdown(
                """
                <div style='
                    background-color: #dbeafe;
                    padding: 20px;
                    border-radius: 15px;
                    margin-top: 10px;
                    font-size: 15px;
                    width: 320px;
                    color: black;
                    line-height: 1.7;
                    margin-left: -100px;
                '>
                    <b>🆘 Help & Instructions</b><br><br>
                    👨‍🏫 Teachers upload Excel & generate codes<br>
                    👩‍🎓 Students enter 6-digit code daily<br>
                    🟡 Missing code = Absent<br>
                    📂 Download attendance in Excel<br>
                    📊 View monthly/yearly percentages<br>
                    ✅ Offline app (No Firebase)
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown("<h1 style='text-align: center;'>📘 Attendix Web - Smart Attendance System</h1>", unsafe_allow_html=True)
    st.divider()

    if st.session_state.page == "Signup":
        st.subheader("🔐 Create an Account")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        username = st.text_input("Choose a Username (used for login)")

        if st.button("Sign Up", key="form_signup"):
            if not email or not password or not username:
                st.warning("⚠️ Please fill in all fields.")
            else:
                conn = sqlite3.connect("users.db")
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username = ?", (username,))
                if c.fetchone():
                    st.error("❌ Username already taken.")
                else:
                    user_id = str(uuid.uuid4())
                    c.execute("""
                        INSERT INTO users (id, email, password, username, name, role, class_name, subject, roll_no)
                        VALUES (?, ?, ?, ?, '', '', '', '', '')
                    """, (user_id, email, password, username))
                    conn.commit()
                    conn.close()
                    st.success("✅ Signup successful!")
                    st.info(f"Now login using your username: **{username}**")
                    st.balloons()

    elif st.session_state.page == "Login":
        st.subheader("🔓 Login to Your Account")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login", key="form_login"):
            conn = sqlite3.connect("users.db")
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            user = c.fetchone()
            conn.close()

            if user:
                st.success("✅ Login successful!")
                name, role, class_name, subject, roll_no = user[4], user[5], user[6], user[7], user[8]

                st.session_state.logged_in = True
                st.session_state.username = username

                if not name or not role or not class_name:
                    st.session_state.page = "ProfileSetup"
                else:
                    st.session_state.page = "Dashboard"
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")

    elif st.session_state.page == "ProfileSetup":
        st.subheader("👤 Complete Your Profile")
        name = st.text_input("Full Name")
        role = st.selectbox("Are you a...", ["Student", "Teacher"])
        class_name = st.text_input("Class / Semester")
        subject = st.text_input("Subject")
        roll_no = st.text_input("Roll No (Student only)", disabled=(role == "Teacher"))

        if st.button("Save Profile", key="save_profile"):
            conn = sqlite3.connect("users.db")
            c = conn.cursor()
            c.execute("""
                UPDATE users 
                SET name = ?, role = ?, class_name = ?, subject = ?, roll_no = ?
                WHERE username = ?
            """, (name, role, class_name, subject, roll_no, st.session_state.username))
            conn.commit()
            conn.close()

            st.success("✅ Profile saved!")
            st.session_state.page = "Dashboard"
            st.rerun()

    if st.session_state.page == "Dashboard":
        username = st.session_state.username
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT name, role, class_name, subject, roll_no FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        name, role, class_name, subject, roll_no = user
        emoji = "👨‍🏫" if role == "Teacher" else "👩‍🎓"

        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button(f"{emoji}", key="profile_icon"):
                st.session_state.show_profile = not st.session_state.get("show_profile", False)
                st.rerun()

        st.markdown(f"### 🎉 Welcome, **{name}**!")

        if st.session_state.get("show_profile", False):
            st.markdown(
                f"""
                <div style='
                    background-color: #f0f9ff;
                    padding: 20px;
                    border-radius: 15px;
                    width: 400px;
                    margin-top: 10px;
                    font-size: 16px;
                    color: black;
                    line-height: 1.8;
                '>
                    <b>{emoji} Profile</b><br><br>
                    <b>Name:</b> {name}<br>
                    <b>Role:</b> {role}<br>
                    <b>Class:</b> {class_name}<br>
                    <b>{'Subject' if role=='Teacher' else 'Roll No'}:</b> {subject if role=='Teacher' else roll_no}<br>
                    <b>Username:</b> {username}<br><br>
                """,
                unsafe_allow_html=True
            )
            if st.button("🚪 Logout", key="logout_btn"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        today_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M:%S")

        if role == "Teacher":
            st.subheader("📜 Code Control Panel")
            st.write(f"🗓️ Today: {today_date}")

            conn = sqlite3.connect("code.db")
            c = conn.cursor()

            c.execute("""
                SELECT code FROM daily_codes 
                WHERE class_name=? AND subject=? AND date=? AND status='active'
            """, (class_name.strip(), subject.strip(), today_date))
            active_code = c.fetchone()

            if active_code:
                st.success(f"✅ Current Active Code: **{active_code[0]}**")
            else:
                st.warning("⚠️ No active code for today yet.")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Generate New Code", key="force_gen_code"):
                    new_code = str(randint(100000, 999999))
                    c.execute("""
                        DELETE FROM daily_codes 
                        WHERE class_name=? AND subject=? AND date=?
                    """, (class_name.strip(), subject.strip(), today_date))
                    c.execute("""
                        INSERT INTO daily_codes (class_name, subject, code, status, generated_by, date, time)
                        VALUES (?, ?, ?, 'active', ?, ?, ?)
                    """, (class_name.strip(), subject.strip(), new_code, username, today_date, current_time))
                    conn.commit()
                    st.success(f"🔁 New code generated: **{new_code}**")

            with col2:
                if st.button("🚩 Stop Code", key="stop_code"):
                    c.execute("""
                        DELETE FROM daily_codes 
                        WHERE class_name=? AND subject=? AND date=?
                    """, (class_name.strip(), subject.strip(), today_date))
                    conn.commit()
                    st.warning("🗑️ Code has been permanently deleted for today.")

            conn.close()

            teacher_dashboard_addons(class_name, subject, today_date)

        elif role == "Student":
            st.subheader("🎯 Enter Today's Code")
            input_code = st.text_input("🔢 Enter 6-digit Code").strip()

            if st.button("Submit Code", key="submit_code"):
                conn = sqlite3.connect("code.db")
                c = conn.cursor()
                c.execute("""
                    SELECT code FROM daily_codes 
                    WHERE LOWER(class_name)=? AND LOWER(subject)=? AND date=? AND status='active'
                """, (class_name.strip().lower(), subject.strip().lower(), today_date))
                result = c.fetchone()
                conn.close()

                if result and input_code == result[0]:
                    conn = sqlite3.connect("attendance.db")
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO attendance (name, roll_no, date, time, status, username, class, subject)
                        VALUES (?, ?, ?, ?, 'Present', ?, ?, ?)
                    """, (name, roll_no, today_date, current_time, username, class_name.strip(), subject.strip()))
                    conn.commit()
                    conn.close()
                    st.success("✅ Attendance marked as Present!")
                elif not result:
                    st.error("⚠️ No code generated today for this class and subject.")
                else:
                    st.error("❌ Invalid or expired code.")

            student_dashboard_addons(username)

st.markdown("<hr style='margin-top: 40px;'>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; font-size:13px; color:gray;'>© 2025 Published by Aju Krishna</p>", unsafe_allow_html=True)

if __name__ == '__main__':
    main()

