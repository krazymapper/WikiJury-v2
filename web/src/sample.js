// Données fictives servant de démonstration (ce sont aussi les jeux de test du moteur).
import articles from '../../shared/fixtures/articles.csv?raw';
import editors from '../../shared/fixtures/editors.csv?raw';
import existing from '../../shared/fixtures/existing_photos.csv?raw';
import uploads from '../../shared/fixtures/uploads.csv?raw';
import wikidata from '../../shared/fixtures/wikidata.csv?raw';

export const SAMPLE_FILES = [
  { name: 'editors.csv', text: editors },
  { name: 'articles.csv', text: articles },
  { name: 'uploads.csv', text: uploads },
  { name: 'wikidata.csv', text: wikidata },
  { name: 'existing_photos.csv', text: existing },
];
