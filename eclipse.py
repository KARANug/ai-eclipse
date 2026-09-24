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

if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None

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

    cursor.execute(
        "SELECT id FROM users WHERE username = %s",
        (username,)
    )

    if cursor.fetchone():
        cursor.close()
        db.close()
        return False, "Username already exists."

    cursor.execute(
        "SELECT id FROM users WHERE email = %s",
        (email,)
    )

    if cursor.fetchone():
        cursor.close()
        db.close()
        return False, "Email already registered."

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

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
    st.session_state.current_conversation_id = None
    st.session_state.messages = []

    st.rerun()


# =========================================================
# CREATE NEW CONVERSATION
# =========================================================

def create_conversation(user_id, title="New Chat"):

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO conversations
        (user_id, title)
        VALUES
        (%s, %s)
        """,
        (user_id, title)
    )

    db.commit()

    conversation_id = cursor.lastrowid

    cursor.close()
    db.close()

    return conversation_id


# =========================================================
# GET USER CONVERSATIONS
# =========================================================

def get_user_conversations(user_id):

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE user_id = %s
        ORDER BY updated_at DESC, id DESC
        """,
        (user_id,)
    )

    conversations = cursor.fetchall()

    cursor.close()
    db.close()

    return conversations


# =========================================================
# LOAD CONVERSATION
# =========================================================

def load_conversation(conversation_id, user_id):

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Make sure this conversation belongs to this user
    cursor.execute(
        """
        SELECT id, title
        FROM conversations
        WHERE id = %s
        AND user_id = %s
        """,
        (conversation_id, user_id)
    )

    conversation = cursor.fetchone()

    if not conversation:

        cursor.close()
        db.close()

        return None, []

    cursor.execute(
        """
        SELECT user_message, bot_response
        FROM chat_history
        WHERE conversation_id = %s
        AND user_id = %s
        ORDER BY id ASC
        """,
        (conversation_id, user_id)
    )

    history = cursor.fetchall()

    cursor.close()
    db.close()

    messages = []

    for item in history:

        messages.append(
            {
                "role": "user",
                "content": item["user_message"]
            }
        )

        messages.append(
            {
                "role": "assistant",
                "content": item["bot_response"]
            }
        )

    return conversation, messages


# =========================================================
# SAVE CHAT MESSAGE
# =========================================================

