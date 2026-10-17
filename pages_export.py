"""Page Exports : sauvegarde Excel et rapport mensuel en PDF."""
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st
from fpdf import FPDF

from utils import (MOIS, debut_mois, fcfa, get_branding, get_client,
                   mois_suivant, tout)


def _s(t):
    return str(t).encode("latin-1", "replace").decode("latin-1")


def _ligne(pdf, texte, taille=11, gras=False):
    pdf.set_font("Helvetica", "B" if gras else "", taille)
    pdf.multi_cell(0, 7, _s(texte), new_x="LMARGIN", new_y="NEXT")


def _paire(pdf, gauche, droite):
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(110, 7, _s(gauche))
    pdf.cell(0, 7, _s(droite), new_x="LMARGIN", new_y="NEXT", align="R")


def construire_rapport(sb, mois, nom_salle):
    fin = mois_suivant(mois)
    trans = (sb.table("transactions").select("*")
             .gte("date_op", str(mois)).lt("date_op", str(fin)).execute().data)
    deps = (sb.table("deposits").select("user_id,montant,statut")
            .gte("date_depot", str(mois)).lt("date_depot", str(fin)).execute().data)
    cfg = sb.table("settings").select("budget_cible").eq("id", 1).single().execute().data
    totaux = sb.table("totaux_depots").select("*").execute().data
    noms = {x["id"]: x["nom"] for x in sb.table("profiles").select("id,nom").execute().data}
    equip = sb.table("equipment").select("quantite,prix_reel,achete").execute().data

    ventes = [t for t in trans if t["type"] == "vente"]
    depenses = [t for t in trans if t["type"] == "depense"]
    tv = sum(float(t["montant"]) for t in ventes)
    td = sum(float(t["montant"]) for t in depenses)

    pdf = FPDF()
    pdf.add_page()
    _ligne(pdf, f"{nom_salle} : rapport de {MOIS[mois.month - 1]} {mois.year}", 16, True)
    pdf.ln(3)

    _ligne(pdf, "Résumé du mois", 13, True)
    _paire(pdf, "Ventes", fcfa(tv))
    _paire(pdf, "Dépenses", fcfa(td))
    _paire(pdf, "Bénéfice", fcfa(tv - td))
    pdf.ln(3)

    for titre, liste in (("Ventes par catégorie", ventes), ("Dépenses par catégorie", depenses)):
        _ligne(pdf, titre, 13, True)
        cats = {}
        for t in liste:
            cats[t["categorie"]] = cats.get(t["categorie"], 0) + float(t["montant"])
        if not cats:
            _ligne(pdf, "Aucune opération.")
        for c, m in sorted(cats.items(), key=lambda x: -x[1]):
            _paire(pdf, c, fcfa(m))
        pdf.ln(3)

    alertes = [t for t in depenses if t.get("alerte")]
    if alertes:
        _ligne(pdf, "Dépenses signalées (au-dessus du seuil)", 13, True)
        for t in alertes:
            _paire(pdf, f"{t['date_op']} {t['categorie']}", fcfa(t["montant"]))
        pdf.ln(3)

    _ligne(pdf, "Dépôts du mois", 13, True)
    par = {}
    for d in deps:
        par[d["user_id"]] = par.get(d["user_id"], 0) + float(d["montant"])
    if not par:
        _ligne(pdf, "Aucun dépôt.")
    for u, m in par.items():
        _paire(pdf, noms.get(u, "?"), fcfa(m))
    pdf.ln(3)

    cible = float(cfg["budget_cible"] or 0)
    confirme = sum(float(t["confirme"]) for t in totaux)
    _ligne(pdf, "Budget de départ", 13, True)
    _paire(pdf, "Budget visé", fcfa(cible))
    _paire(pdf, "Déjà confirmé", fcfa(confirme))
    if cible > 0:
        _paire(pdf, "Avancement", f"{confirme / cible:.0%}")
    achete = sum(float(e["prix_reel"] or 0) * int(e["quantite"] or 0) for e in equip if e["achete"])
    _paire(pdf, "Matériel déjà acheté", fcfa(achete))
    pdf.ln(5)
    _ligne(pdf, f"Rapport généré le {date.today():%d/%m/%Y}", 9)
    return bytes(pdf.output())


def exports():
    sb = get_client()
    st.title("📤 Exports et rapports")

    st.subheader("Sauvegarde Excel")
    st.caption("Toutes les données du site dans un seul fichier. À télécharger régulièrement.")
    TABLES = {
        "Dépôts": ("deposits", "id"), "Matériel": ("equipment", "id"),
        "Ventes et dépenses": ("transactions", "id"), "Bilan mensuel": ("bilan_mensuel", "mois"),
        "Clients": ("customers", "id"), "Tarifs": ("pricing", "id"), "Postes": ("stations", "id"),
        "Sessions": ("play_sessions", "id"), "Réservations": ("reservations", "id"),
        "Tournois": ("tournaments", "id"), "Joueurs": ("tournament_players", "id"),
        "Stock": ("stock_items", "id"), "Devis": ("price_quotes", "id"),
        "Caisse": ("cash_closings", "id"), "Tâches": ("tasks", "id"),
    }
    if st.button("Préparer la sauvegarde"):
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            for feuille, (table, ordre) in TABLES.items():
                pd.DataFrame(tout(sb, table, ordre)).to_excel(xw, sheet_name=feuille[:31], index=False)
        st.session_state["xlsx"] = buf.getvalue()
    if "xlsx" in st.session_state:
        st.download_button(
            "⬇️ Télécharger le fichier Excel", st.session_state["xlsx"],
            file_name=f"sauvegarde_salle_de_jeux_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.subheader("Rapport mensuel en PDF")
    choisi = st.date_input("Mois du rapport", value=date.today(), key="mois_rapport")
    mois = debut_mois(choisi)
    if st.button("Préparer le rapport"):
        try:
            st.session_state["pdf"] = (construire_rapport(sb, mois, get_branding()["nom"]),
                                       f"rapport_{mois:%Y-%m}.pdf")
        except Exception as e:
            st.error(f"Impossible de préparer le rapport : {e}")
    if "pdf" in st.session_state:
        data, nom = st.session_state["pdf"]
        st.download_button("⬇️ Télécharger le rapport PDF", data, file_name=nom, mime="application/pdf")
