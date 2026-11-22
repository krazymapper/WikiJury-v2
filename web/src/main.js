import '@fontsource/atkinson-hyperlegible/400.css';
import '@fontsource/atkinson-hyperlegible/700.css';
import '@fontsource/schibsted-grotesk/500.css';
import '@fontsource/schibsted-grotesk/700.css';
import '@fontsource/schibsted-grotesk/800.css';
import './styles.css';

import columnsSpec from '../../shared/columns.json';
import defaultScoring from '../../shared/scoring.default.json';
import presetsSpec from '../../shared/presets.json';
import content from '../../shared/content.json';
import { detectKind, mapColumns, missingFields } from './engine/columns.js';
import { ARTICLE_MODES, COAUTHOR_RULES, CRITERIA, CRITERION_SHORT, computeRanking, criterionLabel, enabledCriteria, isGridCriterion, mergeScoring, shownCriteria, wikisInData } from './engine/scoring.js';
import { normalizeUsername } from './engine/normalize.js';
import { download, parseCsvText, parseFile, rankingToCsv, slugify } from './io.js';
import { SAMPLE_FILES } from './sample.js';

/* ------------------------------------------------------------------ état */

const STORAGE_KEY = 'wikijury:v3';
const SCORED_KINDS = ['dashboard_articles', 'articles', 'uploads', 'wikidata', 'existing_photos'];

const stored = loadStored();
const state = {
  files: [],
  scoring: mergeScoring(defaultScoring, stored.scoring),
  campaign: stored.campaign ?? '',
  preset: stored.preset ?? 'standard',
  excluded: stored.excluded ?? [],
  result: { participants: [], warnings: [], stats: { deleted: 0, ignored: 0 } },
};
let nextId = 1;

function loadStored() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) ?? {};
  } catch {
    return {};
  }
}

function persist() {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ scoring: state.scoring, campaign: state.campaign, excluded: state.excluded, preset: state.preset }),
    );
  } catch {
    /* stockage indisponible (navigation privée) : sans conséquence */
  }
}

/* ------------------------------------------------------------- utilitaires */

const $ = (sel) => document.querySelector(sel);
const fmt = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 });
const plural = (n, one, many) => `${fmt.format(n)} ${Math.abs(n) >= 2 ? many : one}`;

/** Remplace le contenu d'un élément en ignorant les enfants vides (null, false). */
function mount(el, ...children) {
  el.replaceChildren(...children.flat().filter((c) => c !== null && c !== undefined && c !== false));
}

/** Crée un élément sans jamais interpréter de HTML venant des fichiers. */
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'text') el.textContent = value;
    else if (key === 'style') for (const [p, v] of Object.entries(value)) el.style.setProperty(p, v);
    else if (key.startsWith('on')) el.addEventListener(key.slice(2), value);
    else if (value === true) el.setAttribute(key, '');
    else el.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

const isScoringValid = () =>
  state.scoring.rules.article_mode !== 'tiers' ||
  state.scoring.thresholds.article_short_min_chars < state.scoring.thresholds.article_long_min_chars;

/* ---------------------------------------------------------------- calcul */

function usableDatasets() {
  return state.files
    .filter((f) => !f.error && f.kind && missingFields(f.mapping, columnsSpec.kinds[f.kind]).length === 0)
    .map((f) => ({ kind: f.kind, mapping: f.mapping, rows: f.rows, source: f.name }));
}

function recompute() {
  state.result = isScoringValid()
    ? computeRanking(usableDatasets(), state.scoring, { excluded: state.excluded })
    : state.result;
  render();
}

/* --------------------------------------------------------------- fichiers */

async function addFiles(fileList) {
  for (const file of fileList) {
    const entry = { id: nextId++, name: file.name, headers: [], rows: [], kind: null, mapping: {}, error: null };
    try {
      Object.assign(entry, await parseFile(file));
      applyDetection(entry);
    } catch (err) {
      entry.error = err.message || 'Lecture impossible.';
    }
    state.files.push(entry);
  }
  recompute();
}

function applyDetection(entry) {
  if (entry.headers.length === 0) {
    entry.error = 'Aucune colonne trouvée : vérifiez que la première ligne contient les en-têtes.';
    return;
  }
  const detected = detectKind(entry.headers, entry.name, columnsSpec);
  entry.confidence = detected.confidence;
  entry.kind = detected.kind ?? 'articles';
  entry.mapping = detected.mapping ?? mapColumns(entry.headers, columnsSpec.kinds[entry.kind]);
}

function loadSample() {
  state.files = SAMPLE_FILES.map(({ name, text }) => {
    const entry = { id: nextId++, name, kind: null, mapping: {}, error: null, ...parseCsvText(text) };
    applyDetection(entry);
    return entry;
  });
  if (!state.campaign) {
    state.campaign = 'Concours d’exemple (données fictives)';
    $('[data-campaign]').value = state.campaign;
  }
  persist();
  recompute();
}

/* ---------------------------------------------------------------- rendu */

function render() {
  const activeId = document.activeElement?.id;
  renderFiles();
  renderScoring();
  renderExcluded();
  renderStage();
  const hasRanking = state.result.participants.length > 0;
  for (const btn of document.querySelectorAll('[data-action="export"], [data-action="print"]')) btn.disabled = !hasRanking;
  // Les panneaux sont reconstruits : on rend le focus clavier à l'élément équivalent.
  if (activeId) document.getElementById(activeId)?.focus();
}

function renderFiles() {
  const list = $('[data-file-list]');
  mount(list, ...state.files.map(fileItem));
}

