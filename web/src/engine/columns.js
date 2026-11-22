import { normalizeHeader, stripAccents } from './normalize.js';

/**
 * Associe chaque champ d'un type de fichier à un en-tête réel.
 * @returns {Record<string, string|null>}
 */
export function mapColumns(headers, kindSpec) {
  const byNormalized = new Map();
  for (const h of headers) {
    const key = normalizeHeader(h);
    if (!byNormalized.has(key)) byNormalized.set(key, h);
  }
  const mapping = {};
  const used = new Set();
  for (const [field, spec] of Object.entries(kindSpec.fields)) {
    mapping[field] = null;
    for (const alias of spec.aliases) {
      const header = byNormalized.get(normalizeHeader(alias));
      if (header !== undefined && !used.has(header)) {
        mapping[field] = header;
        used.add(header);
        break;
      }
    }
  }
  return mapping;
}

/** Liste des champs obligatoires encore sans colonne (vide = mapping complet). */
export function missingFields(mapping, kindSpec) {
  const missing = Object.entries(kindSpec.fields)
    .filter(([field, spec]) => spec.required && !mapping[field])
    .map(([field]) => field);
  for (const group of kindSpec.required_any ?? []) {
    if (!group.some((field) => mapping[field])) missing.push(group.join('|'));
  }
  return missing;
}

/**
 * Devine le type d'un fichier depuis ses en-têtes et son nom.
 * Un indice dans le nom du fichier l'emporte s'il est compatible avec les colonnes.
 */
export function detectKind(headers, fileName, columnsSpec) {
  const candidates = [];
  for (const kind of columnsSpec.detection_order) {
    const spec = columnsSpec.kinds[kind];
    const mapping = mapColumns(headers, spec);
    if (missingFields(mapping, spec).length === 0) candidates.push({ kind, mapping });
  }
  if (candidates.length === 0) return { kind: null, mapping: null, confidence: 'none', candidates };

  const name = stripAccents(fileName ?? '').toLowerCase();
  const hinted = candidates.find(({ kind }) =>
    columnsSpec.kinds[kind].filename_hints.some((hint) => name.includes(hint)),
  );
  const chosen = hinted ?? candidates[0];
  const confidence = hinted || chosen.kind !== 'editors' ? 'high' : 'low';
  return { ...chosen, confidence, candidates: candidates.map((c) => c.kind) };
}
