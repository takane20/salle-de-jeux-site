import streamlit as st
from supabase import create_client


def get_client():
    # Un client par session : chaque personne a sa propre connexion
    if "sb" not in st.session_state:
        st.session_state["sb"] = create_client(
            st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
        )
    return st.session_state["sb"]


def fcfa(x):
    try:
        return f"{int(round(float(x))):,}".replace(",", " ") + " FCFA"
    except Exception:
        return "0 FCFA"


def is_admin():
    p = st.session_state.get("profile")
    return bool(p and p.get("role") == "admin")
