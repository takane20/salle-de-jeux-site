import os

import streamlit as st

from utils import appliquer_couleur, get_branding, get_client, is_admin

brand = get_branding()
st.set_page_config(page_title=brand["nom"], page_icon="🎮")

import pages_argent  # noqa: E402
import pages_equipe  # noqa: E402
import pages_export  # noqa: E402
import pages_salle  # noqa: E402

# (page, titre, icône, clé activable depuis Réglages, réservé aux admins)
SECTIONS = {
    "": [
        (pages_argent.accueil, "Accueil", "🏠", None, False),
    ],
    "Argent": [
        ("views/depots.py", "Dépôts et budget", "💰", "depots", True),
        ("views/materiel.py", "Matériel", "🧰", "materiel", True),
        (pages_equipe.devis, "Comparateur de prix", "🛒", "materiel", True),
        (pages_argent.finances, "Ventes et dépenses", "📊", "finances", False),
        (pages_argent.caisse, "Caisse du jour", "🧾", "finances", False),
        (pages_argent.rentabilite, "Rentabilité", "📈", "finances", True),
    ],
    "Salle": [
        (pages_salle.clients, "Clients", "👥", "clients", False),
        (pages_salle.salle, "Salle", "🎮", "salle", False),
        (pages_equipe.taches, "Tâches", "✅", None, False),
    ],
    "Administration": [
        (pages_equipe.documents, "Documents", "📁", None, True),
        (pages_export.exports, "Exports et rapports", "📤", None, True),
        (pages_equipe.apparence, "Apparence", "🎨", None, True),
        ("views/reglages.py", "Réglages", "⚙️", None, True),
        (pages_equipe.journal, "Journal", "📝", None, True),
    ],
}


def login_form():
    if brand.get("logo_url"):
        st.image(brand["logo_url"], width=120)
    st.title(f"🎮 {brand['nom']}")
    if brand.get("slogan"):
        st.caption(brand["slogan"])
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


appliquer_couleur(brand["couleur"])

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

navigation = {}
for section, pages in SECTIONS.items():
    liste = []
    for cible, titre, icone, cle, admin_only in pages:
        if isinstance(cible, str) and not os.path.exists(cible):
            continue
        if admin_only and not is_admin():
            continue
        if cle and pages_actives.get(cle, True) is False:
            continue
        if callable(cible):
            if titre == "Accueil":
                liste.append(st.Page(cible, title=titre, icon=icone, default=True))
            else:
                liste.append(
                    st.Page(cible, title=titre, icon=icone, url_path=cible.__name__)
                )
        else:
            liste.append(st.Page(cible, title=titre, icon=icone))
    if liste:
        navigation[section] = liste

nav = st.navigation(navigation)

with st.sidebar:
    if brand.get("logo_url"):
        st.image(brand["logo_url"], width=80)
    st.caption(f"Connecté : {profile['nom']} ({profile['role']})")
    if st.button("Se déconnecter"):
        try:
            sb.auth.sign_out()
        except Exception:
            pass
        st.session_state.clear()
        st.rerun()

nav.run()
