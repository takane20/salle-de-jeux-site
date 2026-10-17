"""Pages Équipe : comparateur de prix, tâches, documents, apparence, journal."""
import uuid
from datetime import date

import pandas as pd
import streamlit as st

from utils import (TZ, afficher_flash, fcfa, get_branding, get_client, is_admin,
                   vers_dt)


# =====================================================================
# COMPARATEUR DE PRIX
# =====================================================================
def _cout(q):
    return float(q["prix_unitaire"]) + (float(q["frais_transport"]) + float(q["frais_douane"])) / max(int(q["quantite_devis"]), 1)


def devis():
    sb = get_client()
    st.title("🛒 Comparateur de prix")
    st.caption("Compare Cotonou et l'import, transport et douane compris.")
    afficher_flash()

    items = sb.table("equipment").select("id,article,quantite").order("id").execute().data
    if not items:
        st.info("La liste du matériel est vide.")
        return
    quotes = sb.table("price_quotes").select("*").execute().data

    lignes = []
    for it in items:
        qs = [q for q in quotes if q["equipment_id"] == it["id"]]
        loc = [_cout(q) for q in qs if q["origine"] == "local"]
        imp = [_cout(q) for q in qs if q["origine"] == "import"]
        if loc and imp:
            gagnant = "Local" if min(loc) <= min(imp) else f"Import (économie {fcfa(min(loc) - min(imp))} par unité)"
        elif loc:
            gagnant = "Local (pas de devis import)"
        elif imp:
            gagnant = "Import (pas de devis local)"
        else:
            gagnant = "-"
        lignes.append({"Article": it["article"],
                       "Meilleur prix local": fcfa(min(loc)) if loc else "-",
                       "Meilleur prix import": fcfa(min(imp)) if imp else "-",
                       "Le moins cher": gagnant})
    st.subheader("Vue d'ensemble")
    st.dataframe(pd.DataFrame(lignes), hide_index=True)

    st.subheader("Détail par article")
    choix = {f"{it['article']} (n°{it['id']})": it for it in items}
    it = choix[st.selectbox("Article", list(choix))]
    qs = sorted([q for q in quotes if q["equipment_id"] == it["id"]], key=_cout)
    if not qs:
        st.caption("Aucun devis pour cet article.")
    for i, q in enumerate(qs):
        with st.container(border=True):
            origine = "Cotonou" if q["origine"] == "local" else "Import"
            tag = " ✅ le moins cher" if i == 0 else ""
            st.write(f"**{origine}** : {q['fournisseur'] or '-'}{tag}")
            st.caption(f"Prix unitaire {fcfa(q['prix_unitaire'])} | transport {fcfa(q['frais_transport'])} | "
                       f"douane {fcfa(q['frais_douane'])} | pour {q['quantite_devis']} unité(s)"
                       + (f" | délai {q['delai_jours']} jours" if q["delai_jours"] else ""))
            st.write(f"Coût réel par unité : **{fcfa(_cout(q))}**")
            if q["note"]:
                st.caption(q["note"])
            b1, b2 = st.columns(2)
            if b1.button("Utiliser comme prix réel", key=f"use{q['id']}"):
                sb.table("equipment").update({"prix_reel": round(_cout(q))}).eq("id", it["id"]).execute()
                st.session_state["flash"] = "Prix réel mis à jour dans le matériel."
                st.rerun()
            if b2.button("Supprimer le devis", key=f"del{q['id']}"):
                sb.table("price_quotes").delete().eq("id", q["id"]).execute()
                st.rerun()

    with st.expander("➕ Ajouter un devis pour cet article"):
        with st.form(f"nv_devis_{it['id']}", clear_on_submit=True):
            origine = st.radio("Origine", ["local", "import"], horizontal=True,
                               format_func=lambda x: "Cotonou" if x == "local" else "Import")
            fournisseur = st.text_input("Fournisseur")
            prix = st.number_input("Prix unitaire (FCFA)", min_value=0, step=1000, value=0)
            qte = st.number_input("Quantité du devis", min_value=1, step=1, value=1)
            transport = st.number_input("Transport pour toute la commande (FCFA)", min_value=0, step=1000, value=0)
            douane = st.number_input("Douane et taxes pour toute la commande (FCFA)", min_value=0, step=1000, value=0)
            delai = st.number_input("Délai (jours, 0 si inconnu)", min_value=0, step=1, value=0)
            note = st.text_input("Note")
            ok = st.form_submit_button("Ajouter")
        if ok:
            if prix <= 0:
                st.error("Le prix unitaire doit être supérieur à 0.")
            else:
                sb.table("price_quotes").insert({
                    "equipment_id": it["id"], "origine": origine, "fournisseur": fournisseur or None,
                    "prix_unitaire": prix, "quantite_devis": int(qte), "frais_transport": transport,
                    "frais_douane": douane, "delai_jours": int(delai) or None, "note": note or None,
                }).execute()
                st.session_state["flash"] = "Devis ajouté."
                st.rerun()


