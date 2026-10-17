import os
import streamlit as st
from utils import get_client, is_admin

st.set_page_config(page_title="Salle de jeux", page_icon="🎮")

# (fichier, titre, icône, clé de page activable, réservé aux admins)
PAGES = [
    ("views/accueil.py", "Accueil", "🏠", None, False),
    ("views/depots.py", "Dépôts et budget", "💰", "depots", True),
    ("views/materiel.py", "Matériel", "🧰", "materiel", True),
    ("views/finances.py", "Ventes et dépenses", "📊", "finances", False),
    ("views/rentabilite.py", "Rentabilité", "📈", "finances", True),
    ("views/clients.py", "Clients", "👥", "clients", False),
    ("views/salle.py", "Salle", "🎮", "salle", False),
    ("views/reglages.py", "Réglages", "⚙️", None, True),
    ("views/journal.py", "Journal", "📝", None, True),
]


def login_form():
    st.title("🎮 Salle de jeux")
    with st.form("login"):
        email = st.text_input("Email")
        pwd = st.text_input("Mot de passe", type="password")
        ok = st.form_submit_button("Se connecter")
    if ok:
        sb = get_client()
        try:
            res = sb.auth.sign_in_with_password(
                {"email": email.strip(), "password": pwd}
            )
            prof = (
                sb.table("profiles")
                .select("*")
                .eq("id", res.user.id)
                .single()
                .execute()
                .data
            )
            st.session_state["profile"] = prof
            st.rerun()
        except Exception:
            st.error("Email ou mot de passe incorrect.")


if "profile" not in st.session_state:
    login_form()
    st.stop()

sb = get_client()
profile = st.session_state["profile"]

pages_actives = {}
if is_admin():
    try:
        pages_actives = (
            sb.table("settings")
            .select("pages_actives")
            .eq("id", 1)
            .single()
            .execute()
            .data["pages_actives"]
        )
    except Exception:
        pages_actives = {}

pages = []
for fichier, titre, icone, cle, admin_only in PAGES:
    if not os.path.exists(fichier):
        continue
    if admin_only and not is_admin():
        continue
    if cle and pages_actives.get(cle, True) is False:
        continue
    pages.append(st.Page(fichier, title=titre, icon=icone))

nav = st.navigation(pages)

with st.sidebar:
    st.caption(f"Connecté : {profile['nom']} ({profile['role']})")
    if st.button("Se déconnecter"):
        try:
            sb.auth.sign_out()
        except Exception:
            pass
        st.session_state.clear()
        st.rerun()

nav.run()
