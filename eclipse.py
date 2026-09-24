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
# ADMIN DASHBOARD
# =========================================================

def show_admin_dashboard():

    st.title("🛠️ Eclipse AI - Admin Dashboard")

    st.write(
        f"Welcome, **{st.session_state.admin_username}** 👋"
    )

    st.divider()

    # -----------------------------------------------------
    # LOGOUT
    # -----------------------------------------------------

    if st.button("🚪 Logout"):

        st.session_state.admin_logged_in = False
        st.session_state.admin_username = None

        st.rerun()

    st.divider()

    # -----------------------------------------------------
    # GET USER STATISTICS
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

    # -----------------------------------------------------
    # STATISTICS
    # -----------------------------------------------------

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

            # Delete user's chat history first
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

            # Delete user
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
# NORMAL CHATBOT
# =========================================================

def show_chatbot():

    st.title("🤖 Eclipse AI")

    st.write(
        "Your AI assistant — ask me anything!"
    )

    # -----------------------------------------------------
    # DISPLAY PREVIOUS MESSAGES
    # -----------------------------------------------------

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # -----------------------------------------------------
    # USER INPUT
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

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        with st.chat_message("assistant"):
            st.markdown(answer)


# =========================================================
# MAIN APPLICATION
# =========================================================

if st.session_state.admin_logged_in:

    show_admin_dashboard()

else:

    # Sidebar navigation
    st.sidebar.title("🤖 Eclipse AI")

    page = st.sidebar.radio(
        "Navigation",
        [
            "💬 AI Chat",
            "🔐 Admin Login"
        ]
    )

    # -----------------------------------------------------
    # AI CHAT
    # -----------------------------------------------------

    if page == "💬 AI Chat":

        show_chatbot()

    # -----------------------------------------------------
    # ADMIN LOGIN
    # -----------------------------------------------------

    elif page == "🔐 Admin Login":

        st.title("🔐 Admin Login")

        st.write(
            "Login using your administrator account."
        )

        username = st.text_input(
            "Username"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button("Login"):

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
                        "Login error:"
                    )

                    st.code(
                        str(e)
                    )

            else:

                st.warning(
                    "Please enter username and password."
                )
