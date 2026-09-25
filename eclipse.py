import streamlit as st
import mysql.connector
import bcrypt
from google import genai


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Eclipse AI",
    page_icon="🤖",
    layout="wide"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    return mysql.connector.connect(
        host=st.secrets["TIDB_HOST"],
        port=st.secrets["TIDB_PORT"],
        user=st.secrets["TIDB_USER"],
        password=st.secrets["TIDB_PASSWORD"],
        database=st.secrets["TIDB_DATABASE"],
        ssl_ca=st.secrets["TIDB_CA"]
    )


# ============================================================
# GEMINI CONNECTION
# ============================================================

API_KEY = st.secrets["GEMINI_API_KEY"]

client = genai.Client(api_key=API_KEY)


# ============================================================
# SESSION STATE
# ============================================================

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if "admin_username" not in st.session_state:
    st.session_state.admin_username = ""

if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = ""

if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "admin_history_user" not in st.session_state:
    st.session_state.admin_history_user = None


# ============================================================
# ADMIN LOGIN
# ============================================================

def admin_login(username, password):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE username = %s
        """,
        (username,)
    )

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        return False, "Admin account not found."

    if user["role"] != "admin":
        return False, "This account is not an admin account."

    if user["status"] != "active":
        return False, "This admin account is disabled."

    if bcrypt.checkpw(
        password.encode("utf-8"),
        user["password_hash"].encode("utf-8")
    ):
        return True, "Login successful."

    return False, "Incorrect password."


# ============================================================
# USER REGISTRATION
# ============================================================

def register_user(username, email, password):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id
        FROM users
        WHERE username = %s OR email = %s
        """,
        (username, email)
    )

    existing_user = cursor.fetchone()

    if existing_user:

        cursor.close()
        conn.close()

        return False, "Username or email already exists."

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    cursor.execute(
        """
        INSERT INTO users
        (
            username,
            email,
            password_hash,
            role,
            status
        )
        VALUES
        (
            %s,
            %s,
            %s,
            'user',
            'active'
        )
        """,
        (
            username,
            email,
            password_hash
        )
    )

    conn.commit()

    cursor.close()
    conn.close()

    return True, "Registration successful."


# ============================================================
# USER LOGIN
# ============================================================

def user_login(username, password):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE username = %s
        """,
        (username,)
    )

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        return False, None, "User not found."

    if user["role"] != "user":
        return False, None, "Admins must use Admin Login."

    if user["status"] != "active":
        return False, None, "Your account has been disabled."

    if bcrypt.checkpw(
        password.encode("utf-8"),
        user["password_hash"].encode("utf-8")
    ):
        return True, user["id"], "Login successful."

    return False, None, "Incorrect password."


# ============================================================
# USER LOGOUT
# ============================================================

def logout_user():

    st.session_state.user_logged_in = False
    st.session_state.user_id = None
    st.session_state.username = ""
    st.session_state.current_conversation_id = None
    st.session_state.messages = []

    st.rerun()


# ============================================================
# CREATE CONVERSATION
# ============================================================

def create_conversation(user_id, title="New Chat"):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO conversations
        (
            user_id,
            title
        )
        VALUES
        (
            %s,
            %s
        )
        """,
        (
            user_id,
            title
        )
    )

    conversation_id = cursor.lastrowid

    conn.commit()

    cursor.close()
    conn.close()

    return conversation_id


# ============================================================
# GET USER CONVERSATIONS
# ============================================================

def get_user_conversations(user_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            title,
            created_at,
            updated_at
        FROM conversations
        WHERE user_id = %s
        ORDER BY updated_at DESC, id DESC
        """,
        (user_id,)
    )

    conversations = cursor.fetchall()

    cursor.close()
    conn.close()

    return conversations


# ============================================================
# LOAD CONVERSATION
# ============================================================

def load_conversation(conversation_id, user_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            title
        FROM conversations
        WHERE id = %s
        AND user_id = %s
        """,
        (
            conversation_id,
            user_id
        )
    )

    conversation = cursor.fetchone()

    if not conversation:

        cursor.close()
        conn.close()

        return None, []

    cursor.execute(
        """
        SELECT
            user_message,
            bot_response
        FROM chat_history
        WHERE conversation_id = %s
        AND user_id = %s
        ORDER BY id ASC
        """,
        (
            conversation_id,
            user_id
        )
    )

    history = cursor.fetchall()

    cursor.close()
    conn.close()

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


