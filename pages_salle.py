"""Pages Salle : clients, chronomètre, postes, réservations, tournois, stock, tarifs."""
from datetime import date, datetime, time, timedelta, timezone

import pandas as pd
import streamlit as st

from utils import (TZ, afficher_flash, enregistrer_editeur, fcfa, get_client,
                   is_admin, iso_utc, vers_dt)


# =====================================================================
# CLIENTS
# =====================================================================
def clients():
    sb = get_client()
    admin = is_admin()
    st.title("👥 Clients")
    afficher_flash()

    abos = sb.table("pricing").select("id,nom,actif").eq("type", "abonnement").execute().data
    abo_noms = {a["id"]: a["nom"] for a in abos}
    abo_actifs = [a["id"] for a in abos if a["actif"]]

    with st.expander("➕ Ajouter un client"):
        with st.form("nv_client", clear_on_submit=True):
            nom = st.text_input("Nom")
            tel = st.text_input("Téléphone (facultatif)")
            ok = st.form_submit_button("Ajouter")
        if ok:
            if not nom.strip():
                st.error("Le nom est obligatoire.")
            else:
                sb.table("customers").insert({"nom": nom.strip(), "telephone": tel.strip() or None}).execute()
                st.session_state["flash"] = "Client ajouté."
                st.rerun()

    recherche = st.text_input("Rechercher un client")
    q = sb.table("customers").select("*").order("nom")
    if recherche:
        q = q.ilike("nom", f"%{recherche}%")
    liste = q.execute().data
    if not liste:
        st.info("Aucun client.")
        return

    auj = date.today()
    for c in liste:
        with st.container(border=True):
            tel = f" · {c['telephone']}" if c["telephone"] else ""
            st.write(f"**{c['nom']}**{tel}")
            statut = ""
            if c["abonnement_id"]:
                fin = c["abonnement_fin"]
                actif = bool(fin) and date.fromisoformat(fin) >= auj
                nom_abo = abo_noms.get(c["abonnement_id"], "Abonnement")
                statut = f" | {nom_abo} " + (f"(actif jusqu'au {fin})" if actif else "(expiré)")
            st.caption(f"⭐ {c['points_fidelite']} points{statut}")

    with st.expander("✏️ Modifier un client"):
        choix = {f"{c['nom']} (n°{c['id']})": c for c in liste}
        sel = choix[st.selectbox("Client", list(choix))]
        cid = sel["id"]
        with st.form(f"modif_{cid}"):
            nom = st.text_input("Nom", value=sel["nom"])
            tel = st.text_input("Téléphone", value=sel["telephone"] or "")
            options = [None] + abo_actifs
            index = options.index(sel["abonnement_id"]) if sel["abonnement_id"] in options else 0
            abo = st.selectbox("Abonnement", options, index=index,
                               format_func=lambda i: "Aucun" if i is None else abo_noms.get(i, "?"))
            fin = st.date_input("Fin d'abonnement",
                                value=date.fromisoformat(sel["abonnement_fin"]) if sel["abonnement_fin"] else auj)
            note = st.text_area("Note", value=sel["note"] or "")
            ok = st.form_submit_button("Enregistrer")
        if ok:
            sb.table("customers").update({
                "nom": nom.strip() or sel["nom"], "telephone": tel.strip() or None,
                "abonnement_id": abo, "abonnement_fin": str(fin) if abo else None,
                "note": note or None,
            }).eq("id", cid).execute()
            st.session_state["flash"] = "Client modifié."
            st.rerun()

        pts = int(sel["points_fidelite"])
        st.caption(f"Points actuels : {pts}")
        if pts > 0:
            use = st.number_input("Points à utiliser", min_value=0, max_value=pts, step=1,
                                  value=0, key=f"use_{cid}")
            if st.button("Utiliser ces points", key=f"btn_use_{cid}") and use > 0:
                sb.table("customers").update({"points_fidelite": pts - int(use)}).eq("id", cid).execute()
                st.session_state["flash"] = f"{int(use)} points utilisés."
                st.rerun()
        if admin and st.button("Supprimer ce client", key=f"del_{cid}"):
            try:
                sb.table("customers").delete().eq("id", cid).execute()
                st.session_state["flash"] = "Client supprimé."
                st.rerun()
            except Exception as e:
                st.error(f"Impossible de supprimer : {e}")


# =====================================================================
# SALLE : chronomètre, postes, réservations, tournois, classement, stock, tarifs
# =====================================================================
ETATS = ["ok", "a_verifier", "en_panne", "en_reparation"]


