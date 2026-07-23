import streamlit as st
from google import genai

# Replace with your Gemini API key
API_KEY = "AQ.Ab8RN6IlrNn6IwP7mHbuxm77dAtCSnLON8ggWY5D-mcCXnFnUQ"

client = genai.Client(api_key=API_KEY)

st.set_page_config(
    page_title="Eclipse AI",
    page_icon="🤖"
)

st.title("🤖 Eclipse AI")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
prompt = st.chat_input("Ask me anything...")

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
            contents=prompt,
        )

        answer = response.text

    except Exception as e:
        answer = f"❌ Error:\n\n{str(e)}"

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )

    with st.chat_message("assistant"):
        st.markdown(answer)
        