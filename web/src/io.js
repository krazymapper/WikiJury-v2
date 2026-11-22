import Papa from 'papaparse';
import { COAUTHOR_RULES, CRITERIA, CRITERION_SHORT } from './engine/scoring.js';

export const MAX_FILE_BYTES = 25 * 1024 * 1024;

/** Lit un CSV (texte) en lignes-objets. */
export function parseCsvText(text) {
  const result = Papa.parse(text, {
    header: true,
    skipEmptyLines: 'greedy',
    transformHeader: (h) => h.replace(/^﻿/, '').trim(),
  });
  const headers = (result.meta.fields ?? []).filter(Boolean);
  return { headers, rows: result.data };
}

/** Lit un fichier déposé (CSV ou XLSX) en { headers, rows }. */
export async function parseFile(file) {
  if (file.size > MAX_FILE_BYTES) {
    throw new Error(`Fichier trop volumineux (${Math.round(file.size / 1e6)} Mo). La limite est de 25 Mo.`);
  }
  const ext = file.name.split('.').pop().toLowerCase();
  if (ext === 'xlsx') {
    const { readSheet } = await import('read-excel-file/browser');
    const table = await readSheet(file);
    const [head = [], ...body] = table;
    const headers = head.map((h) => String(h ?? '').trim());
    const rows = body
      .filter((r) => r.some((cell) => cell !== null && cell !== ''))
      .map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? ''])));
    return { headers: headers.filter(Boolean), rows };
  }
  if (['csv', 'tsv', 'txt'].includes(ext)) return parseCsvText(await file.text());
  if (ext === 'xls') throw new Error('Le format .xls (Excel 97-2003) n’est pas pris en charge. Enregistrez le fichier en .xlsx ou en CSV.');
  throw new Error('Format non reconnu. Importez un fichier CSV ou Excel (.xlsx).');
}

/** Neutralise les formules lors d'une ouverture dans un tableur (injection CSV). */
function cell(value) {
  let s = value === null || value === undefined ? '' : String(value);
  if (typeof value === 'number') s = s.replace('.', ','); // décimale à la française pour Excel
  else if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[";\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Export du classement, séparateur « ; » et BOM pour Excel en français. */
export function rankingToCsv(participants, scoring) {
  const header = [
    'Rang',
    'Contributeur',
    ...CRITERIA.flatMap((c) => [`${CRITERION_SHORT[c]} (nombre)`, `${CRITERION_SHORT[c]} (points)`]),
    'Total',
    'Statut',
  ];
  const lines = participants.map((p) => [
    p.rank ?? '',
    p.username,
    ...CRITERIA.flatMap((c) => [p.counts[c], p.points[c]]),
    p.total,
    p.excluded ? 'Hors concours' : 'Classé',
  ]);
  const scoringLine = [
    '# Barème',
    ...CRITERIA.map((c) => `${CRITERION_SHORT[c]} = ${scoring.points[c]} pt`),
    `Article long ≥ ${scoring.thresholds.article_long_min_chars} car.`,
    `Article court ≥ ${scoring.thresholds.article_short_min_chars} car.`,
    `Co-auteurs : ${COAUTHOR_RULES[scoring.rules.coauthors]}`,
    ...(scoring.rules.excluded_wikis.length ? [`Wikis non retenus : ${scoring.rules.excluded_wikis.join(', ')}`] : []),
  ];
  return '﻿' + [header, ...lines, [], scoringLine].map((r) => r.map(cell).join(';')).join('\r\n');
}

export function download(filename, content, type = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function slugify(text) {
  return (
    String(text)
      .normalize('NFD')
      .replace(/\p{M}/gu, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '') || 'classement'
  );
}
