import streamlit as st
from google import genai

# Get Gemini API key securely from Streamlit Secrets
API_KEY = st.secrets["GEMINI_API_KEY"]

# Create Gemini client
client = genai.Client(api_key=API_KEY)

# Page settings
st.set_page_config(
    page_title="Eclipse AI",
    page_icon="🤖"
)

st.title("🤖 Eclipse AI")


# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []


# Display previous chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# User input
prompt = st.chat_input("Ask me anything...")


if prompt:

    # Add user message to chat history
    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    try:

        # Send request to Gemini
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )

        answer = response.text

    except Exception as e:

        error_text = str(e)

        # Handle temporary Gemini server overload
        if "503" in error_text or "UNAVAILABLE" in error_text:
            answer = (
                "⚠️ Gemini is temporarily busy right now. "
                "Please try again in a few seconds."
            )

        # Handle authentication problems
        elif "401" in error_text or "UNAUTHENTICATED" in error_text:
            answer = (
                "🔐 Gemini authentication failed. "
                "Please check the API key in Streamlit Secrets."
            )

        # Handle quota problems
        elif "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            answer = (
                "⏳ Gemini API limit reached. "
                "Please try again later."
            )

        # Other errors
        else:
            answer = f"❌ Error: {error_text}"


    # Save assistant response
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )

    # Display assistant response
    with st.chat_message("assistant"):
        st.markdown(answer)
