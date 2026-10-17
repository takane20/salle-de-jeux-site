"""Pages Argent : accueil, ventes et dépenses, caisse, rentabilité."""
import uuid
from datetime import date

import pandas as pd
import streamlit as st

from utils import (afficher_flash, debut_mois, fcfa, get_client, is_admin,
                   mois_suivant)


# =====================================================================
# ACCUEIL
# =====================================================================
def accueil():
    sb = get_client()
    p = st.session_state["profile"]
    st.title("🏠 Accueil")
    st.write(f"Bonjour {p['nom']} 👋")

    # Alerte de stock bas (toute l'équipe)
    try:
        stock = sb.table("stock_items").select("article,quantite,seuil_alerte").execute().data
        bas = [s for s in stock if s["quantite"] <= s["seuil_alerte"]]
        if bas:
            st.warning("Stock bas : " + ", ".join(f"{s['article']} ({s['quantite']})" for s in bas))
    except Exception:
        pass

    if not is_admin():
        st.info("Utilise le menu pour enregistrer les ventes, les clients et la salle.")
        return

    cfg = sb.table("settings").select("*").eq("id", 1).single().execute().data
    cible = float(cfg["budget_cible"] or 0)
    limite = int(cfg["jour_limite_depot"])
    profils = sb.table("profiles").select("id,nom,role").execute().data
    noms = {x["id"]: x["nom"] for x in profils}
    admins = [x for x in profils if x["role"] == "admin"]
    totaux = sb.table("totaux_depots").select("*").execute().data
    confirme = sum(float(t["confirme"]) for t in totaux)
    attente = sum(float(t["en_attente"]) for t in totaux)

    # Rappels de dépôt du mois
    auj = date.today()
    mois = debut_mois(auj)
    cibles = {
        t["user_id"]: float(t["montant_prevu"])
        for t in sb.table("monthly_targets").select("*").eq("mois", str(mois)).execute().data
    }
    deps_mois = (
        sb.table("deposits").select("user_id,montant")
        .gte("date_depot", str(mois)).lt("date_depot", str(mois_suivant(mois)))
        .execute().data
    )
    for a in admins:
        mis = sum(float(d["montant"]) for d in deps_mois if d["user_id"] == a["id"])
        prevu = cibles.get(a["id"], 0)
        if prevu > 0 and mis < prevu:
            manque = fcfa(prevu - mis)
            if auj.day > limite:
                st.error(f"⚠️ {a['nom']} est en retard : il manque {manque} pour ce mois.")
            elif limite - auj.day <= 3:
                st.warning(f"⏳ {a['nom']} doit déposer {manque} avant le {limite}.")

    st.metric("Budget visé", fcfa(cible))
    c1, c2 = st.columns(2)
    c1.metric("Déjà confirmé", fcfa(confirme))
    c2.metric("En attente", fcfa(attente))
    if cible > 0:
        st.progress(min(confirme / cible, 1.0), text=f"{confirme / cible:.0%} du budget atteint")
        st.caption(f"Reste à réunir : {fcfa(max(cible - confirme, 0))}")
    else:
        st.info("Le budget visé n'est pas encore défini. On le règle dans Réglages.")

    st.subheader("Qui a mis combien")
    for t in totaux:
        st.write(f"**{noms.get(t['user_id'], '?')}** : {fcfa(t['confirme'])} confirmé, "
                 f"{fcfa(t['en_attente'])} en attente")

    deps = sb.table("deposits").select("date_depot,montant").order("date_depot").execute().data
    if deps:
        df = pd.DataFrame(deps)
        df["montant"] = df["montant"].astype(float)
        df["date_depot"] = pd.to_datetime(df["date_depot"])
        st.subheader("Évolution des dépôts")
        st.line_chart(df.groupby("date_depot")["montant"].sum().cumsum())


# =====================================================================
# VENTES ET DÉPENSES
# =====================================================================
CAT_VENTES = ["jeu", "boisson", "snack", "abonnement", "tournoi", "autre"]
CAT_DEPENSES = ["loyer", "électricité", "matériel", "réfrigérateur",
                "stock boissons et snacks", "salaire", "entretien", "internet", "autre"]


