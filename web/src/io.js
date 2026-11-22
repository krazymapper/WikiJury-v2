import Papa from 'papaparse';
import { ARTICLE_MODES, COAUTHOR_RULES, CRITERION_SHORT, criterionLabel, isGridCriterion, shownCriteria } from './engine/scoring.js';

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

function tableToRows(table) {
  const [head = [], ...body] = table;
  const headers = head.map((h) => String(h ?? '').trim());
  const rows = body
    .filter((r) => r.some((cell) => cell !== null && cell !== undefined && cell !== ''))
    .map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? ''])));
  return { headers: headers.filter(Boolean), rows };
}

/** Lit un fichier déposé (CSV, XLSX ou XLS) en { headers, rows }. */
export async function parseFile(file) {
  if (file.size > MAX_FILE_BYTES) {
    throw new Error(`Fichier trop volumineux (${Math.round(file.size / 1e6)} Mo). La limite est de 25 Mo.`);
  }
  const ext = file.name.split('.').pop().toLowerCase();
  if (ext === 'xlsx') {
    const { readSheet } = await import('read-excel-file/browser');
    return tableToRows(await readSheet(file));
  }
  if (ext === 'xls') {
    // Excel 97-2003 : bibliothèque chargée seulement quand un tel fichier est déposé.
    const XLSX = await import('@e965/xlsx');
    const workbook = XLSX.read(await file.arrayBuffer(), { type: 'array' });
    const sheet = workbook.Sheets[workbook.SheetNames[0]];
    return tableToRows(XLSX.utils.sheet_to_json(sheet, { header: 1, raw: true, defval: '' }));
  }
  if (['csv', 'tsv', 'txt'].includes(ext)) return parseCsvText(await file.text());
  throw new Error('Format non reconnu. Importez un fichier CSV ou Excel (.xlsx ou .xls).');
}

/** Neutralise les formules lors d'une ouverture dans un tableur (injection CSV). */
function cell(value) {
  let s = value === null || value === undefined ? '' : String(value);
  if (typeof value === 'number') s = s.replace('.', ','); // décimale à la française pour Excel
  else if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[";\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

const gridText = (grid) => [...(grid ?? [])].sort((a, b) => b[0] - a[0]).map(([min, pts]) => `${min} car. = ${String(pts).replace('.', ',')} pt`).join(' | ');

/** Export du classement, séparateur « ; » et BOM pour Excel en français. */
export function rankingToCsv(participants, scoring) {
  const CRITERIA = shownCriteria(scoring);
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
    ...CRITERIA.map((c) => `${criterionLabel(c, scoring)} = ${isGridCriterion(c, scoring) ? 'grille' : `${scoring.points[c]} pt`}`),
    `Articles : ${ARTICLE_MODES[scoring.rules.article_mode ?? 'tiers']}`,
    ...(scoring.rules.article_mode === 'grid' ? [`Grille créations : ${gridText(scoring.grids?.created)}`] : []),
    ...(scoring.grids?.edited?.length ? [`Grille améliorations : ${gridText(scoring.grids.edited)}`] : []),
    `Co-auteurs : ${COAUTHOR_RULES[scoring.rules.coauthors]}`,
    ...(scoring.rules.excluded_wikis.length ? [`Wikis non retenus : ${scoring.rules.excluded_wikis.join(', ')}`] : []),
    ...Object.entries(scoring.rules.caps ?? {}).map(([c, v]) => `Plafond ${CRITERION_SHORT[c]} = ${v} pts`),
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