# ============================================================
# SAVE CHAT MESSAGE
# ============================================================

def save_chat_message(
    user_id,
    conversation_id,
    user_message,
    bot_response
):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO chat_history
        (
            user_id,
            conversation_id,
            user_message,
            bot_response
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s
        )
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

    conn.commit()

    cursor.close()
    conn.close()


# ============================================================
# UPDATE CONVERSATION TITLE
# ============================================================

def update_conversation_title(
    conversation_id,
    user_id,
    title
):

    conn = get_db_connection()
    cursor = conn.cursor()

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

    conn.commit()

    cursor.close()
    conn.close()


# ============================================================
# DELETE CONVERSATION
# ============================================================

def delete_conversation(
    conversation_id,
    user_id
):

    conn = get_db_connection()
    cursor = conn.cursor()

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

    conn.commit()

    cursor.close()
    conn.close()


# ============================================================
# BUILD GEMINI CONTEXT
# ============================================================

def build_gemini_context(messages, new_prompt):

    conversation_text = ""

    for message in messages:

        if message["role"] == "user":

            conversation_text += (
                "User: "
                + message["content"]
                + "\n"
            )

        elif message["role"] == "assistant":

            conversation_text += (
                "Eclipse AI: "
                + message["content"]
                + "\n"
            )

    conversation_text += (
        "User: "
        + new_prompt
        + "\n"
        "Eclipse AI:"
    )

    return conversation_text
# ============================================================
# GEMINI RESPONSE
# ============================================================

import time


def get_gemini_response(prompt, messages):

    context = build_gemini_context(
        messages,
        prompt
    )

    # ========================================================
    # GET ACTIVE API KEYS
    # ========================================================

    api_keys = get_active_api_keys()

    # ========================================================
    # IF NO DATABASE KEYS EXIST
    # USE STREAMLIT SECRET
    # ========================================================

    if not api_keys:

        api_keys = [
            {
                "id": None,
                "key_name": "Streamlit Secret",
                "api_key": st.secrets["GEMINI_API_KEY"]
            }
        ]

    # ========================================================
    # TRY EACH API KEY
    # ========================================================

    last_error = None

    for api_key_data in api_keys:

        api_key_id = api_key_data["id"]
        api_key_name = api_key_data["key_name"]
        api_key = api_key_data["api_key"]

        # ----------------------------------------------------
        # CREATE CLIENT FOR CURRENT KEY
        # ----------------------------------------------------

        try:

            current_client = genai.Client(
                api_key=api_key
            )

        except Exception as client_error:

            last_error = str(client_error)

            continue

        # ====================================================
        # RETRY CURRENT KEY
        # ====================================================

        max_retries = 3

        for attempt in range(max_retries):

            try:

                response = current_client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=context
                )

                # ------------------------------------------------
                # SUCCESS
                # ------------------------------------------------

                if response.text:

                    if api_key_id is not None:

                        update_api_key_last_used(
                            api_key_id
                        )

                    return response.text

                last_error = (
                    "Gemini returned an empty response."
                )

                break

            except Exception as error:

                error_text = str(error)

                last_error = error_text

                # ================================================
                # 503 - TEMPORARY SERVER / HIGH DEMAND
                # ================================================

                if "503" in error_text:

                    if attempt < max_retries - 1:

                        delay = 2 ** attempt

                        time.sleep(delay)

                        continue

                    # --------------------------------------------
                    # Current key exhausted
                    # Move to next API key
                    # --------------------------------------------

                    break

                # ================================================
                # 429 - RATE LIMIT / QUOTA
                # ================================================

                if "429" in error_text:

                    # Move to next API key
                    break

                # ================================================
                # 401 / 403 - AUTHENTICATION
                # ================================================

                if (
                    "401" in error_text
                    or
                    "403" in error_text
                    or
                    "authentication" in error_text.lower()
                    or
                    "api key" in error_text.lower()
                ):

                    # Current key is probably invalid
                    # Move to next key
                    break

                # ================================================
                # 404 - MODEL NOT FOUND
                # ================================================

                if "404" in error_text:

                    return (
                        "❌ Gemini model error.\n\n"
                        "The selected Gemini model "
                        "could not be found or is unavailable."
                    )

                # ================================================
                # OTHER ERROR
                # ================================================

                break

    # ========================================================
    # ALL DATABASE KEYS FAILED
    # ========================================================

    if last_error:

        if "503" in last_error:

            return (
                "⚠️ Gemini is currently experiencing "
                "high demand.\n\n"
                "I tried the available API keys and "
                "automatic retries, but Gemini is still "
                "temporarily unavailable.\n\n"
                "Please try again in a few seconds."
            )

        if "429" in last_error:

            return (
                "⚠️ Gemini API rate limit reached.\n\n"
                "The available API keys have reached "
                "their current quota or rate limit.\n\n"
                "Please try again later."
            )

        if (
            "401" in last_error
            or
            "403" in last_error
            or
            "authentication" in last_error.lower()
        ):

            return (
                "❌ Gemini authentication failed.\n\n"
                "Please check the API keys in the "
                "Admin Dashboard."
            )

        return (
            "❌ Something went wrong while "
            "connecting to Gemini.\n\n"
            + last_error
        )

    return (
        "⚠️ Gemini did not return a response.\n\n"
        "Please try again."
    )
