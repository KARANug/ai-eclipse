import streamlit as st
from google import genai
import mysql.connector
import bcrypt


# =========================================================
# PAGE SETTINGS
# =========================================================

st.set_page_config(
    page_title="Eclipse AI",
    page_icon="🤖"
)


# =========================================================
# GEMINI CONNECTION
# =========================================================

API_KEY = st.secrets["GEMINI_API_KEY"]

client = genai.Client(api_key=API_KEY)


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
# SESSION STATE
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = None

if "messages" not in st.session_state:
    st.session_state.messages = []


# =========================================================
# REGISTRATION
# =========================================================

def register_user(username, email, password):

    db = get_db_connection()
    cursor = db.cursor()

    # Check whether username/email already exists
    cursor.execute(
        "SELECT id FROM users WHERE username = %s OR email = %s",
        (username, email)
    )

    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        db.close()
        return False, "Username or email already exists."

    # Hash password
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # Insert user
    cursor.execute(
        """
        INSERT INTO users
        (username, email, password_hash)
        VALUES (%s, %s, %s)
        """,
        (username, email, password_hash)
    )

    db.commit()

    cursor.close()
    db.close()

    return True, "Registration successful!"


# =========================================================
# LOGIN
# =========================================================

def login_user(username, password):

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT id, username, password_hash
        FROM users
        WHERE username = %s
        """,
        (username,)
    )

    user = cursor.fetchone()

    cursor.close()
    db.close()

    if not user:
        return False, None, None

    user_id = user[0]
    stored_username = user[1]
    stored_password_hash = user[2]

    # Check password
    if bcrypt.checkpw(
        password.encode("utf-8"),
        stored_password_hash.encode("utf-8")
    ):

        return True, user_id, stored_username

    return False, None, None


# =========================================================
# LOGIN / REGISTER PAGE
# =========================================================

if not st.session_state.logged_in:

    st.title("🤖 Eclipse AI")

    login_tab, register_tab = st.tabs(
        ["🔐 Login", "📝 Register"]
    )


    # -----------------------------------------------------
    # LOGIN
    # -----------------------------------------------------

    with login_tab:

        st.subheader("Login")

        login_username = st.text_input(
            "Username",
            key="login_username"
        )

        login_password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button("Login", type="primary"):

            if not login_username or not login_password:

                st.warning("Please enter username and password.")

            else:

                success, user_id, username = login_user(
                    login_username,
                    login_password
                )

                if success:

                    st.session_state.logged_in = True
                    st.session_state.user_id = user_id
                    st.session_state.username = username

                    st.session_state.messages = []

                    st.success("Login successful!")

                    st.rerun()

                else:

                    st.error(
                        "❌ Invalid username or password."
                    )


    # -----------------------------------------------------
    # REGISTER
    # -----------------------------------------------------

    with register_tab:

        st.subheader("Create Account")

        register_username = st.text_input(
            "Username",
            key="register_username"
        )

        register_email = st.text_input(
            "Email",
            key="register_email"
        )

        register_password = st.text_input(
            "Password",
            type="password",
            key="register_password"
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            key="confirm_password"
        )

        if st.button("Create Account"):

            if not register_username or not register_email:

                st.warning(
                    "Please enter username and email."
                )

            elif not register_password:

                st.warning(
                    "Please enter a password."
                )

            elif register_password != confirm_password:

                st.error(
                    "❌ Passwords do not match."
                )

            else:

                success, message = register_user(
                    register_username,
                    register_email,
                    register_password
                )

                if success:

                    st.success(message)

                    st.info(
                        "You can now go to the Login tab."
                    )

                else:

                    st.error(message)


    st.stop()


# =========================================================
# LOGGED-IN CHATBOT
# =========================================================

st.title("🤖 Eclipse AI")

st.write(
    f"Welcome, **{st.session_state.username}**! 👋"
)


# Logout button

if st.button("🚪 Logout"):

    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.messages = []

    st.rerun()


st.divider()


# =========================================================
# DISPLAY PREVIOUS CHAT MESSAGES
# =========================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


# =========================================================
# USER INPUT
# =========================================================

prompt = st.chat_input(
    "Ask me anything..."
)


if prompt:

    # -----------------------------------------------------
    # DISPLAY USER MESSAGE
    # -----------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):

        st.markdown(prompt)


    # -----------------------------------------------------
    # SEND MESSAGE TO GEMINI
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # SAVE ASSISTANT RESPONSE
    # -----------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )


    # -----------------------------------------------------
    # DISPLAY ASSISTANT RESPONSE
    # -----------------------------------------------------

    with st.chat_message("assistant"):

        st.markdown(answer)


    # =====================================================
    # SAVE CHAT TO DATABASE
    # =====================================================

    try:

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            """
            INSERT INTO chat_history
            (user_id, user_message, bot_response)
            VALUES (%s, %s, %s)
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
            f"⚠️ Chat could not be saved to database: {e}"
        )
