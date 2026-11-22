"""WikiJury, version Streamlit.

Lancement local :  streamlit run streamlit_app/app.py
Le moteur de calcul (package `wikijury`) est le même que celui de la version web :
barème et correspondance des colonnes sont lus dans le dossier `shared/`.
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from wikijury import (
    COAUTHOR_RULES,
    CRITERIA,
    CRITERION_SHORT,
    Dataset,
    compute_ranking,
    criterion_label,
    detect_kind,
    load_columns_spec,
    load_default_scoring,
    map_columns,
    merge_scoring,
    missing_fields,
    wikis_in_data,
)
from wikijury.io import ImportError_, ranking_to_csv, read_upload

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "shared" / "brand"
FIXTURES = ROOT / "shared" / "fixtures" / "dashboard"

st.set_page_config(
    page_title="WikiJury : classement des concours Wikimedia",
    page_icon=str(BRAND / "favicon.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

COLORS = {
    "article_long": "#006699",
    "article_short": "#7DB9D6",
    "wikidata_item": "#339966",
    "photo_uploaded_used": "#D9A23A",
    "photo_existing_used": "#8E6FB8",
}
FIELD_LABELS = {
    "username": "Contributeur",
    "title": "Titre de l’article",
    "characters": "Caractères ajoutés",
    "new": "Créé pendant la campagne",
    "filename": "Nom du fichier",
    "usage_count": "Nombre d’utilisations",
    "item": "Identifiant Wikidata",
    "quantity": "Nombre d’éléments",
    "article": "Article",
    "edits": "Modifications",
    "bytes": "Octets ajoutés",
    "references": "Références ajoutées",
    "usernames": "Participants",
    "wiki": "Wiki",
    "namespace": "Espace de noms",
    "deleted": "Supprimé",
    "course": "Campagne",
}
STATUS_TEXT = {
    "article_long": "Article long",
    "article_short": "Article court",
    "too_short": "Trop court",
    "not_new": "Non créé pendant la campagne",
    "photo_uploaded_used": "Utilisée",
    "photo_unused": "Non utilisée dans un article",
    "wikidata_item": "Élément créé",
    "photo_existing_used": "Ajoutée à un article",
    "wiki_excluded": "Wiki non retenu par le jury",
    "photo_usage_unknown": "Usage inconnu : ajoutez l’export « uploads »",
}

SPEC = load_columns_spec()
DEFAULT_SCORING = load_default_scoring()
SCORED_KINDS = {"dashboard_articles", "articles", "uploads", "wikidata", "existing_photos"}

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1280px; }
      h1, h2, h3 { letter-spacing: -0.02em; }
      .wj-title { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; margin: 0 0 .25rem; }
      .wj-title.is-empty { color: #a9b3ad; }
      .wj-legend { display: flex; flex-wrap: wrap; gap: .35rem 1.2rem; font-size: .9rem; color: #4a5664; margin: .25rem 0 1rem; }
      .wj-legend span::before { content: ""; display: inline-block; width: .75rem; height: .75rem; border-radius: 3px;
        margin-right: .4rem; vertical-align: -.05rem; background: var(--c); }
      .wj-footer { text-align: center; color: #4a5664; font-size: .9rem; margin-top: 3rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- état

def init_state() -> None:
    st.session_state.setdefault("points", dict(DEFAULT_SCORING["points"]))
    st.session_state.setdefault("thresholds", dict(DEFAULT_SCORING["thresholds"]))
    for c, v in DEFAULT_SCORING["points"].items():
        st.session_state.setdefault(f"pts_{c}", int(v))
    for k, v in DEFAULT_SCORING["thresholds"].items():
        st.session_state.setdefault(f"th_{k}", int(v))
    st.session_state.setdefault("use_sample", False)
    st.session_state.setdefault("rule_coauthors", DEFAULT_SCORING["rules"]["coauthors"])
    st.session_state.setdefault("campaign", "")


def reset_scoring() -> None:
    for c, v in DEFAULT_SCORING["points"].items():
        st.session_state[f"pts_{c}"] = v
    for k, v in DEFAULT_SCORING["thresholds"].items():
        st.session_state[f"th_{k}"] = v
    st.session_state["rule_coauthors"] = DEFAULT_SCORING["rules"]["coauthors"]


def fmt(n: float) -> str:
    """Nombre à la française : espace fine pour les milliers, virgule décimale."""
    text = f"{n:,.2f}".rstrip("0").rstrip(".") if isinstance(n, float) and n != int(n) else f"{int(n):,}"
    return text.replace(",", "\u202f").replace(".", ",")


def load_sample() -> None:
    st.session_state.use_sample = True
    if not st.session_state.campaign:
        st.session_state.campaign = "Concours d’exemple (données fictives)"


def slug(text: str) -> str:
    from wikijury.normalize import strip_accents
    import re
    return re.sub(r"[^a-z0-9]+", "-", strip_accents(text).lower()).strip("-") or "classement"


@st.cache_data(show_spinner=False)
def parse(name: str, data: bytes):
    return read_upload(name, data)


init_state()

# ------------------------------------------------------------------------ barre latérale

with st.sidebar:
    st.image(str(BRAND / "mark.png"), width=64)
    st.markdown("### WikiJury")
    st.text_input("Nom de la campagne", key="campaign", placeholder="Ex. : Wiki Loves Bénin 2026", max_chars=90)

    uploads = st.file_uploader(
        "Fichiers à classer",
        type=["csv", "tsv", "txt", "xlsx"],
        accept_multiple_files=True,
        help="Exports de l’Outreach Dashboard ou tableaux maison : articles, photos, éléments Wikidata, participants.",
    )

    st.markdown("#### Barème")
    scoring_points = {}
    for c in CRITERIA:
        scoring_points[c] = st.number_input(
            criterion_label(c, {"thresholds": {
                "article_long_min_chars": st.session_state["th_article_long_min_chars"],
                "article_short_min_chars": st.session_state["th_article_short_min_chars"],
            }}),
            min_value=0,
            max_value=1000,
            step=1,
            key=f"pts_{c}",
        )
    col_a, col_b = st.columns(2)
    long_min = col_a.number_input(
        "Article long (car.)", min_value=1, step=100, key="th_article_long_min_chars",
    )
    short_min = col_b.number_input(
        "Article court (car.)", min_value=1, step=100, key="th_article_short_min_chars",
    )
    st.selectbox(
        "Pages créées à plusieurs",
        list(COAUTHOR_RULES),
        format_func=COAUTHOR_RULES.get,
        key="rule_coauthors",
        help="L’export du Dashboard liste tous les participants ayant modifié une page, sans dire qui l’a créée.",
    )
    st.button("Rétablir le barème par défaut", on_click=reset_scoring, width="stretch")

scoring = merge_scoring(DEFAULT_SCORING, {
    "points": scoring_points,
    "thresholds": {"article_long_min_chars": int(long_min), "article_short_min_chars": int(short_min)},
    "rules": {"coauthors": st.session_state.rule_coauthors},
})
scoring_valid = short_min < long_min

# --------------------------------------------------------------------------- en-tête

campaign = st.session_state.campaign.strip()
st.markdown(
    f'<h1 class="wj-title{"" if campaign else " is-empty"}">{html.escape(campaign or "Classement du concours")}</h1>',
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------- fichiers

files: list[dict] = []
if uploads:
    for up in uploads:
        try:
            headers, rows = parse(up.name, up.getvalue())
            files.append({"name": up.name, "headers": headers, "rows": rows, "error": None})
        except ImportError_ as err:
            files.append({"name": up.name, "headers": [], "rows": [], "error": str(err)})
        except Exception:  # fichier corrompu : on l'explique sans planter l'application
            files.append({"name": up.name, "headers": [], "rows": [], "error": "Lecture impossible : le fichier semble endommagé."})
elif st.session_state.use_sample:
    for name in ["course_editors.csv", "course_articles.csv", "course_uploads.csv"]:
        headers, rows = parse(name, (FIXTURES / name).read_bytes())
        files.append({"name": name, "headers": headers, "rows": rows, "error": None})

if not files:
    st.subheader("Un classement que chaque participant peut vérifier.")
    st.write("Chaque point attribué renvoie à l’article, la photo ou l’élément Wikidata qui l’a rapporté.")
    st.markdown(
        "1. **Exportez vos données** : les fichiers CSV « articles », « uploads » et « editors » de l’Outreach Dashboard suffisent. Des tableaux maison sont aussi acceptés.\n"
        "2. **Déposez les fichiers** dans le panneau de gauche : leur type et leurs colonnes sont reconnus automatiquement.\n"
        "3. **Ajustez le barème** : le classement se met à jour aussitôt."
    )
    st.button("Essayer avec des données d’exemple", type="primary", on_click=load_sample)
    st.stop()

datasets: list[Dataset] = []
with st.expander("Fichiers importés et colonnes utilisées", expanded=False):
    kind_options = list(SPEC["kinds"].keys()) + [""]
    kind_labels = {k: v["label"] for k, v in SPEC["kinds"].items()} | {"": "Ne pas utiliser ce fichier"}
    for i, f in enumerate(files):
        st.markdown(f"**{html.escape(f['name'])}**")
        if f["error"]:
            st.error(f["error"])
            continue
        detection = detect_kind(f["headers"], f["name"], SPEC)
        default_kind = detection.kind or "articles"
        kind = st.selectbox(
            "Type de fichier", kind_options, index=kind_options.index(default_kind),
            format_func=kind_labels.get, key=f"kind_{i}_{f['name']}",
        )
        if not kind:
            st.caption("Fichier ignoré.")
            continue
        spec = SPEC["kinds"][kind]
        if spec.get("unusable"):
            st.warning(spec["description"])
            continue
        auto = map_columns(f["headers"], spec)
        mapping = {}
        cols = st.columns(len(spec["fields"]))
        for col, (field, fspec) in zip(cols, spec["fields"].items()):
            options = [""] + f["headers"]
            mapping[field] = col.selectbox(
                FIELD_LABELS.get(field, field) + ("" if fspec.get("required") else " (facultatif)"),
                options,
                index=options.index(auto[field]) if auto[field] in options else 0,
                format_func=lambda h: h or "— aucune —",
                key=f"map_{i}_{f['name']}_{kind}_{field}",
            ) or None
        missing = missing_fields(mapping, spec)
        if missing:
            st.warning(f"{len(missing)} colonne(s) à associer avant que ce fichier soit pris en compte.")
        else:
            st.caption(f"{len(f['rows'])} lignes prises en compte.")
            datasets.append(Dataset(kind, mapping, f["rows"], f["name"]))

if not any(d.kind in SCORED_KINDS for d in datasets):
    st.info("Ajoutez au moins un fichier d’articles, de photos ou d’éléments Wikidata pour calculer le classement.")
    st.stop()

if not scoring_valid:
    st.error("Le seuil de l’article court doit être inférieur à celui de l’article long. Corrigez le barème pour calculer le classement.")
    st.stop()

all_names = sorted({p.username for p in compute_ranking(datasets, scoring).participants})
wikis = wikis_in_data(datasets)
with st.sidebar:
    if len(wikis) > 1:
        kept = st.multiselect("Wikipédias prises en compte", wikis, default=wikis, key="kept_wikis")
        scoring["rules"]["excluded_wikis"] = [w for w in wikis if w not in kept]
    st.markdown("#### Hors concours")
    excluded = st.multiselect(
        "Participants à ne pas classer (organisateurs, jury…)",
        all_names,
        key="excluded_select",
    )

result = compute_ranking(datasets, scoring, excluded)
ranked = [p for p in result.participants if not p.excluded]

# ------------------------------------------------------------------------- classement

st.caption(f"{len(ranked)} participants classés, {fmt(sum(p.total for p in ranked))} points attribués.")

notices = []
unknown_photos = sum(1 for p in result.participants for e in p.evidence if e["status"] == "photo_usage_unknown" and e["share"] > 0)
if unknown_photos:
    notices.append(f"{unknown_photos} photo(s) téléversée(s) non notée(s) : l’export « articles » ne donne pas leur nombre d’utilisations. Ajoutez l’export « uploads » du Dashboard pour les noter.")
if result.stats["ignored"]:
    notices.append(f"{fmt(result.stats['ignored'])} page(s) hors critères ignorée(s) (articles existants modifiés, pages de discussion ou utilisateur, éléments Wikidata modifiés).")
if result.stats["deleted"]:
    notices.append(f"{result.stats['deleted']} page(s) supprimée(s) écartée(s).")
if scoring["rules"]["coauthors"] != "all" and any(e.get("coauthors") for p in result.participants for e in p.evidence):
    notices.append(f"Pages créées à plusieurs : {COAUTHOR_RULES[scoring['rules']['coauthors']].lower()}.")
if notices:
    st.info("\n".join(f"- {n}" for n in notices))

legend = "".join(
    f'<span style="--c:{COLORS[c]}">{CRITERION_SHORT[c]} ({scoring["points"][c]} pt{"s" if scoring["points"][c] > 1 else ""})</span>'
    for c in CRITERIA
)
st.markdown(f'<div class="wj-legend">{legend}</div>', unsafe_allow_html=True)

if result.warnings:
    with st.expander(f"{len(result.warnings)} ligne(s) écartée(s) lors de l’import"):
        st.dataframe(
            pd.DataFrame([{"Fichier": w["source"], "Ligne": w["row"], "Motif": w["message"]} for w in result.warnings]),
            hide_index=True, width="stretch",
        )

labels = [f"{p.rank if p.rank else 'H.C.'}. {p.username}" for p in result.participants]
fig = go.Figure()
for c in CRITERIA:
    fig.add_bar(
        y=labels, x=[p.points[c] for p in result.participants], orientation="h",
        name=CRITERION_SHORT[c], marker_color=COLORS[c],
        hovertemplate=f"{CRITERION_SHORT[c]} : %{{x}} pts<extra></extra>",
    )
fig.update_layout(
    barmode="stack", height=max(260, 38 * len(labels) + 60), margin=dict(l=0, r=10, t=10, b=10),
    yaxis=dict(autorange="reversed"), xaxis=dict(gridcolor="#e6eae6", ticksuffix=" pts"),
    showlegend=False, plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Atkinson Hyperlegible, Segoe UI, sans-serif", color="#1c2633"),
)
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

table = pd.DataFrame([
    {"Rang": p.rank if p.rank else "H.C.", "Contributeur": p.username,
     **{CRITERION_SHORT[c]: p.counts[c] for c in CRITERIA}, "Total": float(p.total)}
    for p in result.participants
])
st.dataframe(table, hide_index=True, width="stretch",
             column_config={"Total": st.column_config.NumberColumn(format="%.2f pts")})

st.download_button(
    "Exporter le classement (CSV)",
    data=ranking_to_csv(result.participants, scoring).encode("utf-8"),
    file_name=f"wikijury-{date.today().isoformat()}.csv" if not campaign else f"wikijury-{slug(campaign)}-{date.today().isoformat()}.csv",
    mime="text/csv",
    type="primary",
)

# ------------------------------------------------------------------------- fiche

st.subheader("Détail d’un contributeur")
who = st.selectbox("Contributeur", [p.username for p in result.participants], label_visibility="collapsed")
p = next(x for x in result.participants if x.username == who)
c1, c2 = st.columns([1, 2])
c1.metric("Total", f"{fmt(p.total)} pts", help="Hors concours" if p.excluded else f"Rang {p.rank}")
if p.context:
    c2.caption(
        "Pour information, sans points : "
        + ", ".join(f"{v} {FIELD_LABELS.get(k, k).lower()}" for k, v in p.context.items())
    )
st.dataframe(
    pd.DataFrame([
        {"Critère": criterion_label(c, scoring), "Nombre": p.counts[c], "Barème": scoring["points"][c], "Points": float(p.points[c])}
        for c in CRITERIA
    ]),
    hide_index=True, width="stretch",
)
if p.evidence:
    rows = []
    for e in p.evidence:
        detail = STATUS_TEXT.get(e["status"], "")
        if e["status"] == "too_short":
            detail += f" ({e['chars']} car., minimum {scoring['thresholds']['article_short_min_chars']})"
        elif e.get("usage"):
            detail += f" ({e['usage']} fois)"
        elif e.get("article"):
            detail += f" dans « {e['article']} »"
        if e.get("coauthors"):
            others = ", ".join(u for u in e["coauthors"] if u != p.username)
            if e["share"] == 0:
                detail += f". Créditée à {e['coauthors'][0]}, premier participant listé (avec {others})"
            elif e["share"] < 1:
                detail += f". Avec {others} : points partagés (1/{len(e['coauthors'])})"
            else:
                detail += f". Avec {others}"
        counted = e["status"] in CRITERIA and e["share"] > 0
        rows.append({
            "Pièce": e["label"], "Statut": detail,
            "Points": round(scoring["points"][e["status"]] * e["share"] * e.get("quantity", 1), 2) if counted else 0,
            "Fichier": e["source"],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ------------------------------------------------------------------------- pied de page

st.markdown(
    '<p class="wj-footer">Les fichiers importés restent sur le serveur le temps de la session et ne sont pas conservés.</p>',
    unsafe_allow_html=True,
)
f1, f2, f3, _ = st.columns([1, 1, 1, 3])
f1.image(str(BRAND / "wikimedia-benin.png"), width=120)
f2.image(str(BRAND / "osm-benin.png"), width=70)
f3.image(str(BRAND / "mapequilibre.png"), width=90)
