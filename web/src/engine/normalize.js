// Normalisation des valeurs importées.
// Toute règle modifiée ici doit l'être aussi dans streamlit_app/wikijury/normalize.py :
// les tests de parité (shared/fixtures/expected.json) le vérifient.

const MARKS = /\p{M}/gu;
const SPACES = /[\s  ]+/g;

export function stripAccents(value) {
  return String(value).normalize('NFD').replace(MARKS, '');
}

/** En-tête de colonne comparable : minuscules, sans accents, '_' et '-' → espace. */
export function normalizeHeader(header) {
  return stripAccents(header ?? '')
    .toLowerCase()
    .replace(/[_\-]+/g, ' ')
    .replace(SPACES, ' ')
    .trim();
}

function upperFirst(value) {
  if (!value) return value;
  const first = String.fromCodePoint(value.codePointAt(0));
  return first.toUpperCase() + value.slice(first.length);
}

/**
 * Nom d'utilisateur MediaWiki canonique : '_' ↔ espace, espaces fusionnés,
 * première lettre en majuscule (MediaWiki est sensible à la casse au-delà).
 */
export function normalizeUsername(value) {
  if (value === null || value === undefined) return '';
  const cleaned = String(value).replace(/_/g, ' ').replace(SPACES, ' ').trim();
  return upperFirst(cleaned);
}

/** Titre de page ou nom de fichier canonique, sans préfixe d'espace de noms. */
export function normalizeTitle(value) {
  if (value === null || value === undefined) return '';
  const cleaned = String(value)
    .replace(/_/g, ' ')
    .replace(SPACES, ' ')
    .trim()
    .replace(/^(file|fichier|image)\s*:\s*/i, '');
  return upperFirst(cleaned);
}

export function normalizeItem(value) {
  if (value === null || value === undefined) return '';
  return String(value).replace(SPACES, '').toUpperCase();
}

/** Clé de tri insensible à la casse et aux accents. */
export function sortKey(value) {
  return stripAccents(value).toLowerCase();
}

export function compareNames(a, b) {
  const ka = sortKey(a);
  const kb = sortKey(b);
  if (ka !== kb) return ka < kb ? -1 : 1;
  if (a === b) return 0;
  return a < b ? -1 : 1;
}

/**
 * Entier depuis une cellule : accepte « 4 500 », « 4,500 », « 4.500 », « 4500.0 ».
 * Toute valeur illisible vaut 0.
 */
export function parseCount(value) {
  if (value === null || value === undefined) return 0;
  if (typeof value === 'number') return Number.isFinite(value) ? Math.trunc(value) : 0;
  const s = String(value).replace(SPACES, '');
  if (s === '') return 0;
  if (/^-?\d{1,3}([.,]\d{3})+$/.test(s)) return parseInt(s.replace(/[.,]/g, ''), 10);
  const n = Number(s.replace(',', '.'));
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

const TRUE_VALUES = new Set(['true', '1', 'yes', 'y', 'oui', 'o', 'vrai', 'x']);
const FALSE_VALUES = new Set(['false', '0', 'no', 'n', 'non', 'faux', '']);

/** true / false, ou null si la valeur n'est pas reconnue. */
export function parseBool(value) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value !== 0;
  if (value === null || value === undefined) return false;
  const s = stripAccents(String(value)).trim().toLowerCase();
  if (TRUE_VALUES.has(s)) return true;
  if (FALSE_VALUES.has(s)) return false;
  return null;
}
