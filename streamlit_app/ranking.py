"""WikiJury, version Streamlit : page « Classement ».

Lancement local :  streamlit run streamlit_app/app.py
Le moteur de calcul (package `wikijury`) est le même que celui de la version web :
barème et correspondance des colonnes sont lus dans le dossier `shared/`.
"""

from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from wikijury import (
    ARTICLE_MODES,
    COAUTHOR_RULES,
    CRITERIA,
    CRITERION_SHORT,
    Dataset,
    compute_ranking,
    criterion_label,
    detect_kind,
    enabled_criteria,
    load_columns_spec,
    load_default_scoring,
    map_columns,
    merge_scoring,
    missing_fields,
    wikis_in_data,
)
from wikijury.io import ImportError_, ranking_to_csv, read_upload
from wikijury.scoring import is_grid_criterion, shown_criteria

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "shared" / "brand"
FIXTURES = ROOT / "shared" / "fixtures" / "dashboard"


COLORS = {
    "article_created": "#006699",
    "article_translated": "#6AA9CC",
    "article_long": "#006699",
    "article_short": "#7DB9D6",
    "article_edited": "#A3ADBB",
    "reference_added": "#B5537A",
    "wikidata_item": "#339966",
    "photo_uploaded": "#ECC977",
    "photo_uploaded_used": "#C98A1B",
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
    "translated": "Article traduit",
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
    "photo_uploaded": "Photo téléversée",
    "photo_uploaded_used": "Bonus : photo utilisée",
    "article_edited": "Article amélioré",
    "edit_too_small": "Modification sous le minimum",
    "article_created": "Article créé",
    "article_translated": "Article traduit",
    "reference_added": "Références ajoutées",
    "wikidata_item": "Élément créé",
    "photo_existing_used": "Ajoutée à un article",
    "wiki_excluded": "Wiki non retenu par le jury",
    "photo_usage_unknown": "Usage inconnu : ajoutez l’export « uploads »",
}