# ============================================================
# API KEY MANAGEMENT
# ============================================================

def get_api_keys():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            key_name,
            api_key,
            status,
            created_at,
            last_used_at
        FROM api_keys
        ORDER BY id DESC
        """
    )

    api_keys = cursor.fetchall()

    cursor.close()
    conn.close()

    return api_keys


# ============================================================
# GET ACTIVE API KEYS
# ============================================================

def get_active_api_keys():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            key_name,
            api_key
        FROM api_keys
        WHERE status = 'active'
        ORDER BY
            last_used_at IS NULL DESC,
            last_used_at ASC,
            id ASC
        """
    )

    api_keys = cursor.fetchall()

    cursor.close()
    conn.close()

    return api_keys


# ============================================================
# UPDATE API KEY LAST USED
# ============================================================

def update_api_key_last_used(api_key_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE api_keys
        SET last_used_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (api_key_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()



def add_api_key(key_name, api_key):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO api_keys
        (
            key_name,
            api_key,
            status
        )
        VALUES
        (
            %s,
            %s,
            'active'
        )
        """,
        (
            key_name,
            api_key
        )
    )

    conn.commit()

    cursor.close()
    conn.close()


def toggle_api_key_status(api_key_id, new_status):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE api_keys
        SET status = %s
        WHERE id = %s
        """,
        (
            new_status,
            api_key_id
        )
    )

    conn.commit()

    cursor.close()
    conn.close()


def delete_api_key(api_key_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM api_keys
        WHERE id = %s
        """,
        (api_key_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()


def mask_api_key(api_key):
    if not api_key:
        return "••••••••"

    if len(api_key) <= 8:
        return "••••••••"

    return (
        api_key[:4]
        + "••••••••••••"
        + api_key[-4:]
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

def show_admin_dashboard():

    st.title("🛡️ Admin Dashboard")

    st.write(
        f"Welcome, **{st.session_state.admin_username}**"
    )

    if st.button("🚪 Admin Logout"):

        st.session_state.admin_logged_in = False
        st.session_state.admin_username = ""

        st.rerun()

    st.divider()

    # ========================================================
    # STATISTICS
    # ========================================================

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT COUNT(*) AS total_users
        FROM users
        WHERE role = 'user'
        """
    )

    total_users = cursor.fetchone()["total_users"]

    cursor.execute(
        """
        SELECT COUNT(*) AS active_users
        FROM users
        WHERE role = 'user'
        AND status = 'active'
        """
    )

    active_users = cursor.fetchone()["active_users"]

    cursor.execute(
        """
        SELECT COUNT(*) AS disabled_users
        FROM users
        WHERE role = 'user'
        AND status = 'disabled'
        """
    )

    disabled_users = cursor.fetchone()["disabled_users"]

    cursor.execute(
        """
        SELECT COUNT(*) AS total_chats
        FROM chat_history
        """
    )

    total_chats = cursor.fetchone()["total_chats"]

    cursor.close()
    conn.close()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "👥 Total Users",
        total_users
    )

    col2.metric(
        "🟢 Active Users",
        active_users
    )

    col3.metric(
        "🔴 Disabled Users",
        disabled_users
    )

    col4.metric(
        "💬 Total Chats",
        total_chats
    )

    st.divider()

    # ========================================================
    # API KEY MANAGEMENT
    # ========================================================

    st.subheader("🔑 API Key Management")

    st.caption(
        "Store and manage backup Gemini API keys. "
        "The actual keys are hidden from the admin interface."
    )

    # --------------------------------------------------------
    # ADD NEW API KEY
    # --------------------------------------------------------

    with st.form("add_api_key_form", clear_on_submit=True):

        st.markdown("### ➕ Add New API Key")

        new_key_name = st.text_input(
            "Key Name",
            placeholder="Example: Demo Key 1"
        )

        new_api_key = st.text_input(
            "Gemini API Key",
            type="password",
            placeholder="Paste the API key here"
        )

        add_key_submitted = st.form_submit_button(
            "➕ Add API Key",
            use_container_width=True
        )

        if add_key_submitted:

            if not new_key_name.strip():
                st.warning("Please enter a key name.")

            elif not new_api_key.strip():
                st.warning("Please enter the Gemini API key.")

            else:
                add_api_key(
                    new_key_name.strip(),
                    new_api_key.strip()
                )

                st.success(
                    f"API key '{new_key_name.strip()}' added successfully."
                )

                st.rerun()

    st.divider()

    # --------------------------------------------------------
    # DISPLAY SAVED API KEYS
    # --------------------------------------------------------

    api_keys = get_api_keys()

    if api_keys:

        st.markdown("### 📋 Saved API Keys")

        for api_key in api_keys:

            col1, col2, col3, col4 = st.columns(
                [2, 3, 1.5, 1.5]
            )

            with col1:
                st.write(
                    f"**{api_key['key_name']}**"
                )

            with col2:
                st.code(
                    mask_api_key(api_key["api_key"]),
                    language=None
                )

            with col3:

                if api_key["status"] == "active":

                    st.success("🟢 Active")

                else:

                    st.error("🔴 Disabled")

            with col4:

                if api_key["status"] == "active":

                    if st.button(
                        "Disable",
                        key=f"disable_api_key_{api_key['id']}",
                        use_container_width=True
                    ):

                        toggle_api_key_status(
                            api_key["id"],
                            "disabled"
                        )

                        st.rerun()

                else:

                    if st.button(
                        "Enable",
                        key=f"enable_api_key_{api_key['id']}",
                        use_container_width=True
                    ):

                        toggle_api_key_status(
                            api_key["id"],
                            "active"
                        )

                        st.rerun()

            info_col1, info_col2, info_col3 = st.columns(3)

            with info_col1:
                st.caption(
                    f"🆔 ID: {api_key['id']}"
                )

            with info_col2:
                st.caption(
                    f"📅 Created: {api_key['created_at']}"
                )

            with info_col3:

                if api_key["last_used_at"]:
                    st.caption(
                        f"🕒 Last used: {api_key['last_used_at']}"
                    )
                else:
                    st.caption("🕒 Last used: Never")

            delete_col1, delete_col2 = st.columns([6, 1])

            with delete_col2:

                if st.button(
                    "🗑️ Delete",
                    key=f"delete_api_key_{api_key['id']}",
                    use_container_width=True
                ):

                    delete_api_key(api_key["id"])

                    st.success(
                        f"API key '{api_key['key_name']}' deleted."
                    )

                    st.rerun()

            st.divider()

    else:

        st.info(
            "No API keys have been added yet. "
            "Add a Gemini API key above."
        )

    # ========================================================
    # USER MANAGEMENT
    # ========================================================

    st.subheader("👥 User Management")

    search = st.text_input(
        "🔎 Search user",
        placeholder="Enter username or email"
    )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if search:

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
            WHERE
                (
                    username LIKE %s
                    OR email LIKE %s
                )
                AND role = 'user'
            ORDER BY id DESC
            """,
            (
                "%" + search + "%",
                "%" + search + "%"
            )
        )

    else:

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
            WHERE role = 'user'
            ORDER BY id DESC
            """
        )

    users = cursor.fetchall()

    cursor.close()
    conn.close()

    if users:

        for user in users:

            st.markdown(
                f"### 👤 {user['username']}"
            )

            col1, col2, col3, col4 = st.columns(4)

            col1.write(
                f"📧 **Email:** {user['email']}"
            )

            col2.write(
                f"📌 **Status:** {user['status']}"
            )

            col3.write(
                f"🆔 **ID:** {user['id']}"
            )

            with col4:

                if user["status"] == "active":

                    if st.button(
                        "Disable",
                        key=f"disable_{user['id']}"
                    ):

                        conn = get_db_connection()
                        cursor = conn.cursor()

                        cursor.execute(
                            """
                            UPDATE users
                            SET status = 'disabled'
                            WHERE id = %s
                            AND role = 'user'
                            """,
                            (user["id"],)
                        )

                        conn.commit()

                        cursor.close()
                        conn.close()

                        st.rerun()

                else:

                    if st.button(
                        "Enable",
                        key=f"enable_{user['id']}"
                    ):

                        conn = get_db_connection()
                        cursor = conn.cursor()

                        cursor.execute(
                            """
                            UPDATE users
                            SET status = 'active'
                            WHERE id = %s
                            AND role = 'user'
                            """,
                            (user["id"],)
                        )

                        conn.commit()

                        cursor.close()
                        conn.close()

                        st.rerun()

            col5, col6 = st.columns(2)

            with col5:

                if st.button(
                    "🗑️ Delete User",
                    key=f"delete_{user['id']}"
                ):

                    conn = get_db_connection()
                    cursor = conn.cursor()

                    cursor.execute(
                        """
                        DELETE FROM chat_history
                        WHERE user_id = %s
                        """,
                        (user["id"],)
                    )

                    cursor.execute(
                        """
                        DELETE FROM conversations
                        WHERE user_id = %s
                        """,
                        (user["id"],)
                    )

                    cursor.execute(
                        """
                        DELETE FROM users
                        WHERE id = %s
                        AND role = 'user'
                        """,
                        (user["id"],)
                    )

                    conn.commit()

                    cursor.close()
                    conn.close()

                    st.rerun()

            with col6:

                if st.button(
                    "💬 View Chat History",
                    key=f"history_{user['id']}"
                ):

                    st.session_state.admin_history_user = (
                        user["username"]
                    )

            st.divider()

    else:

        st.info("No users found.")

    # ========================================================
    # CHAT HISTORY
    # ========================================================

    if st.session_state.admin_history_user:

        selected_user = (
            st.session_state.admin_history_user
        )

        st.subheader(
            f"💬 Chat History — {selected_user}"
        )

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

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
            (selected_user,)
        )

        history = cursor.fetchall()

        cursor.close()
        conn.close()

        if history:

            for item in history:

                st.markdown(
                    f"### 🗂️ {item['title']}"
                )

                st.write(
                    f"🕒 {item['created_at']}"
                )

                st.markdown(
                    f"**👤 User:** {item['user_message']}"
                )

                st.markdown(
                    f"**🤖 Eclipse AI:** {item['bot_response']}"
                )

                st.divider()

        else:

            st.info(
                "This user has no chat history."
            )