# =====================================================================
# TÂCHES
# =====================================================================
def taches():
    sb = get_client()
    admin = is_admin()
    st.title("✅ Tâches")
    afficher_flash()
    noms = {x["id"]: x["nom"] for x in sb.table("profiles").select("id,nom").order("nom").execute().data}

    if admin:
        with st.form("nv_tache", clear_on_submit=True):
            titre = st.text_input("Tâche")
            detail = st.text_area("Détails (facultatif)")
            qui = st.selectbox("Pour qui", list(noms), format_func=lambda i: noms[i])
            avec = st.checkbox("Avec une échéance")
            ech = st.date_input("Échéance", value=date.today())
            ok = st.form_submit_button("Ajouter la tâche")
        if ok:
            if not titre.strip():
                st.error("Écris le titre de la tâche.")
            else:
                sb.table("tasks").insert({
                    "titre": titre.strip(), "detail": detail or None, "assigne_a": qui,
                    "echeance": str(ech) if avec else None,
                }).execute()
                st.session_state["flash"] = "Tâche ajoutée."
                st.rerun()

    rows = sb.table("tasks").select("*").order("fait").order("echeance").execute().data
    if not rows:
        st.info("Aucune tâche.")
        return
    auj = date.today()
    for r in rows:
        with st.container(border=True):
            retard = bool(r["echeance"]) and not r["fait"] and date.fromisoformat(r["echeance"]) < auj
            marque = "✅ " if r["fait"] else ("⚠️ " if retard else "")
            st.write(f"{marque}**{r['titre']}**")
            infos = f"Pour {noms.get(r['assigne_a'], '?')}"
            if r["echeance"]:
                infos += f" | avant le {r['echeance']}"
            st.caption(infos)
            if r["detail"]:
                st.write(r["detail"])
            b1, b2 = st.columns(2)
            if r["fait"]:
                if b1.button("Rouvrir", key=f"ro{r['id']}"):
                    sb.table("tasks").update({"fait": False}).eq("id", r["id"]).execute()
                    st.rerun()
            elif b1.button("Marquer comme fait", key=f"ok{r['id']}"):
                sb.table("tasks").update({"fait": True}).eq("id", r["id"]).execute()
                st.rerun()
            if admin and b2.button("Supprimer", key=f"sp{r['id']}"):
                sb.table("tasks").delete().eq("id", r["id"]).execute()
                st.rerun()


# =====================================================================
# DOCUMENTS
# =====================================================================
def documents():
    sb = get_client()
    st.title("📁 Documents")
    afficher_flash()
    cats = ["contrat", "devis", "recu", "autorisation", "autre"]
    with st.form("nv_doc", clear_on_submit=True):
        titre = st.text_input("Titre")
        cat = st.selectbox("Catégorie", cats)
        f = st.file_uploader("Fichier", type=["pdf", "png", "jpg", "jpeg", "docx", "xlsx"])
        ok = st.form_submit_button("Ajouter")
    if ok:
        if not titre.strip() or f is None:
            st.error("Il faut un titre et un fichier.")
        else:
            ext = f.name.split(".")[-1].lower()
            chemin = f"{uuid.uuid4().hex}.{ext}"
            sb.storage.from_("documents").upload(chemin, f.getvalue(),
                                                 {"content-type": f.type or "application/octet-stream"})
            sb.table("documents").insert({"titre": titre.strip(), "categorie": cat, "chemin": chemin}).execute()
            st.session_state["flash"] = "Document ajouté."
            st.rerun()

    docs = sb.table("documents").select("*").order("created_at", desc=True).execute().data
    if not docs:
        st.info("Aucun document.")
    for d in docs:
        with st.container(border=True):
            st.write(f"**{d['titre']}**")
            st.caption(f"{d['categorie']} | ajouté le {vers_dt(d['created_at']).astimezone(TZ):%d/%m/%Y}")
            b1, b2 = st.columns(2)
            try:
                url = sb.storage.from_("documents").create_signed_url(d["chemin"], 600)["signedURL"]
                b1.link_button("Ouvrir", url)
            except Exception:
                b1.caption("Fichier indisponible.")
            if b2.button("Supprimer", key=f"dd{d['id']}"):
                try:
                    sb.storage.from_("documents").remove([d["chemin"]])
                except Exception:
                    pass
                sb.table("documents").delete().eq("id", d["id"]).execute()
                st.rerun()