def finances():
    sb = get_client()
    admin = is_admin()
    st.title("📊 Ventes et dépenses")
    afficher_flash()

    if admin:
        type_op = st.radio("Type d'opération", ["vente", "depense"], horizontal=True,
                           format_func=lambda x: "Vente" if x == "vente" else "Dépense")
    else:
        type_op = "vente"

    with st.form("op", clear_on_submit=True):
        cat = st.selectbox("Catégorie", CAT_VENTES if type_op == "vente" else CAT_DEPENSES)
        montant = st.number_input("Montant (FCFA)", min_value=0, step=500)
        jour = st.date_input("Date", value=date.today())
        desc = st.text_input("Description (facultatif)")
        recu = st.file_uploader("Reçu ou facture (facultatif)", type=["png", "jpg", "jpeg"]) if admin else None
        ok = st.form_submit_button("Enregistrer")

    if ok:
        if montant <= 0:
            st.error("Le montant doit être supérieur à 0.")
        else:
            chemin = None
            if recu is not None:
                ext = recu.name.split(".")[-1].lower()
                chemin = f"transactions/{uuid.uuid4().hex}.{ext}"
                sb.storage.from_("recus").upload(chemin, recu.getvalue(), {"content-type": recu.type})
            res = sb.table("transactions").insert({
                "type": type_op, "categorie": cat, "montant": montant,
                "date_op": str(jour), "description": desc or None, "recu_path": chemin,
            }).execute()
            st.success("Enregistré.")
            if res.data and res.data[0].get("alerte"):
                st.warning("⚠️ Cette dépense dépasse le seuil d'alerte.")

    st.subheader("Historique")
    choisi = st.date_input("Mois à afficher", value=date.today(), key="mois_fin")
    debut = debut_mois(choisi)
    rows = (
        sb.table("transactions").select("*")
        .gte("date_op", str(debut)).lt("date_op", str(mois_suivant(debut)))
        .order("date_op", desc=True).order("id", desc=True).execute().data
    )
    if not rows:
        st.info("Aucune opération ce mois-ci.")
        return
    df = pd.DataFrame(rows)
    df["montant"] = df["montant"].astype(float)
    if admin:
        v = df.loc[df["type"] == "vente", "montant"].sum()
        d = df.loc[df["type"] == "depense", "montant"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Ventes", fcfa(v))
        c2.metric("Dépenses", fcfa(d))
        c3.metric("Bénéfice", fcfa(v - d))
    else:
        st.metric("Mes ventes du mois", fcfa(df["montant"].sum()))
    aff = df[["date_op", "type", "categorie", "montant", "description", "alerte"]].copy()
    aff["alerte"] = aff["alerte"].map({True: "⚠️", False: ""})
    aff["montant"] = aff["montant"].map(fcfa)
    aff.columns = ["Date", "Type", "Catégorie", "Montant", "Description", "Alerte"]
    st.dataframe(aff, hide_index=True)

    if admin:
        with st.expander("Supprimer une ligne"):
            choix = {
                f"{r['date_op']} | {r['type']} | {r['categorie']} | {fcfa(r['montant'])} (n°{r['id']})": r["id"]
                for r in rows
            }
            sel = st.selectbox("Ligne", list(choix))
            if st.button("Supprimer cette ligne"):
                sb.table("transactions").delete().eq("id", choix[sel]).execute()
                st.rerun()


# =====================================================================
# CAISSE DU JOUR
# =====================================================================
def caisse():
    sb = get_client()
    st.title("🧾 Caisse du jour")
    afficher_flash()
    jour = st.date_input("Jour", value=date.today())
    ventes = sum(
        float(r["montant"]) for r in
        sb.table("transactions").select("montant").eq("type", "vente").eq("date_op", str(jour)).execute().data
    )
    existante = sb.table("cash_closings").select("*").eq("jour", str(jour)).execute().data

    if existante:
        c = existante[0]
        st.success("La caisse de ce jour est déjà clôturée.")
        a, b, e = st.columns(3)
        a.metric("Espèces attendues", fcfa(c["attendu"]))
        b.metric("Espèces comptées", fcfa(c["compte"]))
        e.metric("Écart", fcfa(c["ecart"]))
        if c["note"]:
            st.caption(c["note"])
    else:
        st.metric("Ventes enregistrées ce jour", fcfa(ventes))
        momo = st.number_input("Dont payé par Mobile Money (FCFA)", min_value=0, step=500, value=0)
        attendu = max(ventes - momo, 0)
        st.metric("Espèces attendues dans la caisse", fcfa(attendu))
        compte = st.number_input("Espèces comptées (FCFA)", min_value=0, step=500, value=0)
        note = st.text_input("Note (facultatif)")
        ecart = compte - attendu
        if compte > 0:
            if ecart == 0:
                st.success("La caisse est juste.")
            else:
                st.warning(f"Écart de {fcfa(ecart)}")
        if st.button("Clôturer la caisse", type="primary"):
            try:
                sb.table("cash_closings").insert({
                    "jour": str(jour), "attendu": attendu, "compte": compte, "note": note or None,
                }).execute()
                st.session_state["flash"] = "Caisse clôturée."
                st.rerun()
            except Exception as e:
                st.error(f"Impossible de clôturer : {e}")

    st.subheader("Dernières clôtures")
    hist = sb.table("cash_closings").select("*").order("jour", desc=True).limit(30).execute().data
    if hist:
        df = pd.DataFrame(hist)[["jour", "attendu", "compte", "ecart", "note"]]
        for c in ["attendu", "compte", "ecart"]:
            df[c] = df[c].map(fcfa)
        df.columns = ["Jour", "Attendu", "Compté", "Écart", "Note"]
        st.dataframe(df, hide_index=True)


# =====================================================================
# RENTABILITÉ
# =====================================================================
def rentabilite():
    sb = get_client()
    st.title("📈 Rentabilité")
    t1, t2, t3 = st.tabs(["Bilan mensuel", "Simulateur", "Évolution des dépôts"])

    with t1:
        bilan = sb.table("bilan_mensuel").select("*").order("mois").execute().data
        if not bilan:
            st.info("Pas encore de ventes ni de dépenses enregistrées.")
        else:
            df = pd.DataFrame(bilan)
            for c in ["ventes", "depenses", "benefice"]:
                df[c] = df[c].astype(float)
            df["mois"] = pd.to_datetime(df["mois"]).dt.strftime("%Y-%m")
            df = df.set_index("mois")
            st.metric("Bénéfice cumulé", fcfa(df["benefice"].sum()))
            st.bar_chart(df[["ventes", "depenses"]])
            st.line_chart(df[["benefice"]])
            aff = df.copy()
            for c in aff.columns:
                aff[c] = aff[c].map(fcfa)
            aff.columns = ["Ventes", "Dépenses", "Bénéfice"]
            st.dataframe(aff)

    with t2:
        st.caption("Change les chiffres pour voir ce que ça donne. Rien n'est enregistré.")
        tarifs = (sb.table("pricing").select("prix").eq("type", "heure")
                  .eq("actif", True).order("prix").execute().data)
        prix_def = int(float(tarifs[0]["prix"])) if tarifs else 1000
        cfg = sb.table("settings").select("budget_cible").eq("id", 1).single().execute().data
        c1, c2 = st.columns(2)
        prix = c1.number_input("Prix de l'heure par poste (FCFA)", min_value=0, step=100, value=prix_def)
        postes = c2.number_input("Nombre de postes", min_value=1, step=1, value=4)
        heures = c1.number_input("Heures jouées par poste et par jour", min_value=0.0,
                                 max_value=24.0, step=0.5, value=5.0)
        jours = c2.number_input("Jours d'ouverture par mois", min_value=1, max_value=31, step=1, value=26)
        ouverture = c1.number_input("Heures d'ouverture par jour", min_value=1.0,
                                    max_value=24.0, step=0.5, value=10.0)
        annexes = c2.number_input("Autres ventes par mois (boissons, snacks)", min_value=0, step=5000, value=0)
        charges = c1.number_input("Charges par mois (loyer, électricité, salaires, internet)",
                                  min_value=0, step=5000, value=0)
        invest = c2.number_input("Investissement de départ (FCFA)", min_value=0, step=10000,
                                 value=int(float(cfg["budget_cible"] or 0)))

        base = prix * postes * jours
        ca = base * heures + annexes
        benef = ca - charges
        pm = max(charges - annexes, 0) / base if base > 0 else 0
        occ = heures / ouverture if ouverture else 0
        retour = invest / benef if benef > 0 else None

        if heures > ouverture:
            st.warning("Les heures jouées dépassent les heures d'ouverture.")
        m1, m2 = st.columns(2)
        m1.metric("Chiffre d'affaires par mois", fcfa(ca))
        m2.metric("Bénéfice par mois", fcfa(benef))
        m3, m4 = st.columns(2)
        m3.metric("Point mort", f"{pm:.1f} h par poste et par jour")
        m4.metric("Taux d'occupation", f"{occ:.0%}")
        if retour is not None:
            st.metric("Retour sur investissement", f"{retour:.1f} mois")
        else:
            st.metric("Retour sur investissement", "Pas de bénéfice")

        scen = []
        for nom, coef in [("Prudent (60 %)", 0.6), ("Réaliste (100 %)", 1.0), ("Optimiste (140 %)", 1.4)]:
            h = heures * coef
            c = base * h + annexes
            b = c - charges
            scen.append({"Scénario": nom, "Heures par poste": round(h, 1), "Chiffre d'affaires": fcfa(c),
                         "Bénéfice": fcfa(b),
                         "Retour (mois)": f"{invest / b:.1f}" if b > 0 else "-"})
        st.dataframe(pd.DataFrame(scen), hide_index=True)

    with t3:
        deps = sb.table("deposits").select("date_depot,montant,user_id").order("date_depot").execute().data
        if not deps:
            st.info("Aucun dépôt pour le moment.")
        else:
            noms = {x["id"]: x["nom"] for x in sb.table("profiles").select("id,nom").execute().data}
            df = pd.DataFrame(deps)
            df["montant"] = df["montant"].astype(float)
            df["date_depot"] = pd.to_datetime(df["date_depot"])
            df["qui"] = df["user_id"].map(noms)
            piv = df.pivot_table(index="date_depot", columns="qui", values="montant",
                                 aggfunc="sum").fillna(0).cumsum()
            st.line_chart(piv)
