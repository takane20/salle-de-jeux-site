import streamlit as st
from utils import get_client, fcfa, is_admin

st.title("🏠 Accueil")
p = st.session_state["profile"]
st.write(f"Bonjour {p['nom']} 👋")

if is_admin():
    sb = get_client()
    cible = (
        sb.table("settings").select("budget_cible").eq("id", 1).single().execute().data
    )["budget_cible"]
    cible = float(cible or 0)
    totaux = sb.table("totaux_depots").select("*").execute().data
    noms = {
        x["id"]: x["nom"] for x in sb.table("profiles").select("id,nom").execute().data
    }
    confirme = sum(float(t["confirme"]) for t in totaux)
    attente = sum(float(t["en_attente"]) for t in totaux)

    st.metric("Budget visé", fcfa(cible))
    c1, c2 = st.columns(2)
    c1.metric("Déjà confirmé", fcfa(confirme))
    c2.metric("En attente", fcfa(attente))

    if cible > 0:
        st.progress(
            min(confirme / cible, 1.0), text=f"{confirme / cible:.0%} du budget atteint"
        )
        st.caption(f"Reste à réunir : {fcfa(max(cible - confirme, 0))}")
    else:
        st.info("Le budget visé n'est pas encore défini. On le règlera dans Réglages.")

    st.subheader("Qui a mis combien")
    for t in totaux:
        st.write(
            f"**{noms.get(t['user_id'], '?')}** : {fcfa(t['confirme'])} confirmé, "
            f"{fcfa(t['en_attente'])} en attente"
        )
else:
    st.info("Utilise le menu pour enregistrer les ventes, les clients et la salle.")
