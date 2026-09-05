"""
Authentication for the Wedding Expense Tracker.

Supports three separate passphrases (Groom, Bride, Admin), read
from environment variables / Streamlit secrets — never hardcoded
and never logged or displayed.
"""

import hashlib
import os

import streamlit as st

from config import ROLE_ADMIN, ROLE_BRIDE, ROLE_GROOM, ROLE_LABELS

# Env var / secrets key names, per role.
_PASSPHRASE_KEYS = {
    ROLE_GROOM: "GROOM_PASSPHRASE",
    ROLE_BRIDE: "BRIDE_PASSPHRASE",
    ROLE_ADMIN: "ADMIN_PASSPHRASE",
}


def _read_secret(key):
    """
    Reads a secret from `st.secrets` first (Streamlit Cloud /
    .streamlit/secrets.toml), falling back to an environment
    variable for local use. Never raises if missing.
    """

    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        # st.secrets raises if no secrets file exists at all locally.
        pass

    return os.getenv(key)


def get_configured_passphrases():
    """Returns {role: passphrase_or_None} without ever printing them."""

    return {
        role: _read_secret(key) for role, key in _PASSPHRASE_KEYS.items()
    }


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _match_role(passphrase):
    """
    Compares the entered passphrase (by hash) against each
    configured role passphrase. Returns the matching role, or None.
    """

    configured = get_configured_passphrases()

    for role, configured_value in configured.items():
        if configured_value and _hash(passphrase) == _hash(configured_value):
            return role

    return None


def is_authenticated():
    return bool(st.session_state.get("authenticated"))


def current_role():
    return st.session_state.get("role")


def logout():
    st.session_state.authenticated = False
    st.session_state.role = None


def login():
    """
    Renders the login screen. Returns True once authenticated
    (and stops rendering the login form on subsequent reruns).
    """

    if is_authenticated():
        return True

    st.markdown(
        """
        <div style="text-align:center; padding:60px 0 20px 0;">
            <h1>💍 Wedding Expense Tracker</h1>
            <p>Private Wedding Expense Management</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        configured = get_configured_passphrases()

        if not any(configured.values()):
            st.error(
                "No passphrases are configured. Please set "
                "GROOM_PASSPHRASE, BRIDE_PASSPHRASE and "
                "ADMIN_PASSPHRASE via environment variables or "
                "Streamlit secrets."
            )
            return False

        with st.form("login_form"):
            passphrase = st.text_input(
                "Enter your passphrase",
                type="password",
                placeholder="Groom / Bride / Admin passphrase",
                help="Use the passphrase given to your side of the family, "
                "or the admin passphrase if you manage the tracker.",
            )

            submitted = st.form_submit_button(
                "🔓 Unlock Expense Tracker",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not passphrase:
                st.error("Please enter a passphrase.")
                return False

            role = _match_role(passphrase)

            if role:
                st.session_state.authenticated = True
                st.session_state.role = role
                st.success(f"Welcome, {ROLE_LABELS[role]}!")
                st.rerun()
            else:
                st.error("Incorrect passphrase.")

    return False
