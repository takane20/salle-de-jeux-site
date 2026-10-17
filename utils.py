from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from supabase import create_client

TZ = timezone(timedelta(hours=1))  # heure du Bénin (UTC+1)
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]
DEFAUT_BRANDING = {
    "nom": "Salle de jeux",
    "slogan": None,
    "couleur": "#6C5CE7",
    "logo_url": None,
}


def get_client():
    # Un client par session : chaque personne a sa propre connexion
    if "sb" not in st.session_state:
        st.session_state["sb"] = create_client(
            st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
        )
    return st.session_state["sb"]


def fcfa(x):
    try:
        return f"{int(round(float(x))):,}".replace(",", " ") + " FCFA"
    except Exception:
        return "0 FCFA"


def is_admin():
    p = st.session_state.get("profile")
    return bool(p and p.get("role") == "admin")


def debut_mois(d):
    return d.replace(day=1)


def mois_suivant(d):
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def vers_dt(s):
    return pd.to_datetime(s, utc=True).to_pydatetime()


def iso_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_branding(force=False):
    if force or "brand" not in st.session_state:
        try:
            data = (
                get_client()
                .table("branding")
                .select("*")
                .eq("id", 1)
                .single()
                .execute()
                .data
            )
            brand = dict(DEFAUT_BRANDING)
            brand.update({k: v for k, v in data.items() if v is not None})
            st.session_state["brand"] = brand
        except Exception:
            st.session_state["brand"] = dict(DEFAUT_BRANDING)
    return st.session_state["brand"]


def appliquer_couleur(couleur):
    st.markdown(
        f"""
        <style>
        h1 {{ border-bottom: 3px solid {couleur}; padding-bottom: 0.3rem; }}
        button[kind="primary"],
        button[data-testid="stBaseButton-primary"],
        button[data-testid="stBaseButton-primaryFormSubmit"] {{
            background-color: {couleur}; border-color: {couleur}; color: white;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def tout(sb, table, ordre="id"):
    """Lit toutes les lignes d'une table (par paquets de 1000)."""
    lignes, debut, pas = [], 0, 1000
    while True:
        lot = (
            sb.table(table)
            .select("*")
            .order(ordre)
            .range(debut, debut + pas - 1)
            .execute()
            .data
        )
        lignes += lot
        if len(lot) < pas:
            break
        debut += pas
    return lignes


def afficher_flash():
    msg = st.session_state.pop("flash", None)
    if msg:
        st.success(msg)


# ---------- Tableaux modifiables ----------
def _propre(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v.item() if hasattr(v, "item") else v


def _convertir(v, t):
    v = _propre(v)
    if v is None:
        return None
    if t == "int":
        return int(v)
    if t == "float":
        return float(v)
    if t == "bool":
        return bool(v)
    return str(v)


def sauver_editeur(sb, table, original, edite, types, obligatoire,
                   peut_ajouter=True, peut_supprimer=True, defauts=None):
    defauts = defauts or {}

    def norm(r):
        return {c: _convertir(r[c], t) for c, t in types.items()}

    avant = {int(r["id"]): norm(r) for _, r in original.iterrows()}
    vus = set()
    for _, r in edite.iterrows():
        champs = norm(r)
        for k, v in defauts.items():
            if champs.get(k) is None:
                champs[k] = v
        if not champs.get(obligatoire):
            continue
        if pd.isna(r["id"]):
            if peut_ajouter:
                sb.table(table).insert(champs).execute()
        else:
            rid = int(r["id"])
            vus.add(rid)
            if champs != avant.get(rid):
                sb.table(table).update(champs).eq("id", rid).execute()
    if peut_supprimer:
        for rid in set(avant) - vus:
            sb.table(table).delete().eq("id", rid).execute()


def enregistrer_editeur(*args, **kwargs):
    try:
        sauver_editeur(*args, **kwargs)
    except Exception as e:
        st.error(f"Impossible d'enregistrer : {e}")
        return
    st.session_state["flash"] = "Enregistré."
    st.rerun()