function fileItem(file) {
  const remove = h('button', {
    type: 'button',
    class: 'icon-btn',
    'aria-label': `Retirer ${file.name}`,
    title: 'Retirer ce fichier',
    onclick: () => {
      state.files = state.files.filter((f) => f.id !== file.id);
      recompute();
    },
  }, '×');

  if (file.error) {
    return h('li', { class: 'file is-error' },
      h('div', { class: 'file-head' }, h('span', { class: 'file-name', text: file.name }), remove),
      h('p', { class: 'file-status', role: 'alert', text: file.error }),
    );
  }

  const spec = file.kind ? columnsSpec.kinds[file.kind] : null;
  const missing = spec ? missingFields(file.mapping, spec) : [];
  const selectId = `kind-${file.id}`;

  const kindSelect = h('select', {
    id: selectId,
    class: 'select select-sm',
    onchange: (e) => {
      file.kind = e.target.value || null;
      file.mapping = file.kind ? mapColumns(file.headers, columnsSpec.kinds[file.kind]) : {};
      recompute();
    },
  },
  ...Object.entries(columnsSpec.kinds).map(([kind, k]) => h('option', { value: kind, selected: kind === file.kind, text: k.label })),
  h('option', { value: '', selected: !file.kind, text: 'Ne pas utiliser ce fichier' }));

  let status;
  if (spec?.unusable) status = h('p', { class: 'file-status is-warn', text: spec.description });
  else if (!file.kind) status = h('p', { class: 'file-status is-muted', text: 'Fichier ignoré.' });
  else if (missing.length) status = h('p', { class: 'file-status is-warn', text: `${plural(missing.length, 'colonne', 'colonnes')} à associer avant le calcul.` });
  else {
    const note = { editors: 'sert de liste des participants', translations: 'sert à repérer les traductions' }[file.kind] ?? 'prises en compte';
    status = h('p', { class: 'file-status is-ok', text: `${plural(file.rows.length, 'ligne', 'lignes')}, ${note}.` });
  }

  const mappingRows = spec
    ? Object.entries(spec.fields).map(([field, f]) => {
        const id = `map-${file.id}-${field}`;
        return h('div', { class: 'map-row' },
          h('label', { for: id, text: `${FIELD_LABELS[field] ?? field}${f.required ? '' : ' (facultatif)'}` }),
          h('select', {
            id,
            class: 'select select-sm',
            onchange: (e) => {
              file.mapping[field] = e.target.value || null;
              recompute();
            },
          },
          h('option', { value: '', text: '— aucune —' }),
          ...file.headers.map((header) => h('option', { value: header, selected: file.mapping[field] === header, text: header }))),
        );
      })
    : [];

  return h('li', { class: `file${missing.length || spec?.unusable ? ' is-warn' : ''}` },
    h('div', { class: 'file-head' }, h('span', { class: 'file-name', text: file.name, title: file.name }), remove),
    h('label', { class: 'visually-hidden', for: selectId, text: `Type du fichier ${file.name}` }),
    kindSelect,
    status,
    spec && !spec.unusable ? h('details', { class: 'mapping', open: missing.length > 0 },
      h('summary', { text: 'Colonnes utilisées' }),
      ...mappingRows) : null,
  );
}

const FIELD_LABELS = {
  username: 'Contributeur',
  title: 'Titre de l’article',
  characters: 'Caractères ajoutés',
  new: 'Créé pendant la campagne',
  filename: 'Nom du fichier',
  usage_count: 'Nombre d’utilisations',
  item: 'Identifiant Wikidata',
  quantity: 'Nombre d’éléments',
  article: 'Article',
  usernames: 'Participants',
  wiki: 'Wiki',
  namespace: 'Espace de noms',
  deleted: 'Supprimé',
  course: 'Campagne',
  edits: 'Modifications',
  bytes: 'Octets ajoutés',
  references: 'Références ajoutées',
};

// Le panneau du barème est construit une fois puis mis à jour sur place :
// le reconstruire ferait perdre le focus clavier pendant la saisie.
let scoringUi = null;

function renderScoring() {
  if (!scoringUi) scoringUi = buildScoring();
  const sc = state.scoring;
  const mode = sc.rules.article_mode;
  const flat = mode !== 'tiers';
  const gridCreated = mode === 'grid';
  const gridEdited = Boolean(sc.grids?.edited?.length);
  const enabled = new Set(enabledCriteria(sc));
  for (const c of CRITERIA) {
    const on = enabled.has(c);
    scoringUi.labels[c].textContent = criterionLabel(c, sc);
    scoringUi.toggles[c].checked = on;
    const byGrid = (gridCreated && (c === 'article_created' || c === 'article_translated')) || (gridEdited && c === 'article_edited');
    scoringUi.points[c].disabled = !on || byGrid;
    scoringUi.points[c].title = byGrid ? 'Points fixés par la grille de paliers' : '';
    scoringUi.rows[c].classList.toggle('is-off', !on);
    scoringUi.rows[c].hidden = flat ? ['article_long', 'article_short'].includes(c) : ['article_created', 'article_translated'].includes(c);
    if (document.activeElement !== scoringUi.points[c]) scoringUi.points[c].value = String(sc.points[c]);
  }
  scoringUi.mode.value = sc.rules.article_mode;
  scoringUi.thresholdRows.article_created_min_chars.hidden = mode !== 'flat';
  scoringUi.gridRows.created.hidden = !gridCreated;
  scoringUi.gridRows.edited.hidden = !enabled.has('article_edited');
  for (const key of ['created', 'edited']) {
    if (document.activeElement !== scoringUi.grids[key]) scoringUi.grids[key].value = formatGrid(sc.grids?.[key]);
  }
  scoringUi.thresholdRows.article_long_min_chars.hidden = flat;
  scoringUi.thresholdRows.article_short_min_chars.hidden = flat;
  scoringUi.thresholdRows.article_improved_min_chars.hidden = !enabled.has('article_edited');
  const valid = isScoringValid();
  for (const [key, input] of Object.entries(scoringUi.thresholds)) {
    if (document.activeElement !== input) input.value = String(sc.thresholds[key] ?? 0);
    const tierField = key === 'article_long_min_chars' || key === 'article_short_min_chars';
    if (valid || !tierField) {
      input.removeAttribute('aria-invalid');
      input.removeAttribute('aria-describedby');
    } else {
      input.setAttribute('aria-invalid', 'true');
      input.setAttribute('aria-describedby', 'th-error');
    }
  }
  scoringUi.error.hidden = valid;
  scoringUi.coauthors.value = sc.rules.coauthors;
  scoringUi.preset.value = state.preset;
  const preset = presetsSpec.presets.find((x) => x.id === state.preset);
  scoringUi.presetHelp.textContent = preset?.description ?? '';
  mount(scoringUi.presetSources,
    preset?.unverified?.length ? h('ul', { class: 'preset-warn' }, ...preset.unverified.map((t) => h('li', { text: t }))) : null,
    preset?.sources?.length
      ? h('p', { class: 'rules-help' }, `Sources consultées le ${new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long' }).format(new Date(preset.checked_on))} : `,
          ...preset.sources.flatMap((src, i) => [i ? ', ' : '', h('a', { href: src.url, target: '_blank', rel: 'noopener noreferrer', text: src.title })]))
      : null);
  for (const c of CRITERIA) {
    const cap = sc.rules.caps?.[c];
    if (document.activeElement !== scoringUi.caps[c]) scoringUi.caps[c].value = cap ? String(cap) : '';
    scoringUi.capLabels[c].textContent = CRITERION_SHORT[c];
    scoringUi.capRows[c].hidden = !shownCriteria(sc).includes(c);
  }
  const activeCaps = shownCriteria(sc).filter((c) => Number(sc.rules.caps?.[c]) > 0).length;
  scoringUi.capsSummary.textContent = activeCaps ? `Plafonds par participant (${activeCaps} actif${activeCaps > 1 ? 's' : ''})` : 'Plafonds par participant';
  renderWikis();
}

