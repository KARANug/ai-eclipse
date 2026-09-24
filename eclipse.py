import streamlit as st
import mysql.connector
import bcrypt
from google import genai


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Eclipse AI",
    page_icon="🤖",
    layout="wide"
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    return mysql.connector.connect(
        host=st.secrets["TIDB_HOST"],
        port=st.secrets["TIDB_PORT"],
        user=st.secrets["TIDB_USER"],
        password=st.secrets["TIDB_PASSWORD"],
        database=st.secrets["TIDB_DATABASE"],
        ssl_ca=st.secrets["TIDB_CA"]
    )


# =========================================================
# GEMINI CONNECTION
# =========================================================

API_KEY = st.secrets["GEMINI_API_KEY"]

client = genai.Client(api_key=API_KEY)


# =========================================================
# SESSION STATE
# =========================================================

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if "admin_username" not in st.session_state:
    st.session_state.admin_username = None

if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = None

if "messages" not in st.session_state:
    st.session_state.messages = []


# =========================================================
# ADMIN LOGIN
# =========================================================

def admin_login(username, password):

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, username, password_hash, role, status
        FROM users
        WHERE username = %s
        """,
        (username,)
    )

    user = cursor.fetchone()

    cursor.close()
    db.close()

    if not user:
        return False, "Username not found."

    if user["role"] != "admin":
        return False, "This account is not an admin account."

    if user["status"] != "active":
        return False, "This admin account is disabled."

    password_correct = bcrypt.checkpw(
        password.encode("utf-8"),
        user["password_hash"].encode("utf-8")
    )

    if password_correct:
        return True, "Login successful."

    return False, "Incorrect password."


# =========================================================
# USER REGISTRATION
# =========================================================

def register_user(username, email, password):

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Check username
    cursor.execute(
        "SELECT id FROM users WHERE username = %s",
        (username,)
    )

    if cursor.fetchone():
        cursor.close()
        db.close()
        return False, "Username already exists."

    # Check email
    cursor.execute(
        "SELECT id FROM users WHERE email = %s",
        (email,)
    )

    if cursor.fetchone():
        cursor.close()
        db.close()
        return False, "Email already registered."

    # Hash password
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # Insert user
    cursor.execute(
        """
        INSERT INTO users
        (username, email, password_hash, role, status)
        VALUES
        (%s, %s, %s, 'user', 'active')
        """,
        (username, email, password_hash)
    )

    db.commit()

    cursor.close()
    db.close()

    return True, "Registration successful."


# =========================================================
# USER LOGIN
# =========================================================

def user_login(username, password):

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, username, password_hash, role, status
        FROM users
        WHERE username = %s
        """,
        (username,)
    )

    user = cursor.fetchone()

    cursor.close()
    db.close()

    if not user:
        return False, None, "Username not found."

    if user["role"] != "user":
        return False, None, "Please use the Admin Login."

    if user["status"] != "active":
        return False, None, "Your account has been disabled by the administrator."

    password_correct = bcrypt.checkpw(
        password.encode("utf-8"),
        user["password_hash"].encode("utf-8")
    )

    if not password_correct:
        return False, None, "Incorrect password."

    return True, user["id"], "Login successful."


# =========================================================
# USER LOGOUT
# =========================================================

def user_logout():

    st.session_state.user_logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.messages = []

    st.rerun()


# =========================================================
# ADMIN DASHBOARD
# =========================================================