# =====================================================================
# APPARENCE
# =====================================================================
def apparence():
    sb = get_client()
    st.title("🎨 Apparence")
    b = get_branding(force=True)
    with st.form("apparence"):
        nom = st.text_input("Nom de la salle", value=b["nom"])
        slogan = st.text_input("Slogan (facultatif)", value=b.get("slogan") or "")
        couleur = st.color_picker("Couleur principale", value=b["couleur"])
        logo = st.file_uploader("Logo (png ou jpg)", type=["png", "jpg", "jpeg"])
        ok = st.form_submit_button("Enregistrer")
    if ok:
        maj = {"nom": nom.strip() or "Salle de jeux", "slogan": slogan.strip() or None, "couleur": couleur}
        try:
            if logo is not None:
                ext = logo.name.split(".")[-1].lower()
                chemin = f"logo_{uuid.uuid4().hex}.{ext}"
                sb.storage.from_("logo").upload(chemin, logo.getvalue(), {"content-type": logo.type})
                maj["logo_url"] = sb.storage.from_("logo").get_public_url(chemin)
            sb.table("branding").update(maj).eq("id", 1).execute()
            get_branding(force=True)
            st.success("Enregistré. Recharge la page pour voir les changements partout.")
        except Exception as e:
            st.error(f"Impossible d'enregistrer : {e}")
    if b.get("logo_url"):
        st.image(b["logo_url"], width=150)


# =====================================================================
# JOURNAL
# =====================================================================
def journal():
    sb = get_client()
    st.title("📝 Journal des modifications")
    noms = {x["id"]: x["nom"] for x in sb.table("profiles").select("id,nom").execute().data}
    tables = ["(toutes)", "deposits", "equipment", "transactions", "monthly_targets", "settings",
              "pricing", "customers", "stations", "stock_items", "tournaments", "price_quotes",
              "documents", "tasks", "cash_closings", "branding"]
    c1, c2 = st.columns(2)
    filtre = c1.selectbox("Table", tables)
    n = c2.slider("Nombre de lignes", 20, 200, 50)
    q = sb.table("audit_log").select("*").order("id", desc=True).limit(n)
    if filtre != "(toutes)":
        q = q.eq("table_name", filtre)
    rows = q.execute().data
    if not rows:
        st.info("Aucune modification enregistrée.")
    actions = {"INSERT": "Ajout", "UPDATE": "Modification", "DELETE": "Suppression"}
    for r in rows:
        quand = vers_dt(r["created_at"]).astimezone(TZ)
        with st.container(border=True):
            st.write(f"**{actions.get(r['action'], r['action'])}** dans `{r['table_name']}` (n°{r['record_id']})")
            st.caption(f"{quand:%d/%m/%Y %H:%M} par {noms.get(r['user_id'], 'inconnu')}")
            ancien, nouveau = r["ancien"] or {}, r["nouveau"] or {}
            if r["action"] == "UPDATE":
                diff = [f"{k} : {ancien.get(k)} → {nouveau.get(k)}"
                        for k in nouveau if ancien.get(k) != nouveau.get(k)]
                for ligne in diff[:8]:
                    st.write(ligne)
            else:
                with st.expander("Détails"):
                    st.json(nouveau or ancien)
