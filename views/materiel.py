import pandas as pd
import streamlit as st
from utils import get_client, fcfa

sb = get_client()
st.title("🧰 Matériel")
st.caption("Pour les articles par poste, mets le nombre de postes dans Quantité.")

COLS = ["id", "article", "categorie", "quantite", "prix_estime_min",
        "prix_estime_max", "prix_reel", "achete", "note"]
CATS = ["poste", "salle", "electricite", "gestion", "froid", "autre"]

data = sb.table("equipment").select("*").order("id").execute().data
df = pd.DataFrame(data, columns=COLS)

# Totaux
d = df.copy()
for c in ["quantite", "prix_estime_min", "prix_estime_max", "prix_reel"]:
    d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
q = d["quantite"]
achete = d["achete"].fillna(False).astype(bool)
c1, c2 = st.columns(2)
c1.metric("Estimation basse", fcfa((d["prix_estime_min"] * q).sum()))
c2.metric("Estimation haute", fcfa((d["prix_estime_max"] * q).sum()))
c3, c4 = st.columns(2)
c3.metric("Prix réels trouvés", fcfa((d["prix_reel"] * q).sum()))
c4.metric("Déjà acheté", fcfa((d.loc[achete, "prix_reel"] * q[achete]).sum()))

edit = st.data_editor(
    df,
    num_rows="dynamic",
    hide_index=True,
    key="editeur",
    column_config={
        "id": None,
        "article": "Article",
        "categorie": st.column_config.SelectboxColumn("Catégorie", options=CATS),
        "quantite": st.column_config.NumberColumn("Quantité", min_value=0, step=1),
        "prix_estime_min": st.column_config.NumberColumn("Estimé min", min_value=0, step=1000),
        "prix_estime_max": st.column_config.NumberColumn("Estimé max", min_value=0, step=1000),
        "prix_reel": st.column_config.NumberColumn("Prix réel", min_value=0, step=1000),
        "achete": st.column_config.CheckboxColumn("Acheté"),
        "note": "Note",
    },
)


def propre(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    return v.item() if hasattr(v, "item") else v


def norm(r):
    c = {k: propre(r[k]) for k in COLS if k != "id"}
    c["quantite"] = int(c["quantite"] if c["quantite"] is not None else 1)
    c["achete"] = bool(c["achete"])
    c["categorie"] = c["categorie"] or "autre"
    for k in ("prix_estime_min", "prix_estime_max", "prix_reel"):
        if c[k] is not None:
            c[k] = float(c[k])
    return c


if st.button("Enregistrer les changements", type="primary"):
    avant = {int(r["id"]): norm(r) for _, r in df.iterrows()}
    vus = set()
    for _, r in edit.iterrows():
        champs = norm(r)
        if not champs["article"]:
            continue
        if pd.isna(r["id"]):
            sb.table("equipment").insert(champs).execute()
        else:
            rid = int(r["id"])
            vus.add(rid)
            if champs != avant.get(rid):
                sb.table("equipment").update(champs).eq("id", rid).execute()
    for rid in set(avant) - vus:
        sb.table("equipment").delete().eq("id", rid).execute()
    st.success("Liste enregistrée.")
    st.rerun()
