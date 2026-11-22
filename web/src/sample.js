// Données fictives au format de l'Outreach Dashboard (ce sont aussi des jeux de test du moteur).
import articles from '../../shared/fixtures/dashboard/course_articles.csv?raw';
import editors from '../../shared/fixtures/dashboard/course_editors.csv?raw';
import uploads from '../../shared/fixtures/dashboard/course_uploads.csv?raw';

export const SAMPLE_FILES = [
  { name: 'course_editors.csv', text: editors },
  { name: 'course_articles.csv', text: articles },
  { name: 'course_uploads.csv', text: uploads },
];