/** Cases à cocher des Wikipédias trouvées dans l'export « articles » du Dashboard. */
function renderWikis() {
  const box = scoringUi.wikis;
  const wikis = wikisInData(usableDatasets());
  box.hidden = wikis.length < 2;
  if (box.hidden) return;
  const excluded = new Set(state.scoring.rules.excluded_wikis);
  mount(box, 
    h('legend', { class: 'rules-label', text: 'Wikipédias prises en compte' }),
    ...wikis.map((wiki) => {
      const id = `wiki-${wiki}`;
      return h('div', { class: 'check' },
        h('input', {
          type: 'checkbox',
          id,
          checked: !excluded.has(wiki),
          onchange: (e) => {
            const set = new Set(state.scoring.rules.excluded_wikis);
            if (e.target.checked) set.delete(wiki);
            else set.add(wiki);
            state.scoring.rules.excluded_wikis = [...set].sort();
            persist();
            recompute();
          },
        }),
        h('label', { for: id, text: wiki.replace('.wikipedia.org', '') + '.wikipedia' }));
    }),
  );
}

function buildScoring() {
  const ui = { labels: {}, points: {}, toggles: {}, rows: {}, thresholds: {}, thresholdRows: {}, error: null, caps: {}, capLabels: {}, capRows: {} };
  ui.preset = h('select', {
    id: 'preset',
    class: 'select select-sm',
    onchange: (e) => applyPreset(e.target.value),
  }, ...presetsSpec.presets.map((x) => h('option', { value: x.id, text: x.label })));
  ui.presetHelp = h('p', { class: 'rules-help' });
  ui.presetSources = h('div', { class: 'preset-sources' });
  ui.grids = {};
  ui.gridRows = {};
  for (const [key, label] of [['created', 'Grille des articles créés'], ['edited', 'Grille des articles améliorés (vide : barème fixe)']]) {
    const id = `grid-${key}`;
    ui.grids[key] = h('textarea', {
      id,
      class: 'grid-input',
      rows: '4',
      spellcheck: 'false',
      placeholder: '4000 = 12\n1000 = 4\n1 = 1',
      'aria-describedby': 'grid-help',
      onchange: (e) => {
        state.scoring.grids = { ...(state.scoring.grids ?? {}), [key]: parseGrid(e.target.value) };
        e.target.value = formatGrid(state.scoring.grids[key]);
        persist();
        recompute();
      },
    });
    ui.gridRows[key] = h('div', { class: 'grid-row' }, h('label', { for: id, class: 'rules-label', text: label }), ui.grids[key]);
  }
  ui.mode = h('select', {
    id: 'article-mode',
    class: 'select select-sm',
    onchange: (e) => {
      state.scoring.rules.article_mode = e.target.value;
      persist();
      recompute();
    },
  }, ...Object.entries(ARTICLE_MODES).map(([value, text]) => h('option', { value, text })));

  const capRows = CRITERIA.map((c) => {
    const id = `cap-${c}`;
    ui.capLabels[c] = h('label', { for: id, class: 'score-label' });
    ui.caps[c] = h('input', {
      id,
      type: 'number',
      inputmode: 'numeric',
      min: '0',
      step: '10',
      placeholder: 'aucun',
      onchange: (e) => {
        const v = Math.max(0, Math.trunc(Number(e.target.value) || 0));
        const caps = { ...(state.scoring.rules.caps ?? {}) };
        if (v > 0) caps[c] = v;
        else delete caps[c];
        state.scoring.rules.caps = caps;
        persist();
        recompute();
      },
    });
    ui.capRows[c] = h('div', { class: 'score-row' },
      h('span', { class: `swatch c-${c}`, 'aria-hidden': 'true' }),
      ui.capLabels[c],
      h('span', { class: 'score-input is-wide' }, ui.caps[c], h('span', { class: 'unit', 'aria-hidden': 'true', text: 'pts max' })));
    return ui.capRows[c];
  });
  ui.capsSummary = h('summary', { class: 'rules-label' });
  ui.capsBox = h('details', { class: 'caps' },
    ui.capsSummary,
    h('p', { class: 'rules-help', text: 'Limite les points qu’un participant peut obtenir sur un critère, par exemple pour éviter qu’un grand nombre de petites modifications l’emporte sur le contenu. Laissez vide pour ne rien limiter.' }),
    h('div', { class: 'score-list' }, ...capRows));
  ui.coauthors = h('select', {
    id: 'rule-coauthors',
    class: 'select select-sm',
    onchange: (e) => {
      state.scoring.rules.coauthors = e.target.value;
      persist();
      recompute();
    },
  }, ...Object.entries(COAUTHOR_RULES).map(([value, text]) => h('option', { value, text })));
  ui.wikis = h('fieldset', { class: 'wikis', hidden: true });

  const pointsRows = CRITERIA.map((c) => {
    const id = `pts-${c}`;
    ui.toggles[c] = h('input', {
      type: 'checkbox',
      id: `en-${c}`,
      class: 'toggle',
      'aria-label': `Activer : ${CRITERION_SHORT[c]}`,
      onchange: (e) => toggleCriterion(c, e.target.checked),
    });
    ui.labels[c] = h('label', { for: id, class: 'score-label' });
    ui.points[c] = h('input', {
      id,
      type: 'number',
      inputmode: 'numeric',
      min: '0',
      max: '1000',
      step: '1',
      onchange: (e) => updatePoints(c, e.target),
    });
    ui.rows[c] = h('div', { class: 'score-row has-toggle' },
      ui.toggles[c],
      h('span', { class: `swatch c-${c}`, 'aria-hidden': 'true' }),
      ui.labels[c],
      h('span', { class: 'score-input' }, ui.points[c], h('span', { class: 'unit', 'aria-hidden': 'true', text: 'pt' })));
    return ui.rows[c];
  });

  const threshold = (key, label) => {
    const id = `th-${key}`;
    ui.thresholds[key] = h('input', {
      id,
      type: 'number',
      inputmode: 'numeric',
      min: '0',
      step: '100',
      onchange: (e) => {
        state.scoring.thresholds[key] = Math.max(0, Math.trunc(Number(e.target.value) || 0));
        e.target.value = String(state.scoring.thresholds[key]);
        persist();
        recompute();
      },
    });
    ui.thresholdRows[key] = h('div', { class: 'threshold' },
      h('label', { for: id, text: label }),
      h('span', { class: 'score-input is-wide' }, ui.thresholds[key], h('span', { class: 'unit', 'aria-hidden': 'true', text: 'car.' })));
    return ui.thresholdRows[key];
  };

  ui.error = h('p', {
    id: 'th-error',
    class: 'field-error',
    role: 'alert',
    hidden: true,
    text: 'Le seuil de l’article court doit être inférieur à celui de l’article long. Le classement affiché reste celui du dernier barème valide.',
  });

  mount($('[data-scoring]'),
    h('div', { class: 'preset' },
      h('label', { for: 'preset', class: 'rules-label', text: 'Type de campagne' }),
      ui.preset,
      ui.presetHelp,
      ui.presetSources),
    h('div', { class: 'preset' },
      h('label', { for: 'article-mode', class: 'rules-label', text: 'Notation des nouveaux articles' }),
      ui.mode),
    h('p', { class: 'rules-help', text: 'Cochez les critères retenus par le règlement du concours.' }),
    h('div', { class: 'score-list' }, ...pointsRows),
    h('div', { class: 'thresholds' },
      threshold('article_created_min_chars', 'Minimum pour un article créé ou traduit'),
      threshold('article_long_min_chars', 'Article long à partir de'),
      threshold('article_short_min_chars', 'Article court à partir de'),
      threshold('article_improved_min_chars', 'Minimum ajouté pour un article amélioré'),
      ui.gridRows.created,
      ui.gridRows.edited,
      h('p', { id: 'grid-help', class: 'rules-help', text: 'Une ligne par palier : caractères minimum = points. Le palier le plus élevé atteint s’applique ; sous le dernier palier, la contribution ne rapporte rien.' }),
      ui.error),
    h('div', { class: 'rules' },
      h('label', { for: 'rule-coauthors', class: 'rules-label', text: 'Pages créées à plusieurs' }),
      ui.coauthors,
      h('p', { class: 'rules-help', text: 'L’export du Dashboard liste tous les participants ayant modifié une page, sans dire qui l’a créée.' }),
      ui.wikis,
      ui.capsBox),
  );
  return ui;
}