SPEC = load_columns_spec()
PRESETS = {p["id"]: p for p in json.loads((ROOT / "shared" / "presets.json").read_text(encoding="utf-8"))["presets"]}
DEFAULT_SCORING = load_default_scoring()
SCORED_KINDS = {"dashboard_articles", "articles", "uploads", "wikidata", "existing_photos"}

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1280px; }
      h1, h2, h3 { letter-spacing: -0.02em; }
      .wj-title { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; margin: 0 0 .25rem; }
      .wj-title.is-empty { color: #a9b3ad; }
      .wj-legend { display: flex; flex-wrap: wrap; gap: .35rem 1.2rem; font-size: .9rem; opacity: .85; margin: .25rem 0 1rem; }
      .wj-legend span::before { content: ""; display: inline-block; width: .75rem; height: .75rem; border-radius: 3px;
        margin-right: .4rem; vertical-align: -.05rem; background: var(--c); }
      .wj-footer { text-align: center; opacity: .8; font-size: .9rem; margin-top: 3rem; }
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
    st.session_state.setdefault("preset", "standard")
    if "mode" not in st.session_state:
        st.session_state["mode"] = DEFAULT_SCORING["rules"]["article_mode"]
        for c in CRITERIA:
            st.session_state[f"en_{c}"] = c in DEFAULT_SCORING["rules"]["enabled"]
            st.session_state[f"cap_{c}"] = 0
    st.session_state.setdefault("campaign", "")
    st.session_state.setdefault("grid_created", "")
    st.session_state.setdefault("grid_edited", "")
    # Streamlit oublie l'état d'un widget qui n'est pas affiché pendant une exécution :
    # on recopie ces valeurs pour qu'un critère masqué garde ses réglages.
    for key in list(st.session_state.keys()):
        if str(key).startswith(("pts_", "th_", "en_", "cap_", "grid_")):
            st.session_state[key] = st.session_state[key]


def reset_scoring() -> None:
    """Rétablit les valeurs du modèle de barème choisi."""
    preset = merge_scoring(DEFAULT_SCORING, PRESETS[st.session_state.preset]["scoring"])
    for c, v in preset["points"].items():
        st.session_state[f"pts_{c}"] = v
    for k, v in preset["thresholds"].items():
        st.session_state[f"th_{k}"] = v
    for c in CRITERIA:
        st.session_state[f"cap_{c}"] = int(preset["rules"].get("caps", {}).get(c, 0))
        st.session_state[f"en_{c}"] = c in enabled_criteria(preset)
    st.session_state["mode"] = preset["rules"].get("article_mode", "tiers")
    for key in ("created", "edited"):
        st.session_state[f"grid_{key}"] = format_grid(preset.get("grids", {}).get(key))


def format_grid(grid) -> str:
    return "\n".join(f"{m} = {str(p).replace('.', ',')}" for m, p in sorted(grid or [], key=lambda t: -t[0]))


def parse_grid(text: str) -> list[list[float]]:
    """Lit « 4000 = 12 » ou « 50 : 1,5 », une ligne par palier ; ignore les lignes illisibles."""
    import re
    tiers = []
    for line in re.split(r"[\n;]+", text or ""):
        m = re.match(r"^\s*(\d+)\s*[=:→-]+\s*(\d+(?:[.,]\d+)?)\s*$", line)
        if m:
            pts = float(m.group(2).replace(",", "."))
            tiers.append([int(m.group(1)), int(pts) if pts.is_integer() else pts])
    return sorted(tiers, key=lambda t: -t[0])


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
        type=["csv", "tsv", "txt", "xlsx", "xls"],
        accept_multiple_files=True,
        help="Exports de l’Outreach Dashboard ou tableaux maison : articles, photos, éléments Wikidata, participants.",
    )

    st.markdown("#### Barème")
    st.selectbox("Type de campagne", list(PRESETS), format_func=lambda k: PRESETS[k]["label"], key="preset", on_change=reset_scoring)
    preset_info = PRESETS[st.session_state.preset]
    st.caption(preset_info.get("description", ""))
    for warning in preset_info.get("unverified", []):
        st.warning(warning, icon="⚠️")
    if preset_info.get("sources"):
        st.caption(
            f"Sources consultées le {preset_info['checked_on']} : "
            + ", ".join(f"[{src['title']}]({src['url']})" for src in preset_info["sources"])
        )
    st.selectbox("Notation des nouveaux articles", list(ARTICLE_MODES), format_func=ARTICLE_MODES.get, key="mode")
    flat = st.session_state.mode != "tiers"
    grid_mode = st.session_state.mode == "grid"
    labels_scoring = {"thresholds": {k.removeprefix("th_"): st.session_state[k] for k in st.session_state if str(k).startswith("th_")}}
    st.caption("Cochez les critères retenus par le règlement du concours.")
    scoring_points, enabled = {}, []
    for c in CRITERIA:
        if (flat and c in ("article_long", "article_short")) or (not flat and c in ("article_created", "article_translated")):
            scoring_points[c] = st.session_state[f"pts_{c}"]
            continue
        label = criterion_label(c, labels_scoring)
        on = st.checkbox(label, key=f"en_{c}")
        by_grid = (grid_mode and c in ("article_created", "article_translated")) or (
            c == "article_edited" and bool(parse_grid(st.session_state.grid_edited))
        )
        scoring_points[c] = st.number_input(
            f"Points : {CRITERION_SHORT[c]}", min_value=0, max_value=1000, step=1, key=f"pts_{c}",
            label_visibility="collapsed", disabled=not on or by_grid,
            help="Points fixés par la grille de paliers" if by_grid else None,
        )
        if on:
            enabled.append(c)
    if grid_mode:
        st.text_area("Grille des articles créés", key="grid_created", height=170,
                     help="Une ligne par palier : caractères minimum = points. Le palier le plus élevé atteint s’applique.")
    elif flat:
        st.number_input("Minimum pour un article créé ou traduit (car.)", min_value=0, step=100, key="th_article_created_min_chars")
    else:
        col_a, col_b = st.columns(2)
        col_a.number_input("Article long (car.)", min_value=0, step=100, key="th_article_long_min_chars")
        col_b.number_input("Article court (car.)", min_value=0, step=100, key="th_article_short_min_chars")
    if "article_edited" in enabled:
        st.number_input("Minimum ajouté pour un article amélioré (car.)", min_value=0, step=100, key="th_article_improved_min_chars")
        st.text_area("Grille des articles améliorés (vide : barème fixe)", key="grid_edited", height=170)
    long_min = st.session_state.th_article_long_min_chars
    short_min = st.session_state.th_article_short_min_chars
    st.selectbox(
        "Pages créées à plusieurs",
        list(COAUTHOR_RULES),
        format_func=COAUTHOR_RULES.get,
        key="rule_coauthors",
        help="L’export du Dashboard liste tous les participants ayant modifié une page, sans dire qui l’a créée.",
    )
    with st.expander("Plafonds par participant"):
        st.caption("Limite les points qu’un participant peut obtenir sur un critère (0 = aucun plafond).")
        caps = {c: st.number_input(CRITERION_SHORT[c], min_value=0, step=10, key=f"cap_{c}") for c in CRITERIA if c in enabled}
    st.button("Rétablir les valeurs du modèle", on_click=reset_scoring, width="stretch")

