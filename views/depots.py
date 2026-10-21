import uuid
from datetime import date

import streamlit as st

from utils import fcfa, get_client

sb = get_client()
me = st.session_state["profile"]

st.title("💰 Dépôts et budget")
# Résumé du budget
cfg = sb.table("settings").select("budget_cible").eq("id", 1).single().execute().data
cible = float(cfg["budget_cible"] or 0)
totaux = sb.table("totaux_depots").select("*").execute().data
confirme = sum(float(t["confirme"]) for t in totaux)
attente = sum(float(t["en_attente"]) for t in totaux)
r1, r2 = st.columns(2)
r1.metric("Total confirmé", fcfa(confirme))
r2.metric("En attente", fcfa(attente))
if cible > 0:
    st.progress(min(confirme / cible, 1.0),
                text=f"{confirme / cible:.0%} du budget visé ({fcfa(cible)})")

noms = {x["id"]: x["nom"] for x in sb.table("profiles").select("id,nom").execute().data}

st.subheader("Noter un dépôt")
with st.form("nouveau_depot", clear_on_submit=True):
    montant = st.number_input("Montant déposé (FCFA)", min_value=0, step=1000)
    jour = st.date_input("Date du dépôt", value=date.today())
    note = st.text_input("Note (facultatif)")
    recu = st.file_uploader("Capture du reçu Momo", type=["png", "jpg", "jpeg"])
    ok = st.form_submit_button("Enregistrer le dépôt")

if ok:
    if montant <= 0:
        st.error("Le montant doit être supérieur à 0.")
    else:
        chemin = None
        if recu is not None:
            ext = recu.name.split(".")[-1].lower()
            chemin = f"{me['id']}/{uuid.uuid4().hex}.{ext}"
            try:
                sb.storage.from_("recus").upload(
                    chemin, recu.getvalue(), {"content-type": recu.type or "image/jpeg"}
                )
            except Exception as e:
                st.error(f"La capture n'a pas pu être envoyée : {e}")
                chemin = None
        sb.table("deposits").insert(
            {
                "montant": montant,
                "date_depot": str(jour),
                "note": note or None,
                "recu_path": chemin,
            }
        ).execute()
        st.success("Dépôt enregistré. L'autre personne doit maintenant le confirmer.")

st.subheader("Historique")
rows = (
    sb.table("deposits")
    .select("*")
    .order("date_depot", desc=True)
    .order("id", desc=True)
    .execute()
    .data
)
if not rows:
    st.info("Aucun dépôt pour le moment.")

for r in rows:
    qui = noms.get(r["user_id"], "?")
    etat = "✅ Confirmé" if r["statut"] == "confirme" else "⏳ En attente"
    if r["confirme_par"]:
        etat += f" par {noms.get(r['confirme_par'], '?')}"
    with st.container(border=True):
        st.write(f"**{fcfa(r['montant'])}** par {qui}, le {r['date_depot']}")
        st.caption(etat)
        if r["note"]:
            st.write(r["note"])
        if r["recu_path"]:
            try:
                url = sb.storage.from_("recus").create_signed_url(r["recu_path"], 300)[
                    "signedURL"
                ]
                st.image(url, width=220)
            except Exception:
                st.caption("Reçu indisponible.")
        if r["statut"] == "en_attente":
            if r["user_id"] != me["id"]:
                if st.button("Confirmer ce dépôt", key=f"conf{r['id']}"):
                    sb.table("deposits").update({"statut": "confirme"}).eq(
                        "id", r["id"]
                    ).execute()
                    st.rerun()
            else:
                st.caption("En attente de la confirmation de l'autre personne.")
                if st.button("Supprimer", key=f"sup{r['id']}"):
                    sb.table("deposits").delete().eq("id", r["id"]).execute()
                    st.rerun()