const numberFr = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2, useGrouping: false });

function formatGrid(grid) {
  return [...(grid ?? [])].sort((a, b) => b[0] - a[0]).map(([min, pts]) => `${min} = ${numberFr.format(pts)}`).join('\n');
}

/** Lit « 4000 = 12 » ou « 50 : 1,5 », une ligne par palier ; ignore les lignes illisibles. */
function parseGrid(text) {
  const tiers = [];
  for (const line of String(text).split(/[\n;]+/)) {
    const m = line.match(/^\s*(\d+)\s*[=:→-]+\s*(\d+(?:[.,]\d+)?)\s*$/);
    if (m) tiers.push([Number(m[1]), Number(m[2].replace(',', '.'))]);
  }
  return tiers.sort((a, b) => b[0] - a[0]);
}

function toggleCriterion(criterion, on) {
  const set = new Set(enabledCriteria(state.scoring));
  if (on) set.add(criterion);
  else set.delete(criterion);
  state.scoring.rules.enabled = CRITERIA.filter((c) => set.has(c));
  persist();
  recompute();
}

function applyPreset(id) {
  const preset = presetsSpec.presets.find((x) => x.id === id) ?? presetsSpec.presets[0];
  const { coauthors, excluded_wikis } = state.scoring.rules;
  state.preset = preset.id;
  state.scoring = mergeScoring(mergeScoring(defaultScoring, preset.scoring), { rules: { coauthors, excluded_wikis } });
  state.scoring.grids = { created: [], edited: [], ...(preset.scoring.grids ?? {}) };
  persist();
  recompute();
}

function updatePoints(criterion, input) {
  const value = Math.trunc(Number(input.value));
  state.scoring.points[criterion] = Number.isFinite(value) ? Math.min(1000, Math.max(0, value)) : 0;
  input.value = String(state.scoring.points[criterion]);
  persist();
  recompute();
}

function renderExcluded() {
  const panel = $('[data-excluded-panel]');
  panel.hidden = state.excluded.length === 0;
  mount($('[data-excluded-list]'), 
    ...state.excluded.map((name) =>
      h('li', {},
        h('span', { text: name }),
        h('button', { type: 'button', class: 'btn-text', 'aria-label': `Réintégrer ${name} au classement`, onclick: () => toggleExcluded(name), text: 'Réintégrer' })),
    ),
  );
}

function toggleExcluded(name) {
  const n = normalizeUsername(name);
  state.excluded = state.excluded.includes(n) ? state.excluded.filter((x) => x !== n) : [...state.excluded, n];
  persist();
  recompute();
}

