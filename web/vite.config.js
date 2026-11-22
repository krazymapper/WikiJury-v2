import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';

const { version } = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'));

export default defineConfig({
  // Chemins relatifs : le site fonctionne sur https://<compte>.github.io/<dépôt>/ comme en local.
  base: './',
  define: { __APP_VERSION__: JSON.stringify(version) },
  server: { fs: { allow: ['..'] } },
  build: { outDir: 'dist', emptyOutDir: true },
  test: { include: ['test/**/*.test.js'] },
});
