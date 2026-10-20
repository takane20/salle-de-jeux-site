import pandas as pd
import streamlit as st

from utils import afficher_flash, enregistrer_editeur, fcfa, get_client

sb = get_client()
st.title("🧰 Matériel")
afficher_flash()
st.caption("Pour les articles par poste, mets le nombre de postes dans Quantité. "
           "Décoche « À l'ouverture » pour ce qui peut attendre.")

COLS = ["id", "article", "categorie", "quantite", "prix_estime_min", "prix_estime_max",
        "prix_reel", "achete", "ouverture", "note"]
CATS = ["poste", "salle", "electricite", "gestion", "froid", "autre"]

data = sb.table("equipment").select("*").order("id").execute().data
df = pd.DataFrame(data, columns=COLS)

# Totaux
d = df.copy()
for c in ["quantite", "prix_estime_min", "prix_estime_max", "prix_reel"]:
    d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
q = d["quantite"]
achete = d["achete"].fillna(False).astype(bool)
ouv = d["ouverture"].fillna(True).astype(bool)

st.subheader("Pour ouvrir")
a, b = st.columns(2)
a.metric("Minimum", fcfa((d["prix_estime_min"] * q)[ouv].sum()))
b.metric("Maximum", fcfa((d["prix_estime_max"] * q)[ouv].sum()))

st.subheader("Tout le matériel")
c1, c2 = st.columns(2)
c1.metric("Minimum", fcfa((d["prix_estime_min"] * q).sum()))
c2.metric("Maximum", fcfa((d["prix_estime_max"] * q).sum()))
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
        "ouverture": st.column_config.CheckboxColumn("À l'ouverture"),
        "note": "Note",
    },
)

if st.button("Enregistrer les changements", type="primary"):
    enregistrer_editeur(
        sb, "equipment", df, edit,
        types={"article": "str", "categorie": "str", "quantite": "int",
               "prix_estime_min": "float", "prix_estime_max": "float", "prix_reel": "float",
               "achete": "bool", "ouverture": "bool", "note": "str"},
        obligatoire="article",
        defauts={"categorie": "autre", "quantite": 1, "achete": False, "ouverture": True},
    )