/* --------------------------------------------------------------- scène */

function renderStage() {
  const stage = $('[data-stage]');
  const summary = $('[data-summary]');
  const scored = usableDatasets().some((d) => SCORED_KINDS.includes(d.kind));
  const { participants, warnings } = state.result;

  if (!scored) {
    summary.textContent = '';
    mount(stage, emptyState());
    return;
  }

  const ranked = participants.filter((p) => !p.excluded);
  const totalPoints = ranked.reduce((s, p) => s + p.total, 0);
  summary.textContent = `${plural(ranked.length, 'participant classé', 'participants classés')}, ${plural(totalPoints, 'point attribué', 'points attribués')}.`;

  mount(stage, 
    legend(),
    notices(),
    warnings.length ? warningsBlock(warnings) : null,
    rankingTable(participants),
  );
}

function notices() {
  const { stats, participants } = state.result;
  const items = [];
  const unknownPhotos = participants.reduce((n, p) => n + p.evidence.filter((e) => e.status === 'photo_usage_unknown' && e.share > 0).length, 0);
  const photosScored = ['photo_uploaded', 'photo_uploaded_used'].some((c) => enabledCriteria(state.scoring).includes(c));
  if (unknownPhotos > 0 && photosScored) {
    items.push(`${plural(unknownPhotos, 'photo téléversée n’est pas notée', 'photos téléversées ne sont pas notées')} : l’export « articles » ne donne pas leur nombre d’utilisations. Ajoutez l’export « uploads » du Dashboard pour les noter.`);
  }
  if (stats.ignored > 0) {
    items.push(`${plural(stats.ignored, 'page hors critères ignorée', 'pages hors critères ignorées')} (pages de discussion ou utilisateur, éléments Wikidata modifiés, autres espaces de noms).`);
  }
  const capped = participants.filter((p) => p.capped.length).length;
  if (capped > 0) items.push(`Plafonds appliqués : ${plural(capped, 'participant concerné', 'participants concernés')}.`);
  if (stats.deleted > 0) items.push(`${plural(stats.deleted, 'page supprimée écartée', 'pages supprimées écartées')}.`);
  if (state.scoring.rules.coauthors !== 'all' && participants.some((p) => p.evidence.some((e) => e.coauthors))) {
    items.push(`Pages créées à plusieurs : ${COAUTHOR_RULES[state.scoring.rules.coauthors].toLowerCase()}.`);
  }
  return items.length ? h('ul', { class: 'notices' }, ...items.map((t) => h('li', { text: t }))) : null;
}

function emptyState() {
  const steps = [
    ['Exportez vos données', 'Les fichiers CSV « articles », « uploads » et « editors » de l’Outreach Dashboard suffisent. Des tableaux maison sont aussi acceptés.'],
    ['Déposez les fichiers', 'WikiJury reconnaît le type de chaque fichier et ses colonnes. Vous pouvez corriger son choix.'],
    ['Ajustez le barème', 'Les points et les seuils de taille se modifient dans le panneau « Barème » ; le classement se met à jour aussitôt.'],
  ];
  return h('section', { class: 'empty', 'aria-labelledby': 'empty-title' },
    h('h2', { id: 'empty-title', class: 'empty-title', text: 'Un classement que chaque participant peut vérifier.' }),
    h('p', { class: 'empty-lead', text: 'Chaque point attribué renvoie à l’article, la photo ou l’élément Wikidata qui l’a rapporté.' }),
    h('ol', { class: 'steps' }, ...steps.map(([t, d]) => h('li', {}, h('strong', { text: t }), h('span', { text: d })))),
    h('div', { class: 'empty-actions' },
      h('button', { type: 'button', class: 'btn btn-primary', onclick: () => $('[data-file-input]').click(), text: 'Choisir des fichiers' }),
      h('button', { type: 'button', class: 'btn btn-quiet', onclick: loadSample, text: 'Essayer avec des données d’exemple' }),
    ),
  );
}

function legend() {
  return h('ul', { class: 'legend', 'aria-label': 'Légende des critères' },
    ...shownCriteria(state.scoring).map((c) => h('li', {},
      h('span', { class: `swatch c-${c}`, 'aria-hidden': 'true' }),
      `${CRITERION_SHORT[c]} (${isGridCriterion(c, state.scoring) ? 'grille' : plural(state.scoring.points[c], 'pt', 'pts')})`)));
}

function warningsBlock(warnings) {
  return h('details', { class: 'warnings' },
    h('summary', {}, `${plural(warnings.length, 'ligne écartée', 'lignes écartées')} lors de l’import`),
    h('ul', {}, ...warnings.slice(0, 200).map((w) => h('li', {},
      h('span', { class: 'warn-src', text: `${w.source}, ligne ${w.row}` }),
      h('span', { text: w.message })))),
    warnings.length > 200 ? h('p', { class: 'is-muted', text: `… et ${warnings.length - 200} autres.` }) : null,
  );
}

function rankingTable(participants) {
  const max = Math.max(1, ...participants.map((p) => p.total));
  const ticks = max <= 60;

  const rows = participants.map((p) => {
    const segments = CRITERIA.filter((c) => p.points[c] > 0).map((c) =>
      h('span', {
        class: `seg c-${c}${Number.isInteger(p.points[c]) ? '' : ' no-ticks'}`,
        style: { width: `${(p.points[c] / max) * 100}%`, '--n': Number.isInteger(p.points[c]) ? String(p.points[c]) : null },
        title: `${CRITERION_SHORT[c]} : ${p.counts[c]} × ${state.scoring.points[c]} = ${p.points[c]} pts`,
      }));
    const tie = p.rank !== null && participants.filter((o) => o.rank === p.rank).length > 1;
    return h('tr', { class: `${p.excluded ? 'is-excluded' : ''} ${p.rank && p.rank <= 3 ? `is-top top-${p.rank}` : ''}` },
      h('td', { class: 'col-rank' },
        p.excluded
          ? h('span', { class: 'rank-out', text: 'H.C.', title: 'Hors concours' })
          : h('span', { class: 'rank' }, String(p.rank), tie ? h('span', { class: 'tie', text: ' ex æquo' }) : null)),
      h('th', { scope: 'row', class: 'col-name' },
        h('button', { type: 'button', class: 'name-btn', onclick: (e) => openSheet(p.username, e.currentTarget), text: p.username })),
      h('td', { class: 'col-bar' },
        h('div', { class: `bar${ticks ? ' has-ticks' : ''}`, role: 'img', 'aria-label': describePoints(p) }, ...segments)),
      h('td', { class: 'col-total' }, h('span', { class: 'total', text: fmt.format(p.total) }), h('span', { class: 'total-unit', text: ' pts' })),
    );
  });

  return h('table', { class: 'ranking' },
    h('caption', { class: 'visually-hidden', text: 'Classement des participants. Sélectionnez un nom pour voir le détail des points.' }),
    h('thead', {}, h('tr', {},
      h('th', { scope: 'col', class: 'col-rank', text: 'Rang' }),
      h('th', { scope: 'col', class: 'col-name', text: 'Contributeur' }),
      h('th', { scope: 'col', class: 'col-bar', text: 'Origine des points' }),
      h('th', { scope: 'col', class: 'col-total', text: 'Total' }))),
    h('tbody', {}, ...rows));
}

function describePoints(p) {
  const parts = CRITERIA.filter((c) => p.points[c] > 0).map((c) => `${CRITERION_SHORT[c]} ${p.points[c]}`);
  return parts.length ? parts.join(', ') : 'Aucun point';
}

/* ----------------------------------------------------- fiche contributeur */

const STATUS_TEXT = {
  article_long: () => 'Article long',
  article_short: () => 'Article court',
  too_short: (e) => `Trop court : ${fmt.format(e.chars)} car., minimum ${fmt.format(state.scoring.rules.article_mode === 'flat' ? state.scoring.thresholds.article_created_min_chars : state.scoring.thresholds.article_short_min_chars)}`,
  not_new: () => 'Non créé pendant la campagne',
  wiki_excluded: (e) => `${e.wiki} n’est pas retenue par le jury`,
  photo_usage_unknown: () => 'Usage inconnu : ajoutez l’export « uploads »',
  photo_uploaded: (e) => (e.usage > 0 ? `Utilisée ${plural(e.usage, 'fois', 'fois')}` : 'Non utilisée dans un article'),
  photo_uploaded_used: (e) => `Utilisée ${plural(e.usage, 'fois', 'fois')}`,
  article_edited: (e) => (e.chars !== undefined ? `Article amélioré : ${fmt.format(e.chars)} car. ajoutés` : 'Article existant modifié'),
  edit_too_small: (e) => `Modification sous le minimum : ${fmt.format(e.chars)} car., minimum ${fmt.format(state.scoring.thresholds.article_improved_min_chars)}`,
  article_created: (e) => `Article créé : ${fmt.format(e.chars)} car.${e.unit !== undefined ? ` (palier à ${fmt.format(e.unit)} pt)` : ''}`,
  article_translated: (e) => `Article traduit : ${fmt.format(e.chars)} car.`,
  reference_added: (e) => plural(e.quantity, 'référence ajoutée', 'références ajoutées'),
  photo_unused: () => 'Non utilisée dans un article',
  wikidata_item: () => 'Élément créé',
  photo_existing_used: (e) => (e.article ? `Ajoutée à « ${e.article} »` : 'Ajoutée à un article'),
};

const EVIDENCE_GROUPS = [
  ['article', 'Articles créés'],
  ['edit', 'Articles existants modifiés'],
  ['reference', 'Références ajoutées dans des articles existants'],
  ['upload', 'Photos téléversées'],
  ['wikidata', 'Éléments Wikidata'],
  ['existing_photo', 'Photos existantes réutilisées'],
];

function evidenceLink(e) {
  if (e.type === 'upload' || e.type === 'existing_photo') {
    return h('a', { href: `https://commons.wikimedia.org/wiki/File:${encodeURIComponent(e.label.replace(/ /g, '_'))}`, target: '_blank', rel: 'noopener noreferrer', text: e.label });
  }
  if (e.type === 'wikidata' && /^Q\d+$/.test(e.label)) {
    return h('a', { href: `https://www.wikidata.org/wiki/${e.label}`, target: '_blank', rel: 'noopener noreferrer', text: e.label });
  }
  return h('span', { text: e.label });
}

/** Pièce d'un critère que le barème n'a pas retenu. */
function disabledText(e) {
  return CRITERIA.includes(e.status) && !enabledCriteria(state.scoring).includes(e.status) ? 'Critère non retenu par le barème' : '';
}

function coauthorText(e, username) {
  if (!e.coauthors) return '';
  const others = e.coauthors.filter((u) => u !== username);
  const list = others.length > 1 ? `${others.slice(0, -1).join(', ')} et ${others.at(-1)}` : others[0];
  if (e.share === 0) return `Créditée à ${e.coauthors[0]}, premier participant listé (avec ${list})`;
  if (e.share < 1) return `Avec ${list} : points partagés (1/${e.coauthors.length})`;
  return `Avec ${list}`;
}

let sheetOpener = null;

function openSheet(username, opener) {
  const p = state.result.participants.find((x) => x.username === username);
  if (!p) return;
  sheetOpener = opener;
  const dialog = $('[data-sheet]');
  const pointsRows = shownCriteria(state.scoring).map((c) => h('tr', {},
    h('th', { scope: 'row' }, h('span', { class: `swatch c-${c}`, 'aria-hidden': 'true' }), criterionLabel(c, state.scoring)),
    h('td', { text: fmt.format(p.counts[c]) }),
    h('td', { text: isGridCriterion(c, state.scoring) ? 'grille' : `× ${state.scoring.points[c]}` }),
    h('td', { class: 'num-strong' }, fmt.format(p.points[c]), p.capped.includes(c) ? h('span', { class: 'capped', text: ' plafonné' }) : null)));

  const MAX_ITEMS = 150;
  const active = new Set(enabledCriteria(state.scoring));
  const entryPoints = (e) => (active.has(e.status) && e.share > 0 ? (e.unit ?? state.scoring.points[e.status]) * e.share * (e.quantity ?? 1) : 0);
  const groups = EVIDENCE_GROUPS.map(([type, title]) => {
    // Le bonus « photo utilisée » est fusionné avec la ligne de la photo.
    const items = p.evidence.filter((e) => e.type === type && !e.bonus);
    if (!items.length) return null;
    const bonusFor = (e) => p.evidence.find((b) => b.bonus && b.label === e.label);
    return h('section', { class: 'evidence' },
      h('h3', { text: `${title} (${fmt.format(items.length)})` }),
      h('ul', {}, ...items.slice(0, MAX_ITEMS).map((e) => {
        const pts = entryPoints(e) + (e.type === 'upload' ? entryPoints(bonusFor(e) ?? {}) : 0);
        const counted = pts > 0;
        const swatch = counted ? `c-${e.type === 'upload' && e.usage > 0 && state.scoring.points.photo_uploaded === 0 ? 'photo_uploaded_used' : e.status}` : 'c-none';
        return h('li', { class: counted ? 'is-counted' : 'is-ignored' },
          h('span', { class: `swatch ${swatch}`, 'aria-hidden': 'true' }),
          h('span', { class: 'ev-label' }, evidenceLink(e)),
          h('span', { class: 'ev-status', text: [STATUS_TEXT[e.status]?.(e), e.translated && e.status !== 'article_translated' ? 'Dans la liste des traductions' : '', disabledText(e), coauthorText(e, p.username)].filter(Boolean).join('. ') }),
          h('span', { class: 'ev-points', text: counted ? `+${fmt.format(pts)}` : '0' }));
      })),
      items.length > MAX_ITEMS ? h('p', { class: 'is-muted', text: `… et ${fmt.format(items.length - MAX_ITEMS)} autres, détaillées dans l’export CSV de vos fichiers source.` }) : null);
  });

  const ctx = p.context;
  const context = Object.keys(ctx).length
    ? h('p', { class: 'sheet-context', text: [
        ctx.edits !== undefined ? plural(ctx.edits, 'modification', 'modifications') : null,
        ctx.bytes !== undefined ? `${fmt.format(ctx.bytes)} octets ajoutés` : null,
        ctx.references !== undefined ? plural(ctx.references, 'référence ajoutée', 'références ajoutées') : null,
      ].filter(Boolean).join(', ') + ' pendant la campagne (pour information, sans points).' })
    : null;

  mount($('[data-sheet-body]'), 
    h('header', { class: 'sheet-head' },
      h('div', {},
        h('p', { class: 'sheet-rank', text: p.excluded ? 'Hors concours' : `${p.rank}${p.rank === 1 ? 'er' : 'e'} du classement` }),
        h('h2', { id: 'sheet-title', class: 'sheet-name', text: p.username })),
      h('button', { type: 'button', class: 'icon-btn', 'aria-label': 'Fermer la fiche', onclick: () => dialog.close() }, '×')),
    h('p', { class: 'sheet-total' }, h('span', { text: fmt.format(p.total) }), ' points'),
    context,
    h('table', { class: 'points-table' },
      h('caption', { class: 'visually-hidden', text: 'Calcul des points par critère' }),
      h('thead', {}, h('tr', {}, h('th', { scope: 'col', text: 'Critère' }), h('th', { scope: 'col', text: 'Nombre' }), h('th', { scope: 'col', text: 'Barème' }), h('th', { scope: 'col', text: 'Points' }))),
      h('tbody', {}, ...pointsRows)),
    ...groups,
    h('div', { class: 'sheet-actions' },
      h('button', {
        type: 'button',
        class: 'btn btn-quiet',
        onclick: () => {
          toggleExcluded(p.username);
          dialog.close();
        },
        text: p.excluded ? 'Réintégrer au classement' : 'Classer hors concours',
      })),
  );
  dialog.showModal();
}

/* ------------------------------------------------- procès-verbal imprimé */

function renderPrint() {
  const date = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long' }).format(new Date());
  const { participants } = state.result;
  mount($('[data-print]'), 
    h('h1', { text: state.campaign || 'Classement du concours' }),
    h('p', { text: `Procès-verbal établi le ${date} avec WikiJury.` }),
    h('h2', { text: 'Barème appliqué' }),
    h('table', {}, h('tbody', {}, ...shownCriteria(state.scoring).map((c) => h('tr', {}, h('td', { text: criterionLabel(c, state.scoring) }), h('td', { text: isGridCriterion(c, state.scoring) ? 'selon la grille' : plural(state.scoring.points[c], 'point', 'points') }))))),
    h('p', { text: `Modèle : ${presetsSpec.presets.find((x) => x.id === state.preset)?.label ?? 'personnalisé'}. Pages créées à plusieurs : ${COAUTHOR_RULES[state.scoring.rules.coauthors].toLowerCase()}.${state.scoring.rules.excluded_wikis.length ? ` Wikis non retenus : ${state.scoring.rules.excluded_wikis.join(', ')}.` : ''}${Object.keys(state.scoring.rules.caps ?? {}).length ? ` Plafonds par participant : ${Object.entries(state.scoring.rules.caps).map(([c, v]) => `${CRITERION_SHORT[c]} ${v} pts`).join(', ')}.` : ''}` }),
    state.scoring.rules.article_mode === 'grid' ? h('p', { text: `Grille des articles créés : ${formatGrid(state.scoring.grids?.created).replace(/\n/g, ' ; ')}.` }) : null,
    state.scoring.grids?.edited?.length ? h('p', { text: `Grille des articles améliorés : ${formatGrid(state.scoring.grids.edited).replace(/\n/g, ' ; ')}.` }) : null,
    h('h2', { text: 'Classement' }),
    h('table', {},
      h('thead', {}, h('tr', {}, h('th', { text: 'Rang' }), h('th', { text: 'Contributeur' }), ...shownCriteria(state.scoring).map((c) => h('th', { text: CRITERION_SHORT[c] })), h('th', { text: 'Total' }))),
      h('tbody', {}, ...participants.map((p) => h('tr', {},
        h('td', { text: p.excluded ? 'H.C.' : String(p.rank) }),
        h('td', { text: p.username }),
        ...shownCriteria(state.scoring).map((c) => h('td', { text: String(p.counts[c]) })),
        h('td', { text: fmt.format(p.total) }))))),
    h('p', { class: 'print-note', text: 'Les colonnes de critères indiquent le nombre de contributions retenues. H.C. : hors concours.' }),
    h('div', { class: 'signatures' }, ...[1, 2, 3].map(() => h('div', {}, h('span', { text: 'Membre du jury : nom et signature' })))),
  );
}

/* --------------------------------------------------------------- liaisons */

function bind() {
  const input = $('[data-file-input]');
  input.addEventListener('change', () => {
    addFiles([...input.files]);
    input.value = '';
  });

  const zone = $('[data-dropzone]');
  for (const type of ['dragenter', 'dragover']) {
    zone.addEventListener(type, (e) => {
      e.preventDefault();
      zone.classList.add('is-over');
    });
  }
  for (const type of ['dragleave', 'drop']) zone.addEventListener(type, () => zone.classList.remove('is-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    addFiles([...e.dataTransfer.files]);
  });

  const campaign = $('[data-campaign]');
  campaign.value = state.campaign;
  campaign.addEventListener('input', () => {
    state.campaign = campaign.value;
    persist();
  });

  $('[data-action="reset-scoring"]').addEventListener('click', () => {
    applyPreset(state.preset);
  });

  $('[data-action="export"]').addEventListener('click', () => {
    const date = new Date().toISOString().slice(0, 10);
    download(`wikijury-${slugify(state.campaign)}-${date}.csv`, rankingToCsv(state.result.participants, state.scoring));
  });

  $('[data-action="print"]').addEventListener('click', () => {
    renderPrint();
    window.print();
  });

  const dialog = $('[data-sheet]');
  dialog.addEventListener('click', (e) => {
    if (e.target === dialog) dialog.close();
  });
  dialog.addEventListener('close', () => sheetOpener?.isConnected && sheetOpener.focus());
}

/* --------------------------------------------------- pages À propos et FAQ */

function renderAbout() {
  const a = content.about;
  mount($('[data-view="about"]'),
    h('article', { class: 'page-inner' },
      h('h1', { id: 'about-title', class: 'page-title', text: a.title }),
      h('p', { class: 'page-lead', text: a.lead }),
      ...a.sections.map((sec) => h('section', { class: 'page-section' },
        h('h2', { text: sec.heading }),
        ...(sec.paragraphs ?? []).map((t) => h('p', { text: t })),
        sec.items ? h('ul', {}, ...sec.items.map((t) => h('li', { text: t }))) : null)),
      h('p', { class: 'page-links' }, ...a.links.map((l) => h('a', { class: 'btn btn-quiet', href: l.url, target: '_blank', rel: 'noopener noreferrer', text: l.label }))),
      h('p', { class: 'page-meta', text: `Version ${__APP_VERSION__}` })));
}

function renderFaq() {
  const f = content.faq;
  mount($('[data-view="faq"]'),
    h('article', { class: 'page-inner' },
      h('h1', { id: 'faq-title', class: 'page-title', text: f.title }),
      ...f.groups.map((g) => h('section', { class: 'page-section' },
        h('h2', { text: g.heading }),
        ...g.questions.map((item) => h('details', { class: 'faq-item', id: `faq-${item.id}` },
          h('summary', { text: item.q }),
          ...item.a.map((t) => h('p', { text: t }))))))));
}

/* ------------------------------------------------------------- routage */

const ROUTES = { '': 'ranking', 'a-propos': 'about', faq: 'faq' };
const TITLES = { ranking: 'WikiJury : classement des concours Wikimedia', about: 'À propos · WikiJury', faq: 'FAQ · WikiJury' };

/** « #/faq#co-auteurs » → { view: 'faq', anchor: 'co-auteurs' } ; tout autre fragment → classement. */
function currentView() {
  const hash = location.hash;
  if (!hash.startsWith('#/')) return { view: 'ranking' };
  const [path, anchor] = hash.slice(2).split('#');
  return { view: ROUTES[path] ?? 'ranking', anchor };
}

function route() {
  const { view, anchor } = currentView();
  for (const el of document.querySelectorAll('[data-view]')) el.hidden = el.dataset.view !== view;
  for (const el of document.querySelectorAll('[data-ranking-only]')) el.hidden = view !== 'ranking';
  for (const link of document.querySelectorAll('[data-route]')) {
    if (link.dataset.route === view) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  document.title = TITLES[view];
  if (view === 'faq' && anchor) {
    const item = document.getElementById(`faq-${anchor}`);
    if (item) {
      item.open = true;
      item.scrollIntoView();
      item.querySelector('summary')?.focus();
      return;
    }
  }
  if (view !== 'ranking') {
    window.scrollTo(0, 0);
    document.querySelector(`[data-view="${view}"]`).focus({ preventScroll: true });
  }
}

/* --------------------------------------------------------------- thème */

function applyTheme(theme, save) {
  document.documentElement.dataset.theme = theme;
  const btn = $('[data-action="theme"]');
  const dark = theme === 'dark';
  btn.setAttribute('aria-pressed', String(dark));
  btn.title = dark ? 'Mode clair' : 'Mode sombre';
  if (save) {
    try {
      localStorage.setItem('wikijury:theme', theme);
    } catch {
      /* stockage indisponible : le choix vaut pour cette visite */
    }
  }
}

function bindTheme() {
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light', false);
  $('[data-action="theme"]').addEventListener('click', () => {
    applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark', true);
  });
  // Sans choix explicite, le thème suit celui du système.
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    let saved = null;
    try {
      saved = localStorage.getItem('wikijury:theme');
    } catch {
      /* ignoré */
    }
    if (!saved) applyTheme(e.matches ? 'dark' : 'light', false);
  });
}

function bindSkipLink() {
  $('.skip-link').addEventListener('click', (e) => {
    e.preventDefault();
    const visible = [...document.querySelectorAll('main')].find((m) => !m.closest('[hidden]') && !m.hidden);
    visible?.focus();
  });
}

renderAbout();
renderFaq();
bind();
bindTheme();
bindSkipLink();
window.addEventListener('hashchange', route);
route();
recompute();