def save_chat_message(
    user_id,
    conversation_id,
    user_message,
    bot_response
):

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO chat_history
        (user_id, conversation_id, user_message, bot_response)
        VALUES
        (%s, %s, %s, %s)
        """,
        (
            user_id,
            conversation_id,
            user_message,
            bot_response
        )
    )

    cursor.execute(
        """
        UPDATE conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        AND user_id = %s
        """,
        (
            conversation_id,
            user_id
        )
    )

    db.commit()

    cursor.close()
    db.close()


# =========================================================
# UPDATE CONVERSATION TITLE
# =========================================================

def update_conversation_title(
    conversation_id,
    user_id,
    title
):

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        """
        UPDATE conversations
        SET title = %s
        WHERE id = %s
        AND user_id = %s
        """,
        (
            title,
            conversation_id,
            user_id
        )
    )

    db.commit()

    cursor.close()
    db.close()


# =========================================================
# DELETE CONVERSATION
# =========================================================

def delete_conversation(
    conversation_id,
    user_id
):

    db = get_db_connection()
    cursor = db.cursor()

    # Delete messages first
    cursor.execute(
        """
        DELETE FROM chat_history
        WHERE conversation_id = %s
        AND user_id = %s
        """,
        (
            conversation_id,
            user_id
        )
    )

    # Delete conversation
    cursor.execute(
        """
        DELETE FROM conversations
        WHERE id = %s
        AND user_id = %s
        """,
        (
            conversation_id,
            user_id
        )
    )

    db.commit()

    cursor.close()
    db.close()


# =========================================================
# USER CHATBOT
# =========================================================

def show_user_chatbot():

    # -----------------------------------------------------
    # SIDEBAR
    # -----------------------------------------------------

    with st.sidebar:

        st.title("🤖 Eclipse AI")

        st.write(
            f"👋 {st.session_state.username}"
        )

        st.divider()

        # New chat
        if st.button(
            "➕ New Chat",
            use_container_width=True
        ):

            conversation_id = create_conversation(
                st.session_state.user_id
            )

            st.session_state.current_conversation_id = conversation_id
            st.session_state.messages = []

            st.rerun()

        st.divider()

        st.subheader("🕘 Recent Chats")

        conversations = get_user_conversations(
            st.session_state.user_id
        )

        if conversations:

            for conversation in conversations:

                title = conversation["title"]

                if len(title) > 28:
                    title = title[:28] + "..."

                # Conversation button
                if st.button(
                    f"💬 {title}",
                    key=f"chat_{conversation['id']}",
                    use_container_width=True
                ):

                    loaded_conversation, messages = load_conversation(
                        conversation["id"],
                        st.session_state.user_id
                    )

                    if loaded_conversation:

                        st.session_state.current_conversation_id = (
                            loaded_conversation["id"]
                        )

                        st.session_state.messages = messages

                        st.rerun()

        else:

            st.caption(
                "No conversations yet."
            )

        st.divider()

        # Delete current conversation
        if st.session_state.current_conversation_id:

            if st.button(
                "🗑️ Delete Current Chat",
                use_container_width=True
            ):

                delete_conversation(
                    st.session_state.current_conversation_id,
                    st.session_state.user_id
                )

                st.session_state.current_conversation_id = None
                st.session_state.messages = []

                st.rerun()

        st.divider()

        if st.button(
            "🚪 Logout",
            use_container_width=True
        ):

            user_logout()

    # -----------------------------------------------------
    # MAIN CHAT AREA
    # -----------------------------------------------------

    st.title("🤖 Eclipse AI")

    st.caption(
        f"Logged in as {st.session_state.username}"
    )

    # -----------------------------------------------------
    # DISPLAY MESSAGES
    # -----------------------------------------------------

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(
                message["content"]
            )

    # -----------------------------------------------------
    # CHAT INPUT
    # -----------------------------------------------------

    prompt = st.chat_input(
        "Ask me anything..."
    )

    if prompt:

        # Create conversation automatically
        # if this is the first message
        if st.session_state.current_conversation_id is None:

            conversation_id = create_conversation(
                st.session_state.user_id,
                prompt[:60]
            )

            st.session_state.current_conversation_id = (
                conversation_id
            )

        else:

            conversation_id = (
                st.session_state.current_conversation_id
            )

        # Display user message
        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt
            }
        )

        with st.chat_message("user"):

            st.markdown(prompt)

        # -------------------------------------------------
        # GEMINI
        # -------------------------------------------------

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

        # -------------------------------------------------
        # SAVE MESSAGE IN SESSION
        # -------------------------------------------------

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        # -------------------------------------------------
        # SAVE TO DATABASE
        # -------------------------------------------------

        try:

            save_chat_message(
                st.session_state.user_id,
                conversation_id,
                prompt,
                answer
            )

            # First message becomes title
            if len(st.session_state.messages) == 2:

                title = prompt.strip()

                if len(title) > 60:

                    title = title[:60] + "..."

                update_conversation_title(
                    conversation_id,
                    st.session_state.user_id,
                    title
                )

        except Exception:

            st.warning(
                "⚠️ Response generated, "
                "but chat could not be saved."
            )

        # -------------------------------------------------
        # DISPLAY AI RESPONSE
        # -------------------------------------------------

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
                    st.session_state.current_conversation_id = None
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

    cursor.execute(
        "SELECT COUNT(*) AS total FROM users"
    )

    total_users = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM users
        WHERE status = 'active'
        """
    )

    active_users = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM users
        WHERE status = 'disabled'
        """
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
        st.metric(
            "👥 Total Users",
            total_users
        )

    with col2:
        st.metric(
            "🟢 Active Users",
            active_users
        )

    with col3:
        st.metric(
            "🔴 Disabled Users",
            disabled_users
        )

    with col4:
        st.metric(
            "💬 Total Chats",
            total_chats
        )

    st.divider()

    # -----------------------------------------------------
    # USER MANAGEMENT
    # -----------------------------------------------------

    st.subheader("👥 User Management")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            username,
            email,
            role,
            status,
            created_at
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

        st.info(
            "No users found."
        )

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
            SELECT
                id,
                username,
                email,
                role,
                status,
                created_at
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

            st.warning(
                "No matching user found."
            )

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
        [
            "active",
            "disabled"
        ]
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
                (
                    new_status,
                    username_status
                )
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

            st.warning(
                "Please enter a username."
            )

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
                DELETE FROM conversations
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

            st.warning(
                "Please enter a username."
            )

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
                    c.title,
                    h.user_message,
                    h.bot_response,
                    h.created_at
                FROM chat_history h
                JOIN users u
                    ON h.user_id = u.id
                JOIN conversations c
                    ON h.conversation_id = c.id
                WHERE u.username = %s
                ORDER BY h.created_at DESC
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

            st.warning(
                "Please enter a username."
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