scoring = merge_scoring(DEFAULT_SCORING, {
    "points": scoring_points,
    "thresholds": {k: int(st.session_state[f"th_{k}"]) for k in DEFAULT_SCORING["thresholds"]},
    "rules": {
        "article_mode": st.session_state.mode,
        "enabled": enabled + [c for c in CRITERIA if c not in enabled and st.session_state.get(f"en_{c}") and c in (
            ("article_long", "article_short") if flat else ("article_created", "article_translated"))],
        "coauthors": st.session_state.rule_coauthors,
        "caps": {c: v for c, v in caps.items() if v > 0},
    },
    "grids": {"created": parse_grid(st.session_state.grid_created), "edited": parse_grid(st.session_state.grid_edited)},
})
scoring_valid = flat or short_min < long_min
SHOWN = shown_criteria(scoring)

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
if unknown_photos and any(c in enabled_criteria(scoring) for c in ("photo_uploaded", "photo_uploaded_used")):
    notices.append(f"{unknown_photos} photo(s) téléversée(s) non notée(s) : l’export « articles » ne donne pas leur nombre d’utilisations. Ajoutez l’export « uploads » du Dashboard pour les noter.")
if result.stats["ignored"]:
    notices.append(f"{fmt(result.stats['ignored'])} page(s) hors critères ignorée(s) (pages de discussion ou utilisateur, éléments Wikidata modifiés, autres espaces de noms).")
if result.stats["deleted"]:
    notices.append(f"{result.stats['deleted']} page(s) supprimée(s) écartée(s).")
if scoring["rules"]["coauthors"] != "all" and any(e.get("coauthors") for p in result.participants for e in p.evidence):
    notices.append(f"Pages créées à plusieurs : {COAUTHOR_RULES[scoring['rules']['coauthors']].lower()}.")
capped = sum(1 for p in result.participants if p.capped)
if capped:
    notices.append(f"Plafonds appliqués : {capped} participant(s) concerné(s).")
if notices:
    st.info("\n".join(f"- {n}" for n in notices))

legend = "".join(
    f'<span style="--c:{COLORS[c]}">{CRITERION_SHORT[c]} ({"grille" if is_grid_criterion(c, scoring) else str(scoring["points"][c]) + (" pts" if scoring["points"][c] > 1 else " pt")})</span>'
    for c in SHOWN
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
for c in SHOWN:
    fig.add_bar(
        y=labels, x=[p.points[c] for p in result.participants], orientation="h",
        name=CRITERION_SHORT[c], marker_color=COLORS[c],
        hovertemplate=f"{CRITERION_SHORT[c]} : %{{x}} pts<extra></extra>",
    )
dark = getattr(getattr(st.context, "theme", None), "type", "light") == "dark"
fig.update_layout(
    barmode="stack", height=max(260, 38 * len(labels) + 60), margin=dict(l=0, r=10, t=10, b=10),
    yaxis=dict(autorange="reversed"), xaxis=dict(gridcolor="#313945" if dark else "#e6eae6", ticksuffix=" pts"),
    showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Atkinson Hyperlegible, Segoe UI, sans-serif", color="#e8ecf1" if dark else "#1c2633"),
)
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

table = pd.DataFrame([
    {"Rang": p.rank if p.rank else "H.C.", "Contributeur": p.username,
     **{CRITERION_SHORT[c]: p.counts[c] for c in SHOWN}, "Total": float(p.total)}
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
        {"Critère": criterion_label(c, scoring) + (" (plafonné)" if c in p.capped else ""), "Nombre": p.counts[c], "Barème": scoring["points"][c], "Points": float(p.points[c])}
        for c in SHOWN
    ]),
    hide_index=True, width="stretch",
)
if p.evidence:
    rows = []
    for e in p.evidence:
        if e.get("bonus"):
            continue  # fusionné avec la ligne de la photo
        detail = STATUS_TEXT.get(e["status"], "")
        if e["status"] == "reference_added":
            detail = f"{e['quantity']} référence(s) ajoutée(s)"
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
        def pts(x):
            ok = x["status"] in CRITERIA and x["share"] > 0
            return scoring["points"][x["status"]] * x["share"] * x.get("quantity", 1) if ok else 0
        value = pts(e)
        if e["type"] == "upload":
            value += sum(pts(b) for b in p.evidence if b.get("bonus") and b["label"] == e["label"])
        rows.append({"Pièce": e["label"], "Statut": detail, "Points": round(value, 2), "Fichier": e["source"]})
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
