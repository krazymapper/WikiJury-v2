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
  'article_long',
  'article_short',
  'wikidata_item',
  'photo_uploaded_used',
  'photo_existing_used',
];

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
  switch (id) {
    case 'article_long':
      return `Article créé de ${formatInt(long)} caractères ou plus`;
    case 'article_short':
      return `Article créé de ${formatInt(short)} à ${formatInt(long - 1)} caractères`;
    case 'wikidata_item':
      return 'Élément Wikidata créé';
    case 'photo_uploaded_used':
      return 'Photo téléversée et utilisée';
    case 'photo_existing_used':
      return 'Photo Commons existante utilisée';
    default:
      return id;
  }
}

/** Libellés courts pour la légende et les colonnes étroites. */
export const CRITERION_SHORT = {
  article_long: 'Article long',
  article_short: 'Article court',
  wikidata_item: 'Wikidata',
  photo_uploaded_used: 'Photo téléversée',
  photo_existing_used: 'Photo réutilisée',
};

/** Arrondi au centième, identique en Python (pas d'arrondi bancaire). */
export const round2 = (x) => Math.floor(x * 100 + 0.5) / 100;

const emptyCounts = () => Object.fromEntries(CRITERIA.map((c) => [c, 0]));

function articleStatus(chars, thresholds) {
  if (chars >= thresholds.article_long_min_chars) return 'article_long';
  if (chars >= thresholds.article_short_min_chars) return 'article_short';
  return 'too_short';
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
        if (!isNew || !(isArticle || isItem || isFile) || (isFile && hasUploads)) {
          stats.ignored += 1;
          return;
        }
        if (!once(`${wiki}|${ns}|${title}`, source, line, `« ${title} » (${wiki})`)) return;

        if (isArticle) {
          const chars = parseCount(get(row, 'characters'));
          const status = excludedWikis.has(wiki) ? 'wiki_excluded' : articleStatus(chars, scoring.thresholds);
          credit(users, { type: 'article', status, label: title, wiki, chars, source });
        } else if (isItem) {
          credit(users, { type: 'wikidata', status: 'wikidata_item', label: normalizeItem(title), source });
        } else {
          credit(users, { type: 'upload', status: 'photo_usage_unknown', label: title, source });
        }
        return;
      }

      if (columnsUnusable(kind)) return;

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
        const status = isNew ? articleStatus(chars, scoring.thresholds) : 'not_new';
        p.evidence.push({ type: 'article', status, label: title, chars, source, share: 1 });
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
        const status = usage > 0 ? 'photo_uploaded_used' : 'photo_unused';
        p.evidence.push({ type: 'upload', status, label: file, usage, source, share: 1 });
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

  const list = [...participants.values()].map((p) => {
    const counts = emptyCounts();
    const raw = emptyCounts();
    for (const e of p.evidence) {
      if (!CRITERIA.includes(e.status) || e.share <= 0) continue;
      const quantity = e.quantity ?? 1;
      counts[e.status] += quantity;
      raw[e.status] += (Number(scoring.points[e.status]) || 0) * e.share * quantity;
    }
    const points = Object.fromEntries(CRITERIA.map((c) => [c, round2(raw[c])]));
    const total = round2(CRITERIA.reduce((sum, c) => sum + points[c], 0));
    return { ...p, counts, points, total, excluded: excludedSet.has(p.username), rank: null };
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
