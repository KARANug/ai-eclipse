
import streamlit as st
from google import genai

st.set_page_config(page_title="Gemini Test")

API_KEY = st.secrets["GEMINI_API_KEY"]

try:
    client = genai.Client(api_key=API_KEY)

    models = list(client.models.list())

    st.success("✅ Gemini authentication is working!")

    st.write("Available models:")

    for model in models:
        st.write(model.name)

except Exception as e:
    st.error("❌ Gemini authentication failed")
    st.code(str(e))