def show_admin_dashboard():

    st.title("🛠️ Eclipse AI - Admin Dashboard")

    st.write(
        f"Welcome, **{st.session_state.admin_username}** 👋"
    )

    st.divider()

    if st.button("🚪 Admin Logout"):

        st.session_state.admin_logged_in = False
        st.session_state.admin_username = None

        st.rerun()

    st.divider()

    # -----------------------------------------------------
    # STATISTICS
    # -----------------------------------------------------

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM users")
    total_users = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM users WHERE status = 'active'"
    )
    active_users = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM users WHERE status = 'disabled'"
    )
    disabled_users = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM chat_history"
    )
    total_chats = cursor.fetchone()["total"]

    cursor.close()
    db.close()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("👥 Total Users", total_users)

    with col2:
        st.metric("🟢 Active Users", active_users)

    with col3:
        st.metric("🔴 Disabled Users", disabled_users)

    with col4:
        st.metric("💬 Total Chats", total_chats)

    st.divider()

    # -----------------------------------------------------
    # USER MANAGEMENT
    # -----------------------------------------------------

    st.subheader("👥 User Management")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, username, email, role, status, created_at
        FROM users
        ORDER BY id DESC
        """
    )

    users = cursor.fetchall()

    cursor.close()
    db.close()

    if users:

        st.dataframe(
            users,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("No users found.")

    st.divider()

    # -----------------------------------------------------
    # SEARCH USER
    # -----------------------------------------------------

    st.subheader("🔎 Search User")

    search_username = st.text_input(
        "Enter username"
    )

    if search_username:

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, username, email, role, status, created_at
            FROM users
            WHERE username LIKE %s
            """,
            (f"%{search_username}%",)
        )

        search_results = cursor.fetchall()

        cursor.close()
        db.close()

        if search_results:

            st.dataframe(
                search_results,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning("No matching user found.")

    st.divider()

    # -----------------------------------------------------
    # ENABLE / DISABLE USER
    # -----------------------------------------------------

    st.subheader("🟢🔴 Change User Status")

    username_status = st.text_input(
        "Username",
        key="status_username"
    )

    new_status = st.selectbox(
        "Select status",
        ["active", "disabled"]
    )

    if st.button("Update Status"):

        if username_status:

            db = get_db_connection()
            cursor = db.cursor()

            cursor.execute(
                """
                UPDATE users
                SET status = %s
                WHERE username = %s
                AND role != 'admin'
                """,
                (new_status, username_status)
            )

            db.commit()

            affected_rows = cursor.rowcount

            cursor.close()
            db.close()

            if affected_rows > 0:

                st.success(
                    f"User '{username_status}' status changed to '{new_status}'."
                )

                st.rerun()

            else:

                st.warning(
                    "User not found, or admin accounts cannot be changed here."
                )

        else:

            st.warning("Please enter a username.")

    st.divider()

    # -----------------------------------------------------
    # DELETE USER
    # -----------------------------------------------------

    st.subheader("🗑️ Delete User")

    delete_username = st.text_input(
        "Username to delete",
        key="delete_username"
    )

    if st.button("Delete User"):

        if delete_username:

            db = get_db_connection()
            cursor = db.cursor()

            cursor.execute(
                """
                DELETE FROM chat_history
                WHERE user_id = (
                    SELECT id
                    FROM users
                    WHERE username = %s
                    AND role != 'admin'
                )
                """,
                (delete_username,)
            )

            cursor.execute(
                """
                DELETE FROM users
                WHERE username = %s
                AND role != 'admin'
                """,
                (delete_username,)
            )

            db.commit()

            affected_rows = cursor.rowcount

            cursor.close()
            db.close()

            if affected_rows > 0:

                st.success(
                    f"User '{delete_username}' deleted successfully."
                )

                st.rerun()

            else:

                st.warning(
                    "User not found, or admin accounts cannot be deleted."
                )

        else:

            st.warning("Please enter a username.")

    st.divider()

    # -----------------------------------------------------
    # CHAT HISTORY
    # -----------------------------------------------------

    st.subheader("💬 User Chat History")

    history_username = st.text_input(
        "Enter username to view chat history",
        key="history_username"
    )

    if st.button("View Chat History"):

        if history_username:

            db = get_db_connection()
            cursor = db.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT
                    u.username,
                    c.user_message,
                    c.bot_response,
                    c.created_at
                FROM chat_history c
                JOIN users u
                ON c.user_id = u.id
                WHERE u.username = %s
                ORDER BY c.created_at DESC
                """,
                (history_username,)
            )

            history = cursor.fetchall()

            cursor.close()
            db.close()

            if history:

                st.dataframe(
                    history,
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info(
                    "No chat history found for this user."
                )

        else:

            st.warning("Please enter a username.")


# =========================================================
# USER CHATBOT
# =========================================================

def show_user_chatbot():

    st.title("🤖 Eclipse AI")

    st.write(
        f"Welcome, **{st.session_state.username}**! 👋"
    )

    if st.button("🚪 Logout"):

        user_logout()

    st.divider()

    # -----------------------------------------------------
    # DISPLAY CHAT
    # -----------------------------------------------------

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

    # -----------------------------------------------------
    # CHAT INPUT
    # -----------------------------------------------------

    prompt = st.chat_input(
        "Ask me anything..."
    )

    if prompt:

        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt
            }
        )

        with st.chat_message("user"):

            st.markdown(prompt)

        try:

            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt
            )

            answer = response.text

        except Exception as e:

            error_text = str(e)

            if "503" in error_text or "UNAVAILABLE" in error_text:

                answer = (
                    "⚠️ Gemini is temporarily busy right now. "
                    "Please try again in a few seconds."
                )

            elif "401" in error_text or "UNAUTHENTICATED" in error_text:

                answer = (
                    "🔐 Gemini authentication failed. "
                    "Please check the API key in Streamlit Secrets."
                )

            elif "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:

                answer = (
                    "⏳ Gemini API limit reached. "
                    "Please try again later."
                )

            else:

                answer = f"❌ Error: {error_text}"

        # Save response in session
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        # Save chat to database
        try:

            db = get_db_connection()
            cursor = db.cursor()

            cursor.execute(
                """
                INSERT INTO chat_history
                (user_id, user_message, bot_response)
                VALUES
                (%s, %s, %s)
                """,
                (
                    st.session_state.user_id,
                    prompt,
                    answer
                )
            )

            db.commit()

            cursor.close()
            db.close()

        except Exception as e:

            st.warning(
                "⚠️ Chat response was generated, but it could not be saved to the database."
            )

        with st.chat_message("assistant"):

            st.markdown(answer)


# =========================================================
# USER REGISTRATION PAGE
# =========================================================

def show_registration():

    st.title("📝 Create an Eclipse AI Account")

    username = st.text_input(
        "Username"
    )

    email = st.text_input(
        "Email"
    )

    password = st.text_input(
        "Password",
        type="password"
    )

    confirm_password = st.text_input(
        "Confirm Password",
        type="password"
    )

    if st.button("Create Account"):

        if not username or not email or not password:

            st.warning(
                "Please fill in all fields."
            )

        elif password != confirm_password:

            st.error(
                "Passwords do not match."
            )

        elif len(password) < 6:

            st.warning(
                "Password must contain at least 6 characters."
            )

        else:

            try:

                success, message = register_user(
                    username,
                    email,
                    password
                )

                if success:

                    st.success(message)

                    st.info(
                        "You can now go to User Login and sign in."
                    )

                else:

                    st.error(message)

            except Exception as e:

                st.error(
                    "Registration error:"
                )

                st.code(
                    str(e)
                )


# =========================================================
# USER LOGIN PAGE
# =========================================================

def show_user_login():

    st.title("🔐 User Login")

    username = st.text_input(
        "Username",
        key="user_login_username"
    )

    password = st.text_input(
        "Password",
        type="password",
        key="user_login_password"
    )

    if st.button("Login"):

        if not username or not password:

            st.warning(
                "Please enter username and password."
            )

        else:

            try:

                success, user_id, message = user_login(
                    username,
                    password
                )

                if success:

                    st.session_state.user_logged_in = True
                    st.session_state.user_id = user_id
                    st.session_state.username = username
                    st.session_state.messages = []

                    st.success(message)

                    st.rerun()

                else:

                    st.error(message)

            except Exception as e:

                st.error(
                    "Login error:"
                )

                st.code(
                    str(e)
                )


# =========================================================
# MAIN APPLICATION
# =========================================================

if st.session_state.admin_logged_in:

    show_admin_dashboard()

elif st.session_state.user_logged_in:

    show_user_chatbot()

else:

    st.sidebar.title("🤖 Eclipse AI")

    page = st.sidebar.radio(
        "Navigation",
        [
            "🔐 User Login",
            "📝 Register",
            "🔑 Admin Login"
        ]
    )

    if page == "🔐 User Login":

        show_user_login()

    elif page == "📝 Register":

        show_registration()

    elif page == "🔑 Admin Login":

        st.title("🔑 Admin Login")

        username = st.text_input(
            "Admin Username"
        )

        password = st.text_input(
            "Admin Password",
            type="password"
        )

        if st.button("Admin Login"):

            if username and password:

                try:

                    success, message = admin_login(
                        username,
                        password
                    )

                    if success:

                        st.session_state.admin_logged_in = True
                        st.session_state.admin_username = username

                        st.success(message)

                        st.rerun()

                    else:

                        st.error(message)

                except Exception as e:

                    st.error(
                        "Admin login error:"
                    )

                    st.code(
                        str(e)
                    )

            else:

                st.warning(
                    "Please enter admin username and password."
                )
