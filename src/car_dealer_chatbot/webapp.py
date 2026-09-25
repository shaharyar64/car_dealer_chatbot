"""Streamlit web interface for the car dealer chatbot (temporary, session-based chat history).

Run with: streamlit run src/car_dealer_chatbot/webapp.py
"""

# Absolute imports: `streamlit run` executes this file as a script, not as a package module.
import streamlit as st

from car_dealer_chatbot.config import load_env
from car_dealer_chatbot.logging_config import setup_logging
from car_dealer_chatbot.repository import DataError
from car_dealer_chatbot.services.factory import AppServices, build_services
from car_dealer_chatbot.ui import session, theme
from car_dealer_chatbot.ui.chat_page import render_chat_page
from car_dealer_chatbot.ui.sidebar import render_sidebar

st.set_page_config(
    page_title=theme.APP_NAME,
    page_icon=":material/directions_car:",
    layout="centered",
    initial_sidebar_state="auto",  # open on desktop, collapsed on phones so the chat comes first
)


@st.cache_resource(show_spinner="Starting the assistant...")
def get_services() -> AppServices:
    """Build the services once per server process; shared by all visitors."""
    load_env()
    setup_logging()
    return build_services()


def main() -> None:
    try:
        services = get_services()
    except (ValueError, DataError) as exc:
        st.error(f"Could not start the chatbot: {exc}")
        st.stop()

    theme.apply_base()
    store = session.get_store()
    render_sidebar(services.chat, store)
    render_chat_page(services.chat, store)


main()
