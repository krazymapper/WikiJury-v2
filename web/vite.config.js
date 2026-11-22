import { defineConfig } from 'vite';

export default defineConfig({
  // Chemins relatifs : le site fonctionne sur https://<compte>.github.io/<dépôt>/ comme en local.
  base: './',
  server: { fs: { allow: ['..'] } },
  build: { outDir: 'dist', emptyOutDir: true },
  test: { include: ['test/**/*.test.js'] },
});
