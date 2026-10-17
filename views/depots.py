import uuid
from datetime import date
import streamlit as st
from utils import get_client, fcfa

sb = get_client()
me = st.session_state["profile"]

st.title("💰 Dépôts et budget")

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
            sb.storage.from_("recus").upload(
                chemin, recu.getvalue(), {"content-type": recu.type}
            )
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
