import {
  compareNames,
  normalizeItem,
  normalizeTitle,
  normalizeUsername,
  parseBool,
  parseCount,
} from './normalize.js';

/** Critères notés, dans l'ordre d'affichage. */
export const CRITERIA = [
  'article_long',
  'article_short',
  'wikidata_item',
  'photo_uploaded_used',
  'photo_existing_used',
];

export function mergeScoring(base, override = {}) {
  return {
    version: base.version,
    thresholds: { ...base.thresholds, ...(override.thresholds ?? {}) },
    points: { ...base.points, ...(override.points ?? {}) },
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

function emptyCounts() {
  return Object.fromEntries(CRITERIA.map((c) => [c, 0]));
}

/**
 * Calcule le classement.
 * @param {Array<{kind:string, mapping:Record<string,string|null>, rows:Array<Record<string,unknown>>, source:string}>} datasets
 * @param {{thresholds:object, points:object}} scoring
 * @param {{excluded?: string[]}} options
 */
export function computeRanking(datasets, scoring, { excluded = [] } = {}) {
  const participants = new Map();
  const warnings = [];
  const seen = { articles: new Set(), uploads: new Set(), wikidata: new Set(), existing_photos: new Set() };
  const excludedSet = new Set(excluded.map(normalizeUsername).filter(Boolean));

  const participant = (rawName) => {
    const username = normalizeUsername(rawName);
    if (!username) return null;
    if (!participants.has(username)) {
      participants.set(username, { username, counts: emptyCounts(), evidence: [], context: {} });
    }
    return participants.get(username);
  };

  const warn = (code, source, row, message) => warnings.push({ code, source, row, message });

  for (const { kind, mapping, rows, source } of datasets) {
    const get = (row, field) => (mapping[field] ? row[mapping[field]] : undefined);

    rows.forEach((row, index) => {
      const line = index + 2; // ligne 1 = en-têtes
      const p = participant(get(row, 'username'));
      if (!p) {
        warn('missing_value', source, line, 'Nom d’utilisateur manquant : ligne ignorée.');
        return;
      }

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
        const key = title;
        if (seen.articles.has(key)) {
          warn('duplicate', source, line, `« ${title} » apparaît plusieurs fois : seule la première ligne compte.`);
          return;
        }
        seen.articles.add(key);
        let isNew = true;
        if (mapping.new) {
          const parsed = parseBool(get(row, 'new'));
          if (parsed === null) warn('invalid_value', source, line, `Valeur « nouvel article » illisible pour « ${title} » : considéré comme non créé.`);
          isNew = parsed === true;
        }
        const chars = parseCount(get(row, 'characters'));
        let status = 'not_new';
        if (isNew) {
          if (chars >= scoring.thresholds.article_long_min_chars) status = 'article_long';
          else if (chars >= scoring.thresholds.article_short_min_chars) status = 'article_short';
          else status = 'too_short';
        }
        if (CRITERIA.includes(status)) p.counts[status] += 1;
        p.evidence.push({ type: 'article', status, label: title, chars, source });
        return;
      }

      if (kind === 'uploads') {
        const file = normalizeTitle(get(row, 'filename'));
        if (!file) {
          warn('missing_value', source, line, 'Nom de fichier manquant : ligne ignorée.');
          return;
        }
        if (seen.uploads.has(file)) {
          warn('duplicate', source, line, `« ${file} » apparaît plusieurs fois : seule la première ligne compte.`);
          return;
        }
        seen.uploads.add(file);
        const usage = parseCount(get(row, 'usage_count'));
        const status = usage > 0 ? 'photo_uploaded_used' : 'photo_unused';
        if (status === 'photo_uploaded_used') p.counts.photo_uploaded_used += 1;
        p.evidence.push({ type: 'upload', status, label: file, usage, source });
        return;
      }

      if (kind === 'wikidata') {
        const item = normalizeItem(get(row, 'item'));
        if (item) {
          if (seen.wikidata.has(item)) {
            warn('duplicate', source, line, `${item} apparaît plusieurs fois : seule la première ligne compte.`);
            return;
          }
          seen.wikidata.add(item);
          p.counts.wikidata_item += 1;
          p.evidence.push({ type: 'wikidata', status: 'wikidata_item', label: item, source });
          return;
        }
        const quantity = mapping.quantity ? Math.max(0, parseCount(get(row, 'quantity'))) : 0;
        if (!mapping.quantity) {
          warn('missing_value', source, line, 'Identifiant Wikidata manquant : ligne ignorée.');
          return;
        }
        p.counts.wikidata_item += quantity;
        p.evidence.push({ type: 'wikidata', status: 'wikidata_item', label: `${quantity} élément(s) déclaré(s)`, quantity, source });
        return;
      }

      if (kind === 'existing_photos') {
        const file = normalizeTitle(get(row, 'filename'));
        if (!file) {
          warn('missing_value', source, line, 'Nom de fichier manquant : ligne ignorée.');
          return;
        }
        const article = normalizeTitle(get(row, 'article'));
        const key = `${file}\u0000${article}`;
        if (seen.existing_photos.has(key)) {
          warn('duplicate', source, line, `« ${file} »${article ? ` dans « ${article} »` : ''} apparaît plusieurs fois : seule la première ligne compte.`);
          return;
        }
        seen.existing_photos.add(key);
        p.counts.photo_existing_used += 1;
        p.evidence.push({ type: 'existing_photo', status: 'photo_existing_used', label: file, article, source });
      }
    });
  }

  const list = [...participants.values()].map((p) => {
    const points = Object.fromEntries(CRITERIA.map((c) => [c, p.counts[c] * (Number(scoring.points[c]) || 0)]));
    const total = CRITERIA.reduce((sum, c) => sum + points[c], 0);
    return { ...p, points, total, excluded: excludedSet.has(p.username), rank: null };
  });

  const byScore = (a, b) => b.total - a.total || compareNames(a.username, b.username);
  const ranked = list.filter((p) => !p.excluded).sort(byScore);
  // Classement « compétition » : les ex-aequo partagent le rang, le suivant saute (1, 2, 2, 4).
  ranked.forEach((p, i) => {
    p.rank = i > 0 && ranked[i - 1].total === p.total ? ranked[i - 1].rank : i + 1;
  });
  const out = list.filter((p) => p.excluded).sort((a, b) => compareNames(a.username, b.username));

  return { participants: [...ranked, ...out], warnings };
}
