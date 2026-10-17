from datetime import date, timedelta
import streamlit as st
from utils import get_client, fcfa

sb = get_client()
st.title("⚙️ Réglages")

cfg = sb.table("settings").select("*").eq("id", 1).single().execute().data
profils = sb.table("profiles").select("id,nom,role").order("nom").execute().data
admins = [p for p in profils if p["role"] == "admin"]

# 1. Budget et alertes
st.subheader("Budget et alertes")
with st.form("budget"):
    cible = st.number_input(
        "Budget de départ visé (FCFA)",
        min_value=0, step=10000, value=int(cfg["budget_cible"] or 0),
    )
    jour = st.number_input(
        "Jour limite de dépôt chaque mois",
        min_value=1, max_value=28, value=int(cfg["jour_limite_depot"]),
    )
    seuil = st.number_input(
        "Alerte si une dépense dépasse (FCFA, 0 = pas d'alerte)",
        min_value=0, step=5000, value=int(cfg["seuil_alerte_depense"] or 0),
    )
    if st.form_submit_button("Enregistrer"):
        sb.table("settings").update(
            {
                "budget_cible": cible,
                "jour_limite_depot": int(jour),
                "seuil_alerte_depense": seuil,
            }
        ).eq("id", 1).execute()
        st.success("Réglages enregistrés.")

# 2. Pages du site
st.subheader("Pages du site")
LIBELLES = {
    "depots": "Dépôts et budget",
    "materiel": "Matériel",
    "finances": "Ventes, dépenses et rentabilité",
    "clients": "Clients",
    "salle": "Salle (postes, tournois, stock)",
}
actives = cfg.get("pages_actives") or {}
with st.form("pages"):
    choix = {k: st.checkbox(v, value=actives.get(k, True)) for k, v in LIBELLES.items()}
    if st.form_submit_button("Enregistrer les pages"):
        sb.table("settings").update({"pages_actives": choix}).eq("id", 1).execute()
        st.success("Enregistré. Recharge la page pour voir le nouveau menu.")

# 3. Objectifs mensuels
st.subheader("Objectifs de dépôt par mois")
aujourdhui = date.today()
mois_courant = aujourdhui.replace(day=1)
choisi = st.date_input("Mois (n'importe quel jour du mois)", value=mois_courant)
mois = choisi.replace(day=1)

cibles = {
    t["user_id"]: t["montant_prevu"]
    for t in sb.table("monthly_targets").select("*").eq("mois", str(mois)).execute().data
}
with st.form("objectifs"):
    vals = {
        p["id"]: st.number_input(
            f"{p['nom']} (FCFA)",
            min_value=0, step=5000, value=int(cibles.get(p["id"], 0)),
            key=f"obj_{p['id']}_{mois}",
        )
        for p in admins
    }
    if st.form_submit_button("Enregistrer les objectifs"):
        for uid, v in vals.items():
            sb.table("monthly_targets").upsert(
                {"user_id": uid, "mois": str(mois), "montant_prevu": v},
                on_conflict="user_id,mois",
            ).execute()
        st.success("Objectifs enregistrés.")
        cibles = {uid: v for uid, v in vals.items()}

# 4. Suivi du mois et retards
st.subheader("Suivi des dépôts du mois")
fin = (mois.replace(day=28) + timedelta(days=4)).replace(day=1)
deps = (
    sb.table("deposits")
    .select("user_id,montant")
    .gte("date_depot", str(mois))
    .lt("date_depot", str(fin))
    .execute()
    .data
)
limite = int(cfg["jour_limite_depot"])
for p in admins:
    mis = sum(float(d["montant"]) for d in deps if d["user_id"] == p["id"])
    prevu = float(cibles.get(p["id"], 0) or 0)
    if prevu == 0:
        etat = "Pas d'objectif fixé"
    elif mis >= prevu:
        etat = "✅ Objectif atteint"
    elif mois > mois_courant:
        etat = "À venir"
    elif mois < mois_courant or aujourdhui.day > limite:
        etat = f"⚠️ En retard, il manque {fcfa(prevu - mis)}"
    else:
        etat = f"⏳ À déposer avant le {limite}, il manque {fcfa(prevu - mis)}"
    st.write(f"**{p['nom']}** : {fcfa(mis)} sur {fcfa(prevu)}. {etat}")

# 5. Équipe
st.subheader("Équipe")
for p in profils:
    st.write(f"**{p['nom']}** : {p['role']}")
st.caption(
    "Pour ajouter un employé : Supabase, Authentication, Users, Add user. "
    "Son compte aura automatiquement un accès limité."
             )