# ============================================================
# USER CHATBOT
# ============================================================

def show_user_chatbot():

    # ========================================================
    # SIDEBAR
    # ========================================================

    with st.sidebar:

        st.title("🤖 Eclipse AI")

        st.caption(
            f"Logged in as **{st.session_state.username}**"
        )

        st.divider()

        # ----------------------------------------------------
        # NEW CHAT
        # ----------------------------------------------------

        if st.button(
            "➕ New Chat",
            use_container_width=True
        ):

            st.session_state.current_conversation_id = None
            st.session_state.messages = []

            st.rerun()

        st.divider()

        # ----------------------------------------------------
        # RECENT CHATS
        # ----------------------------------------------------

        st.subheader("💬 Recent Chats")

        conversations = get_user_conversations(
            st.session_state.user_id
        )

        if conversations:

            for conversation in conversations:

                title = conversation["title"]

                if len(title) > 30:

                    title = title[:30] + "..."

                is_current = (
                    conversation["id"]
                    == st.session_state.current_conversation_id
                )

                if is_current:

                    button_text = "👉 " + title

                else:

                    button_text = "💬 " + title

                if st.button(
                    button_text,
                    key=f"conversation_{conversation['id']}",
                    use_container_width=True
                ):

                    (
                        loaded_conversation,
                        loaded_messages
                    ) = load_conversation(
                        conversation["id"],
                        st.session_state.user_id
                    )

                    if loaded_conversation:

                        st.session_state.current_conversation_id = (
                            loaded_conversation["id"]
                        )

                        st.session_state.messages = (
                            loaded_messages
                        )

                        st.rerun()

        else:

            st.caption(
                "No conversations yet."
            )

        # ----------------------------------------------------
        # DELETE CURRENT CHAT
        # ----------------------------------------------------

        if st.session_state.current_conversation_id:

            st.divider()

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

        # ----------------------------------------------------
        # LOGOUT
        # ----------------------------------------------------

        if st.button(
            "🚪 Logout",
            use_container_width=True
        ):

            logout_user()

    # ========================================================
    # MAIN CHAT
    # ========================================================

    st.title("🤖 Eclipse AI")

    st.caption(
        "Your AI assistant — ask me anything!"
    )

    st.divider()

    # ========================================================
    # DISPLAY EXISTING MESSAGES
    # ========================================================

    for message in st.session_state.messages:

        with st.chat_message(
            message["role"]
        ):

            st.markdown(
                message["content"]
            )

    # ========================================================
    # CHAT INPUT
    # ========================================================

    prompt = st.chat_input(
        "Message Eclipse AI..."
    )

    if prompt:

        # ====================================================
        # CREATE CONVERSATION
        # ====================================================

        is_first_message = (
            st.session_state.current_conversation_id
            is None
        )

        if is_first_message:

            title = prompt.strip()

            if len(title) > 60:

                title = title[:60] + "..."

            conversation_id = create_conversation(
                st.session_state.user_id,
                title
            )

            st.session_state.current_conversation_id = (
                conversation_id
            )

        else:

            conversation_id = (
                st.session_state.current_conversation_id
            )

        # ====================================================
        # SAVE USER MESSAGE IN SESSION
        # ====================================================

        previous_messages = (
            st.session_state.messages.copy()
        )

        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt
            }
        )

        # ====================================================
        # DISPLAY USER MESSAGE
        # ====================================================

        with st.chat_message("user"):

            st.markdown(prompt)

        # ====================================================
        # GET GEMINI RESPONSE
        # ====================================================

        with st.chat_message("assistant"):

            with st.spinner(
                "Thinking... 🤔"
            ):

                bot_response = get_gemini_response(
                    prompt,
                    previous_messages
                )

            st.markdown(
                bot_response
            )

        # ====================================================
        # SAVE ASSISTANT MESSAGE IN SESSION
        # ====================================================

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": bot_response
            }
        )

        # ====================================================
        # SAVE CHAT TO DATABASE
        # ====================================================

        save_chat_message(
            st.session_state.user_id,
            conversation_id,
            prompt,
            bot_response
        )

        # ====================================================
        # UPDATE TITLE
        # ====================================================

        if is_first_message:

            update_conversation_title(
                conversation_id,
                st.session_state.user_id,
                title
            )


