import streamlit as st
import re
from db_mongodb import save_entry, get_entry, delete_entry

# =============================================================================
# Mock Database Layer
# =============================================================================
# In production, this would be replaced with actual MongoDB operations.
# Note: For MongoDB, additional NoSQL injection sanitization would be required.

if "db" not in st.session_state:
    st.session_state.db = {}


def sanitize_input(value: str) -> str:
    """
    Sanitize user input to prevent injection attacks.
    Strips whitespace, removes control characters, and escapes special chars.
    In production with MongoDB, additional sanitization for $ and . operators
    would be needed to prevent NoSQL injection.
    """
    if not isinstance(value, str):
        return ""
    value = value.strip()
    value = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", value)
    value = value.replace("<", "&lt;").replace(">", "&gt;")
    return value


def validate_email(email: str) -> bool:
    """
    Validate email format: must contain @ and a domain with at least one dot.
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


# def save_entry(email: str, show: str) -> None:
#     """
#     Save or overwrite an entry in the mock database.
#     Email serves as the unique key; submitting again overwrites the show.
#     """
#     st.session_state.db[email.lower()] = show


# def get_entry(email: str) -> str | None:
#     """
#     Retrieve the show for a given email, or None if not found.
#     """
#     return st.session_state.db.get(email.lower())


# def delete_entry(email: str) -> bool:
#     """
#     Delete an entry from the mock database.
#     Returns True if entry existed and was deleted, False otherwise.
#     """
#     email_key = email.lower()
#     if email_key in st.session_state.db:
#         del st.session_state.db[email_key]
#         return True
#     return False


# =============================================================================
# Broadway Shows List
# =============================================================================

SHOWS = [
    "ALADDIN",
    "BEETLEJUICE",
    "DEATH BECOMES HER",
    "MJ",
    "SIX",
    "STRANGER THINGS",
    "THE LION KING",
    "WICKED",
]

# =============================================================================
# Streamlit App
# =============================================================================

st.title("Broadway Lottery Entry")

st.info(
    "By submitting an entry, you will be automatically enrolled in the Broadway Direct lottery every day. "
    "Use **Cancel Entry** if you wish to opt out."
)

selected_show = st.selectbox(
    "Select a show:",
    options=SHOWS,
    index=0,
)

email_input = st.text_input(
    "Enter your email address:",
    placeholder="you@example.com",
)

col1, col2 = st.columns(2)

with col1:
    submit_clicked = st.button("Submit Entry", type="primary")

with col2:
    cancel_clicked = st.button("Cancel Entry")

if submit_clicked:
    sanitized_email = sanitize_input(email_input)

    if not sanitized_email:
        st.error("Please enter an email address.")
    elif not validate_email(sanitized_email):
        st.error("Please enter a valid email address (e.g., you@example.com).")
    else:
        existing_entry = get_entry(sanitized_email)
        save_entry(sanitized_email, selected_show)

        if existing_entry:
            st.success(
                f"You're signed up for {selected_show} with email: {sanitized_email}"
            )
            st.info(f"Your previous entry for {existing_entry} has been updated.")
        else:
            st.success(
                f"You're signed up for {selected_show} with email: {sanitized_email}"
            )

if cancel_clicked:
    sanitized_email = sanitize_input(email_input)

    if not sanitized_email:
        st.error("Please enter your email address to cancel your entry.")
    elif not validate_email(sanitized_email):
        st.error("Please enter a valid email address (e.g., you@example.com).")
    else:
        existing_entry = get_entry(sanitized_email)
        if existing_entry:
            delete_entry(sanitized_email)
            st.success(f"Your entry for {existing_entry} has been cancelled.")
        else:
            st.warning("No entry found for this email address.")
