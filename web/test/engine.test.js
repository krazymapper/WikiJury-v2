import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import columnsSpec from '../../shared/columns.json';
import defaultScoring from '../../shared/scoring.default.json';
import expected from '../../shared/fixtures/expected.json';
import { detectKind, mapColumns, missingFields } from '../src/engine/columns.js';
import { normalizeUsername, normalizeTitle, parseBool, parseCount } from '../src/engine/normalize.js';
import { computeRanking, mergeScoring } from '../src/engine/scoring.js';
import { parseCsvText, rankingToCsv } from '../src/io.js';

const fixture = (path) => readFileSync(fileURLToPath(new URL(`../../shared/fixtures/${path}`, import.meta.url)), 'utf8');

function loadDatasets(suite) {
  return Object.keys(suite.files).map((name) => {
    const { headers, rows } = parseCsvText(fixture(`${suite.dir}/${name}`));
    const { kind, mapping } = detectKind(headers, name, columnsSpec);
    return { kind, mapping, rows, source: name };
  });
}

describe('détection des fichiers', () => {
  for (const suite of expected.suites) {
    for (const [name, kind] of Object.entries(suite.files)) {
      it(`${suite.dir}/${name} est reconnu comme « ${kind} »`, () => {
        const { headers } = parseCsvText(fixture(`${suite.dir}/${name}`));
        expect(detectKind(headers, name, columnsSpec).kind).toBe(kind);
      });
    }
  }

  it('reconnaît les exports du Dashboard sans indice dans le nom du fichier', () => {
    for (const [name, kind] of Object.entries(expected.suites[1].files)) {
      const { headers } = parseCsvText(fixture(`dashboard/${name}`));
      expect(detectKind(headers, 'export.csv', columnsSpec).kind).toBe(kind);
    }
  });

  it('reconnaît le type même sans indice dans le nom du fichier', () => {
    const { headers } = parseCsvText(fixture('generic/uploads.csv'));
    expect(detectKind(headers, 'export.csv', columnsSpec).kind).toBe('uploads');
  });

  it('reconnaît des en-têtes en français avec accents', () => {
    const spec = columnsSpec.kinds.articles;
    const mapping = mapColumns(['Utilisateur', 'Titre', 'Caractères ajoutés', 'Nouvel article'], spec);
    expect(missingFields(mapping, spec)).toEqual([]);
    expect(mapping.characters).toBe('Caractères ajoutés');
  });
});

describe('normalisation', () => {
  it('rend équivalents les noms MediaWiki', () => {
    expect(normalizeUsername(' koffi_Mensah ')).toBe('Koffi Mensah');
    expect(normalizeUsername('Aïcha__Dossou')).toBe('Aïcha Dossou');
  });
  it('retire le préfixe de fichier', () => {
    expect(normalizeTitle('Fichier:Abomey_palais.jpg')).toBe('Abomey palais.jpg');
    expect(normalizeTitle('File: pendjari lion.jpg')).toBe('Pendjari lion.jpg');
  });
  it('lit les nombres saisis à la française', () => {
    expect(parseCount('4 500')).toBe(4500);
    expect(parseCount('4 500')).toBe(4500);
    expect(parseCount('4.500')).toBe(4500);
    expect(parseCount('1500.0')).toBe(1500);
    expect(parseCount('n/a')).toBe(0);
  });
  it('lit les booléens courants', () => {
    expect(parseBool('Oui')).toBe(true);
    expect(parseBool('FAUX')).toBe(false);
    expect(parseBool('peut-être')).toBe(null);
  });
});

for (const suite of expected.suites) {
  describe(`classement, ${suite.name} (parité avec shared/fixtures/expected.json)`, () => {
    const datasets = loadDatasets(suite);

    for (const scenario of suite.scenarios) {
      it(scenario.name, () => {
        const scoring = mergeScoring(defaultScoring, scenario.scoring);
        const { participants } = computeRanking(datasets, scoring, { excluded: scenario.excluded });
        const got = participants.map((p) => ({
          username: p.username,
          rank: p.rank,
          total: p.total,
          ...(scenario.ranking[0].counts ? { counts: p.counts } : {}),
        }));
        expect(got).toEqual(scenario.ranking);
      });
    }

    it('signale les doublons et les lignes incomplètes, compte les pages écartées', () => {
      const { warnings, stats } = computeRanking(datasets, mergeScoring(defaultScoring));
      const byCode = warnings.reduce((acc, w) => ({ ...acc, [w.code]: (acc[w.code] ?? 0) + 1 }), {});
      expect(byCode).toEqual(suite.warnings);
      expect(stats).toEqual(suite.stats);
    });
  });
}

describe('pièces justificatives', () => {
  it('garde la trace d’un article trop court', () => {
    const { participants } = computeRanking(loadDatasets(expected.suites[0]), mergeScoring(defaultScoring));
    const aicha = participants.find((p) => p.username === 'Aïcha Dossou');
    expect(aicha.evidence.find((e) => e.label === 'Marché Dantokpa')).toMatchObject({ status: 'too_short', chars: 1200 });
  });

  it('indique les co-auteurs et la part de points', () => {
    const { participants } = computeRanking(loadDatasets(expected.suites[1]), mergeScoring(defaultScoring));
    const abla = participants.find((p) => p.username === 'Abla Exemple');
    const abomey = abla.evidence.find((e) => e.label === 'Abomey');
    expect(abomey).toMatchObject({ status: 'article_long', share: 0.5, coauthors: ['Bio Exemple', 'Abla Exemple'] });
  });
});

describe('export CSV', () => {
  it('neutralise les formules et utilise le point-virgule', () => {
    const scoring = mergeScoring(defaultScoring);
    const csv = rankingToCsv([
      { rank: 1, username: '=HYPERLINK("x")', counts: { article_long: 1, article_short: 0, wikidata_item: 0, photo_uploaded_used: 0, photo_existing_used: 0 }, points: { article_long: 5, article_short: 0, wikidata_item: 0, photo_uploaded_used: 0, photo_existing_used: 0 }, total: 5, excluded: false },
    ], scoring);
    expect(csv.startsWith('﻿Rang;Contributeur')).toBe(true);
    expect(csv).toContain(`"'=HYPERLINK(""x"")"`);
  });
});