# ============================================================
# MAIN APPLICATION
# ============================================================

if st.session_state.admin_logged_in:

    show_admin_dashboard()

elif st.session_state.user_logged_in:

    show_user_chatbot()

else:

    st.sidebar.title("🤖 Eclipse AI")

    page = st.sidebar.radio(
        "Menu",
        [
            "🔐 User Login",
            "📝 Register",
            "🔑 Admin Login"
        ]
    )

    # ========================================================
    # USER LOGIN
    # ========================================================

    if page == "🔐 User Login":

        st.title("🔐 User Login")

        username = st.text_input(
            "Username"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button(
            "Login",
            use_container_width=True
        ):

            if not username or not password:

                st.warning(
                    "Please enter username and password."
                )

            else:

                (
                    success,
                    user_id,
                    message
                ) = user_login(
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

    # ========================================================
    # REGISTRATION
    # ========================================================

    elif page == "📝 Register":

        st.title("📝 Create Account")

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

        if st.button(
            "Register",
            use_container_width=True
        ):

            if (
                not username
                or not email
                or not password
            ):

                st.warning(
                    "Please fill in all fields."
                )

            elif password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            elif len(password) < 6:

                st.error(
                    "Password must be at least 6 characters."
                )

            else:

                success, message = register_user(
                    username,
                    email,
                    password
                )

                if success:

                    st.success(
                        message
                    )

                    st.info(
                        "You can now go to User Login."
                    )

                else:

                    st.error(
                        message
                    )

    # ========================================================
    # ADMIN LOGIN
    # ========================================================

    elif page == "🔑 Admin Login":

        st.title("🔑 Admin Login")

        username = st.text_input(
            "Admin Username"
        )

        password = st.text_input(
            "Admin Password",
            type="password"
        )

        if st.button(
            "Admin Login",
            use_container_width=True
        ):

            if not username or not password:

                st.warning(
                    "Please enter admin username and password."
                )

            else:

                success, message = admin_login(
                    username,
                    password
                )

                if success:

                    st.session_state.admin_logged_in = True
                    st.session_state.admin_username = username

                    st.success(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )
