import {
  compareNames,
  normalizeItem,
  normalizeTitle,
  normalizeUsername,
  parseBool,
  parseCount,
} from './normalize.js';

// Toute règle modifiée ici doit l'être aussi dans streamlit_app/wikijury/scoring.py.

/** Critères notés, dans l'ordre d'affichage. */
export const CRITERIA = [
  'article_created',
  'article_translated',
  'article_long',
  'article_short',
  'article_edited',
  'reference_added',
  'wikidata_item',
  'photo_uploaded',
  'photo_uploaded_used',
  'photo_existing_used',
];

export const ARTICLE_MODES = {
  flat: 'Forfait par article (avec minimum)',
  tiers: 'Selon la taille (deux paliers)',
};

/** Critères actifs : tous si le barème ne précise rien. */
export function enabledCriteria(scoring) {
  const list = scoring.rules?.enabled;
  return Array.isArray(list) ? CRITERIA.filter((c) => list.includes(c)) : [...CRITERIA];
}

/** Critères actifs et pertinents pour le mode de notation des articles (affichage, export). */
export function shownCriteria(scoring) {
  const flat = (scoring.rules?.article_mode ?? 'tiers') === 'flat';
  const hidden = flat ? ['article_long', 'article_short'] : ['article_created', 'article_translated'];
  return enabledCriteria(scoring).filter((c) => !hidden.includes(c));
}

export const COAUTHOR_RULES = {
  split: 'Partager les points entre co-auteurs',
  all: 'Points entiers pour chaque co-auteur',
  first: 'Points au premier participant listé',
};

export function mergeScoring(base, override = {}) {
  return {
    version: base.version,
    thresholds: { ...base.thresholds, ...(override.thresholds ?? {}) },
    points: { ...base.points, ...(override.points ?? {}) },
    rules: { ...base.rules, ...(override.rules ?? {}) },
  };
}

const formatInt = (n) => new Intl.NumberFormat('fr-FR').format(n);

export function criterionLabel(id, scoring) {
  const { article_long_min_chars: long, article_short_min_chars: short } = scoring.thresholds;
  const created = scoring.thresholds.article_created_min_chars ?? 0;
  const improved = scoring.thresholds.article_improved_min_chars ?? 0;
  switch (id) {
    case 'article_created':
      return created > 0 ? `Article créé (${formatInt(created)} caractères minimum)` : 'Article créé';
    case 'article_translated':
      return created > 0 ? `Article traduit (${formatInt(created)} caractères minimum)` : 'Article traduit';
    case 'article_long':
      return `Article créé de ${formatInt(long)} caractères ou plus`;
    case 'article_short':
      return short <= 1
        ? `Article créé de moins de ${formatInt(long)} caractères`
        : `Article créé de ${formatInt(short)} à ${formatInt(long - 1)} caractères`;
    case 'article_edited':
      return improved > 0 ? `Article amélioré (${formatInt(improved)} caractères ajoutés minimum)` : 'Article existant modifié';
    case 'reference_added':
      return 'Référence ajoutée dans un article existant';
    case 'wikidata_item':
      return 'Élément Wikidata créé';
    case 'photo_uploaded':
      return 'Photo téléversée (utilisée ou non)';
    case 'photo_uploaded_used':
      return 'Bonus : photo téléversée et utilisée';
    case 'photo_existing_used':
      return 'Photo Commons existante utilisée';
    default:
      return id;
  }
}

/** Libellés courts pour la légende et les colonnes étroites. */
export const CRITERION_SHORT = {
  article_created: 'Article créé',
  article_translated: 'Article traduit',
  article_long: 'Article long',
  article_short: 'Article court',
  article_edited: 'Article amélioré',
  reference_added: 'Référence',
  wikidata_item: 'Wikidata',
  photo_uploaded: 'Photo téléversée',
  photo_uploaded_used: 'Photo utilisée',
  photo_existing_used: 'Photo réutilisée',
};

/** Arrondi au centième, identique en Python (pas d'arrondi bancaire). */
export const round2 = (x) => Math.floor(x * 100 + 0.5) / 100;

const emptyCounts = () => Object.fromEntries(CRITERIA.map((c) => [c, 0]));

/** Statut d'un nouvel article selon le mode de notation du barème. */
function articleStatus(chars, scoring, translated = false) {
  const t = scoring.thresholds;
  if ((scoring.rules.article_mode ?? 'tiers') === 'flat') {
    const min = t.article_created_min_chars ?? 0;
    if (min > 0 && chars < min) return 'too_short';
    return translated && enabledCriteria(scoring).includes('article_translated') ? 'article_translated' : 'article_created';
  }
  if (chars >= t.article_long_min_chars) return 'article_long';
  if (chars >= t.article_short_min_chars) return 'article_short';
  return 'too_short';
}

/** Un article existant est « amélioré » s'il atteint le minimum de caractères ajoutés. */
function editStatus(chars, scoring) {
  const min = scoring.thresholds.article_improved_min_chars ?? 0;
  return min > 0 && chars < min ? 'edit_too_small' : 'article_edited';
}

/**
 * Calcule le classement.
 * Chaque pièce justificative (evidence) porte son statut et la part de points
 * attribuée (share) : les totaux sont recalculés à partir d'elles.
 */
export function computeRanking(datasets, scoring, { excluded = [] } = {}) {
  const participants = new Map();
  const warnings = [];
  const stats = { deleted: 0, ignored: 0 };
  const seen = new Set();
  const excludedSet = new Set(excluded.map(normalizeUsername).filter(Boolean));
  const excludedWikis = new Set((scoring.rules.excluded_wikis ?? []).map((w) => String(w).toLowerCase()));
  const coauthorRule = scoring.rules.coauthors ?? 'split';
  const hasUploads = datasets.some((d) => d.kind === 'uploads');

  // Liste des traductions : elle ne fait que requalifier des créations de la campagne.
  const translations = new Map();
  for (const { kind, mapping, rows, source } of datasets) {
    if (kind !== 'translations') continue;
    rows.forEach((row, index) => {
      const title = normalizeTitle(mapping.title ? row[mapping.title] : '');
      if (!title) return;
      const wiki = mapping.wiki ? String(row[mapping.wiki] ?? '').trim().toLowerCase() : '';
      translations.set(`${wiki}|${title}`, { title, wiki, source, line: index + 2, matched: false });
    });
  }
  const isTranslated = (title, wiki = '') => {
    const hit =
      translations.get(`${wiki}|${title}`) ??
      translations.get(`|${title}`) ??
      (wiki ? undefined : [...translations.values()].find((t) => t.title === title));
    if (hit) hit.matched = true;
    return Boolean(hit);
  };

  const participant = (username) => {
    if (!participants.has(username)) {
      participants.set(username, { username, counts: emptyCounts(), evidence: [], context: {} });
    }
    return participants.get(username);
  };

  const warn = (code, source, row, message) => warnings.push({ code, source, row, message });

  /** Attribue une pièce à un ou plusieurs participants selon la règle des co-auteurs. */
  const credit = (users, entry) => {
    const coauthors = users.length > 1 ? users : undefined;
    users.forEach((username, i) => {
      let share = 1;
      if (users.length > 1) {
        if (coauthorRule === 'split') share = 1 / users.length;
        else if (coauthorRule === 'first') share = i === 0 ? 1 : 0;
      }
      participant(username).evidence.push({ ...entry, share, coauthors });
    });
  };

  const once = (key, source, line, label) => {
    if (seen.has(key)) {
      warn('duplicate', source, line, `${label} apparaît plusieurs fois : seule la première ligne compte.`);
      return false;
    }
    seen.add(key);
    return true;
  };

  for (const { kind, mapping, rows, source } of datasets) {
    const get = (row, field) => (mapping[field] ? row[mapping[field]] : undefined);

    rows.forEach((row, index) => {
      const line = index + 2; // ligne 1 = en-têtes

      if (kind === 'dashboard_articles') {
        const users = [...new Set(String(get(row, 'usernames') ?? '').split(',').map(normalizeUsername).filter(Boolean))];
        if (users.length === 0) {
          warn('missing_value', source, line, 'Aucun participant indiqué : ligne ignorée.');
          return;
        }
        if (mapping.deleted && parseBool(get(row, 'deleted')) === true) {
          stats.deleted += 1;
          return;
        }
        const wiki = String(get(row, 'wiki') ?? '').trim().toLowerCase();
        const ns = parseCount(get(row, 'namespace'));
        const title = normalizeTitle(get(row, 'title'));
        if (!title) {
          warn('missing_value', source, line, 'Titre manquant : ligne ignorée.');
          return;
        }
        const isNew = parseBool(get(row, 'new')) === true;
        const isArticle = wiki.endsWith('.wikipedia.org') && ns === 0;
        const isItem = wiki === 'www.wikidata.org' && ns === 0 && /^Q\d+$/.test(normalizeItem(title));
        const isFile = wiki === 'commons.wikimedia.org' && ns === 6;
        // Seules les créations pendant la campagne comptent ; les fichiers
        // sont notés à partir de l'export « uploads » quand il est fourni.
        if (isArticle && !isNew) {
          // Article existant : chaque participant l'a modifié (1 pièce chacun) ;
          // les références ajoutées, cumulées sur la page, suivent la règle des co-auteurs.
          if (!once(`${wiki}|${ns}|${title}`, source, line, `« ${title} » (${wiki})`)) return;
          if (excludedWikis.has(wiki)) {
            for (const u of users) participant(u).evidence.push({ type: 'edit', status: 'wiki_excluded', label: title, wiki, source, share: 1 });
            return;
          }
          const chars = parseCount(get(row, 'characters'));
          const status = editStatus(chars, scoring);
          for (const u of users) {
            participant(u).evidence.push({ type: 'edit', status, label: title, wiki, chars, source, share: 1, coauthors: users.length > 1 ? users : undefined });
          }
          const refs = mapping.references ? Math.max(0, parseCount(get(row, 'references'))) : 0;
          if (refs > 0) credit(users, { type: 'reference', status: 'reference_added', label: title, wiki, quantity: refs, source });
          return;
        }
        if (!isNew || !(isArticle || isItem || isFile) || (isFile && hasUploads)) {
          stats.ignored += 1;
          return;
        }
        if (!once(`${wiki}|${ns}|${title}`, source, line, `« ${title} » (${wiki})`)) return;

        if (isArticle) {
          const chars = parseCount(get(row, 'characters'));
          const translated = isTranslated(title, wiki);
          const status = excludedWikis.has(wiki) ? 'wiki_excluded' : articleStatus(chars, scoring, translated);
          credit(users, { type: 'article', status, label: title, wiki, chars, translated, source });
        } else if (isItem) {
          credit(users, { type: 'wikidata', status: 'wikidata_item', label: normalizeItem(title), source });
        } else {
          credit(users, { type: 'upload', status: 'photo_usage_unknown', label: title, source });
        }
        return;
      }

      if (columnsUnusable(kind) || kind === 'translations') return;

      const username = normalizeUsername(get(row, 'username'));
      if (!username) {
        warn('missing_value', source, line, 'Nom d’utilisateur manquant : ligne ignorée.');
        return;
      }
      const p = participant(username);

      if (kind === 'editors') {
        for (const field of ['edits', 'bytes', 'references']) {
          if (mapping[field]) p.context[field] = (p.context[field] ?? 0) + parseCount(get(row, field));
        }
        return;
      }

      if (kind === 'articles') {
        const title = normalizeTitle(get(row, 'title'));
        if (!title) {
          warn('missing_value', source, line, 'Titre d’article manquant : ligne ignorée.');
          return;
        }
        if (!once(`article|${title}`, source, line, `« ${title} »`)) return;
        let isNew = true;
        if (mapping.new) {
          const parsed = parseBool(get(row, 'new'));
          if (parsed === null) warn('invalid_value', source, line, `Valeur « nouvel article » illisible pour « ${title} » : considéré comme non créé.`);
          isNew = parsed === true;
        }
        const chars = parseCount(get(row, 'characters'));
        const translated = (mapping.translated && parseBool(get(row, 'translated')) === true) || isTranslated(title);
        if (isNew) p.evidence.push({ type: 'article', status: articleStatus(chars, scoring, translated), label: title, chars, translated, source, share: 1 });
        else p.evidence.push({ type: 'edit', status: editStatus(chars, scoring), label: title, chars, source, share: 1 });
        return;
      }

      if (kind === 'uploads') {
        const file = normalizeTitle(get(row, 'filename'));
        if (!file) {
          warn('missing_value', source, line, 'Nom de fichier manquant : ligne ignorée.');
          return;
        }
        if (mapping.deleted && parseBool(get(row, 'deleted')) === true) {
          stats.deleted += 1;
          return;
        }
        if (!once(`upload|${file}`, source, line, `« ${file} »`)) return;
        const usage = parseCount(get(row, 'usage_count'));
        p.evidence.push({ type: 'upload', status: 'photo_uploaded', label: file, usage, source, share: 1 });
        if (usage > 0) p.evidence.push({ type: 'upload', status: 'photo_uploaded_used', label: file, usage, source, share: 1, bonus: true });
        return;
      }

      if (kind === 'wikidata') {
        const item = normalizeItem(get(row, 'item'));
        if (item) {
          if (!once(`item|${item}`, source, line, item)) return;
          p.evidence.push({ type: 'wikidata', status: 'wikidata_item', label: item, source, share: 1 });
          return;
        }
        if (!mapping.quantity) {
          warn('missing_value', source, line, 'Identifiant Wikidata manquant : ligne ignorée.');
          return;
        }
        const quantity = Math.max(0, parseCount(get(row, 'quantity')));
        p.evidence.push({ type: 'wikidata', status: 'wikidata_item', label: `${quantity} élément(s) déclaré(s)`, quantity, source, share: 1 });
        return;
      }

      if (kind === 'existing_photos') {
        const file = normalizeTitle(get(row, 'filename'));
        if (!file) {
          warn('missing_value', source, line, 'Nom de fichier manquant : ligne ignorée.');
          return;
        }
        const article = normalizeTitle(get(row, 'article'));
        if (!once(`existing|${file}|${article}`, source, line, `« ${file} »${article ? ` dans « ${article} »` : ''}`)) return;
        p.evidence.push({ type: 'existing_photo', status: 'photo_existing_used', label: file, article, source, share: 1 });
      }
    });
  }

  for (const t of translations.values()) {
    if (!t.matched) {
      warn('not_in_campaign', t.source, t.line, `« ${t.title} » figure dans la liste des traductions mais pas parmi les créations de la campagne : ignoré.`);
    }
  }

  const active = new Set(enabledCriteria(scoring));
  const list = [...participants.values()].map((p) => {
    const counts = emptyCounts();
    const raw = emptyCounts();
    for (const e of p.evidence) {
      if (!CRITERIA.includes(e.status) || e.share <= 0) continue;
      const quantity = e.quantity ?? 1;
      counts[e.status] += quantity;
      if (active.has(e.status)) raw[e.status] += (Number(scoring.points[e.status]) || 0) * e.share * quantity;
    }
    const caps = scoring.rules.caps ?? {};
    const capped = [];
    const points = Object.fromEntries(CRITERIA.map((c) => {
      const value = round2(raw[c]);
      const cap = Number(caps[c]);
      if (cap > 0 && value > cap) {
        capped.push(c);
        return [c, cap];
      }
      return [c, value];
    }));
    const total = round2(CRITERIA.reduce((sum, c) => sum + points[c], 0));
    return { ...p, counts, points, capped, total, excluded: excludedSet.has(p.username), rank: null };
  });

  const byScore = (a, b) => b.total - a.total || compareNames(a.username, b.username);
  const ranked = list.filter((p) => !p.excluded).sort(byScore);
  // Classement « compétition » : les ex-aequo partagent le rang, le suivant saute (1, 2, 2, 4).
  ranked.forEach((p, i) => {
    p.rank = i > 0 && ranked[i - 1].total === p.total ? ranked[i - 1].rank : i + 1;
  });
  const out = list.filter((p) => p.excluded).sort((a, b) => compareNames(a.username, b.username));

  return { participants: [...ranked, ...out], warnings, stats };
}

function columnsUnusable(kind) {
  return kind === 'dashboard_summary';
}

/** Wikipédias présentes dans les données, pour le filtre du jury. */
export function wikisInData(datasets) {
  const wikis = new Set();
  for (const { kind, mapping, rows } of datasets) {
    if (kind !== 'dashboard_articles' || !mapping.wiki) continue;
    for (const row of rows) {
      const wiki = String(row[mapping.wiki] ?? '').trim().toLowerCase();
      if (wiki.endsWith('.wikipedia.org')) wikis.add(wiki);
    }
  }
  return [...wikis].sort();
}