def salle():
    sb = get_client()
    admin = is_admin()
    st.title("🎮 Salle")
    afficher_flash()
    onglets = st.tabs(["Chronomètre", "Postes", "Réservations", "Tournois",
                       "Classement", "Stock", "Tarifs"])

    postes = sb.table("stations").select("*").order("nom").execute().data
    liste_clients = sb.table("customers").select("id,nom").order("nom").execute().data
    noms_clients = {c["id"]: c["nom"] for c in liste_clients}
    noms_postes = {p["id"]: p["nom"] for p in postes}

    # ---------- Chronomètre ----------
    with onglets[0]:
        sessions = sb.table("play_sessions").select("*").eq("statut", "en_cours").execute().data
        par_poste = {s["station_id"]: s for s in sessions}
        tarifs = (sb.table("pricing").select("id,nom,prix").eq("type", "heure")
                  .eq("actif", True).order("prix").execute().data)
        if st.button("🔄 Actualiser les chronomètres"):
            st.rerun()
        if not postes:
            st.info("Aucun poste. Un administrateur peut en ajouter dans l'onglet Postes.")
        for p in postes:
            with st.container(border=True):
                st.markdown(f"**{p['nom']}** ({p['console']})")
                s = par_poste.get(p["id"])
                if s:
                    debut = vers_dt(s["debut"])
                    secondes = (datetime.now(timezone.utc) - debut).total_seconds()
                    minutes = int(secondes // 60)
                    montant = round(secondes / 3600 * float(s["prix_heure"]))
                    qui = noms_clients.get(s["customer_id"]) or s["nom_libre"] or "Client"
                    st.write(f"En cours : **{qui}**, depuis {debut.astimezone(TZ):%H:%M}")
                    st.metric("Durée", f"{minutes // 60} h {minutes % 60:02d} min")
                    st.caption(f"Prix actuel : {fcfa(montant)} ({fcfa(s['prix_heure'])} l'heure)")
                    if st.button("Terminer et encaisser", key=f"fin{s['id']}", type="primary"):
                        try:
                            sb.table("play_sessions").update({"statut": "termine"}).eq("id", s["id"]).execute()
                            st.session_state["flash"] = f"Session terminée : {fcfa(montant)} encaissés."
                            st.rerun()
                        except Exception as e:
                            st.error(f"Impossible de terminer : {e}")
                elif p["etat"] in ("en_panne", "en_reparation"):
                    st.warning("Poste hors service.")
                else:
                    with st.form(f"debut{p['id']}"):
                        cl = st.selectbox("Client", [None] + list(noms_clients),
                                          format_func=lambda i: "Client de passage" if i is None else noms_clients[i])
                        libre = st.text_input("Nom (si de passage)")
                        opt = {f"{t['nom']} ({fcfa(t['prix'])} l'heure)": float(t["prix"]) for t in tarifs}
                        opt["Prix libre"] = None
                        choix = st.selectbox("Tarif", list(opt))
                        prix_libre = st.number_input("Prix libre de l'heure (FCFA)", min_value=0, step=100, value=0)
                        ok = st.form_submit_button("Démarrer")
                    if ok:
                        prix = opt[choix] if opt[choix] is not None else float(prix_libre)
                        sb.table("play_sessions").insert({
                            "station_id": p["id"], "customer_id": cl,
                            "nom_libre": libre or None, "prix_heure": prix,
                        }).execute()
                        st.rerun()

    # ---------- Postes ----------
    with onglets[1]:
        cols = ["id", "nom", "console", "nb_manettes", "etat", "etat_manettes", "note"]
        df = pd.DataFrame(postes, columns=cols)
        edit = st.data_editor(
            df, hide_index=True, num_rows="dynamic" if admin else "fixed", key="ed_postes",
            disabled=[] if admin else ["id", "nom", "console", "nb_manettes"],
            column_config={
                "id": None, "nom": "Poste", "console": "Console",
                "nb_manettes": st.column_config.NumberColumn("Manettes", min_value=0, step=1),
                "etat": st.column_config.SelectboxColumn("État console", options=ETATS),
                "etat_manettes": st.column_config.SelectboxColumn("État manettes", options=ETATS),
                "note": "Note",
            },
        )
        if st.button("Enregistrer les postes"):
            enregistrer_editeur(
                sb, "stations", df, edit,
                types={"nom": "str", "console": "str", "nb_manettes": "int",
                       "etat": "str", "etat_manettes": "str", "note": "str"},
                obligatoire="nom", peut_ajouter=admin, peut_supprimer=admin,
                defauts={"console": "PS5", "nb_manettes": 2, "etat": "ok", "etat_manettes": "ok"},
            )

    # ---------- Réservations ----------
    with onglets[2]:
        if not postes:
            st.info("Ajoute d'abord des postes.")
        else:
            with st.form("resa"):
                pid = st.selectbox("Poste", list(noms_postes), format_func=lambda i: noms_postes[i])
                cl = st.selectbox("Client ", [None] + list(noms_clients),
                                  format_func=lambda i: "Client de passage" if i is None else noms_clients[i])
                libre = st.text_input("Nom (si de passage) ")
                jour = st.date_input("Jour", value=date.today())
                heure = st.time_input("Heure de début", value=time(16, 0))
                duree = st.number_input("Durée (minutes)", min_value=15, step=15, value=60)
                ok = st.form_submit_button("Réserver")
            if ok:
                debut = datetime.combine(jour, heure, tzinfo=TZ)
                fin = debut + timedelta(minutes=int(duree))
                conflits = (
                    sb.table("reservations").select("id").eq("station_id", pid)
                    .in_("statut", ["reserve", "en_cours"])
                    .lt("debut", iso_utc(fin)).gt("fin", iso_utc(debut)).execute().data
                )
                if conflits:
                    st.error("Ce poste est déjà réservé à cette heure.")
                else:
                    sb.table("reservations").insert({
                        "station_id": pid, "customer_id": cl, "nom_libre": libre or None,
                        "debut": iso_utc(debut), "fin": iso_utc(fin),
                    }).execute()
                    st.session_state["flash"] = "Réservation enregistrée."
                    st.rerun()

            st.subheader("À venir")
            avenir = (sb.table("reservations").select("*").eq("statut", "reserve")
                      .gte("fin", iso_utc(datetime.now(timezone.utc))).order("debut").execute().data)
            if not avenir:
                st.caption("Aucune réservation à venir.")
            for r in avenir:
                d, f = vers_dt(r["debut"]).astimezone(TZ), vers_dt(r["fin"]).astimezone(TZ)
                qui = noms_clients.get(r["customer_id"]) or r["nom_libre"] or "Client"
                with st.container(border=True):
                    st.write(f"**{noms_postes.get(r['station_id'], '?')}** : {d:%d/%m %H:%M} à {f:%H:%M}, {qui}")
                    if st.button("Annuler", key=f"annule{r['id']}"):
                        sb.table("reservations").update({"statut": "annule"}).eq("id", r["id"]).execute()
                        st.rerun()

    # ---------- Tournois ----------
    with onglets[3]:
        with st.expander("➕ Nouveau tournoi"):
            with st.form("nv_tournoi", clear_on_submit=True):
                nom = st.text_input("Nom du tournoi")
                jeu = st.text_input("Jeu")
                jour = st.date_input("Jour ", value=date.today())
                heure = st.time_input("Heure ", value=time(15, 0))
                frais = st.number_input("Frais d'inscription (FCFA)", min_value=0, step=500, value=0)
                recompense = st.text_input("Récompense du gagnant")
                ok = st.form_submit_button("Créer")
            if ok:
                if not nom.strip():
                    st.error("Le nom est obligatoire.")
                else:
                    sb.table("tournaments").insert({
                        "nom": nom.strip(), "jeu": jeu or None,
                        "date_tournoi": iso_utc(datetime.combine(jour, heure, tzinfo=TZ)),
                        "frais_inscription": frais, "prix_gagnant": recompense or None,
                    }).execute()
                    st.session_state["flash"] = "Tournoi créé."
                    st.rerun()

        tournois = sb.table("tournaments").select("*").order("date_tournoi", desc=True).execute().data
        if not tournois:
            st.info("Aucun tournoi.")
        else:
            choix = {f"{t['nom']} ({vers_dt(t['date_tournoi']).astimezone(TZ):%d/%m/%Y})": t for t in tournois}
            t = choix[st.selectbox("Tournoi", list(choix))]
            st.caption(f"Jeu : {t['jeu'] or '-'} | Inscription : {fcfa(t['frais_inscription'])} | "
                       f"Récompense : {t['prix_gagnant'] or '-'}")
            joueurs = sb.table("tournament_players").select("*").eq("tournament_id", t["id"]).order("id").execute().data
            with st.form(f"nv_joueur_{t['id']}", clear_on_submit=True):
                cl = st.selectbox("Joueur (client)", [None] + list(noms_clients),
                                  format_func=lambda i: "Joueur de passage" if i is None else noms_clients[i])
                libre = st.text_input("Nom (si de passage)  ")
                paye = st.checkbox("A payé l'inscription")
                ok = st.form_submit_button("Ajouter le joueur")
            if ok:
                if cl is None and not libre.strip():
                    st.error("Choisis un client ou écris un nom.")
                else:
                    sb.table("tournament_players").insert({
                        "tournament_id": t["id"], "customer_id": cl,
                        "nom_libre": libre.strip() or None, "paye": paye,
                    }).execute()
                    st.rerun()
            if joueurs:
                dfj = pd.DataFrame([{
                    "id": j["id"],
                    "joueur": noms_clients.get(j["customer_id"]) or j["nom_libre"] or "?",
                    "paye": bool(j["paye"]), "classement": j["classement"],
                } for j in joueurs])
                editj = st.data_editor(
                    dfj, hide_index=True, disabled=["id", "joueur"], key=f"ed_j_{t['id']}",
                    column_config={"id": None, "joueur": "Joueur",
                                   "paye": st.column_config.CheckboxColumn("Payé"),
                                   "classement": st.column_config.NumberColumn("Classement", min_value=1, step=1)},
                )
                st.metric("Recettes d'inscriptions", fcfa(int(editj["paye"].sum()) * float(t["frais_inscription"])))
                if st.button("Enregistrer les résultats"):
                    for _, r in editj.iterrows():
                        rang = None if pd.isna(r["classement"]) else int(r["classement"])
                        sb.table("tournament_players").update(
                            {"paye": bool(r["paye"]), "classement": rang}
                        ).eq("id", int(r["id"])).execute()
                    st.session_state["flash"] = "Résultats enregistrés."
                    st.rerun()

    # ---------- Classement ----------
    with onglets[4]:
        rows = sb.table("classement_joueurs").select("*").execute().data
        if not rows:
            st.info("Le classement apparaît dès qu'un tournoi a des résultats.")
        else:
            df = pd.DataFrame(rows).sort_values(["victoires", "podiums", "tournois"],
                                                ascending=[False, False, False]).head(10).reset_index(drop=True)
            medailles = ["🥇", "🥈", "🥉"]
            df.insert(0, "Rang", [medailles[i] if i < 3 else str(i + 1) for i in range(len(df))])
            df.columns = ["Rang", "Joueur", "Tournois", "Victoires", "Podiums"]
            st.dataframe(df, hide_index=True)

    # ---------- Stock ----------
    with onglets[5]:
        cols = ["id", "article", "categorie", "quantite", "seuil_alerte", "prix_achat", "prix_vente"]
        data = sb.table("stock_items").select("*").order("article").execute().data
        df = pd.DataFrame(data, columns=cols)
        if not df.empty:
            bas = df[pd.to_numeric(df["quantite"]) <= pd.to_numeric(df["seuil_alerte"])]
            if not bas.empty:
                st.warning("Stock bas : " + ", ".join(f"{r['article']} ({r['quantite']})" for _, r in bas.iterrows()))
        edit = st.data_editor(
            df, hide_index=True, num_rows="dynamic" if admin else "fixed", key="ed_stock",
            disabled=[] if admin else ["id", "article", "categorie", "seuil_alerte", "prix_achat", "prix_vente"],
            column_config={
                "id": None, "article": "Article",
                "categorie": st.column_config.SelectboxColumn("Catégorie", options=["boisson", "snack", "autre"]),
                "quantite": st.column_config.NumberColumn("Quantité", min_value=0, step=1),
                "seuil_alerte": st.column_config.NumberColumn("Seuil d'alerte", min_value=0, step=1),
                "prix_achat": st.column_config.NumberColumn("Prix d'achat", min_value=0, step=50),
                "prix_vente": st.column_config.NumberColumn("Prix de vente", min_value=0, step=50),
            },
        )
        if st.button("Enregistrer le stock"):
            enregistrer_editeur(
                sb, "stock_items", df, edit,
                types={"article": "str", "categorie": "str", "quantite": "int",
                       "seuil_alerte": "int", "prix_achat": "float", "prix_vente": "float"},
                obligatoire="article", peut_ajouter=admin, peut_supprimer=admin,
                defauts={"categorie": "boisson", "quantite": 0, "seuil_alerte": 5},
            )

    # ---------- Tarifs ----------
    with onglets[6]:
        cols = ["id", "nom", "type", "prix", "duree_minutes", "actif"]
        data = sb.table("pricing").select("*").order("id").execute().data
        df = pd.DataFrame(data, columns=cols)
        if not admin:
            st.caption("Seuls les administrateurs peuvent modifier les tarifs.")
        edit = st.data_editor(
            df, hide_index=True, num_rows="dynamic", key="ed_tarifs", disabled=not admin,
            column_config={
                "id": None, "nom": "Nom",
                "type": st.column_config.SelectboxColumn("Type", options=["heure", "partie", "abonnement", "forfait"]),
                "prix": st.column_config.NumberColumn("Prix (FCFA)", min_value=0, step=100),
                "duree_minutes": st.column_config.NumberColumn("Durée (min)", min_value=0, step=15),
                "actif": st.column_config.CheckboxColumn("Actif"),
            },
        )
        if admin and st.button("Enregistrer les tarifs"):
            enregistrer_editeur(
                sb, "pricing", df, edit,
                              types={"nom": "str", "type": "str", "prix": "float", "duree_minutes": "int", "actif": "bool"},
                obligatoire="nom", defauts={"type": "heure", "prix": 0.0, "actif": True},
            )
          
