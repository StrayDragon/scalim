import { readFile } from 'node:fs/promises';
import { dirname, resolve, sep } from 'path';
import { defineConfig, type Plugin } from 'vite';
import { fileURLToPath } from 'url';
import { svelte, vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from 'tailwindcss';
import autoprefixer from 'autoprefixer';
import tailwindConfig from './tailwind.config';
import { VIZ_ARTIFACTS_ROOT, VIZ_REPLAY_ROUTE } from './src/generated/project_constants';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../..');
const REPLAY_ALLOWED_ROOT = resolve(REPO_ROOT, VIZ_ARTIFACTS_ROOT);

const scalimVizReplayPlugin = (): Plugin => {
  return {
    name: 'scalim-viz-replay',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        try {
          if (!req.url) return next();
          const url = new URL(req.url, 'http://localhost');
          if (url.pathname !== VIZ_REPLAY_ROUTE) return next();

          const relPath = url.searchParams.get('path') || '';
          if (!relPath) {
            res.statusCode = 400;
            res.end('missing path');
            return;
          }

          const cleaned = relPath.replace(/^\/+/, '');
          const abs = resolve(REPO_ROOT, cleaned);
          const allowed = abs === REPLAY_ALLOWED_ROOT || abs.startsWith(REPLAY_ALLOWED_ROOT + sep);
          if (!allowed) {
            res.statusCode = 403;
            res.end('forbidden');
            return;
          }

          if (!abs.endsWith('.json') && !abs.endsWith('.jsonl')) {
            res.statusCode = 415;
            res.end('unsupported');
            return;
          }

          const content = await readFile(abs);
          res.statusCode = 200;
          res.setHeader('Content-Type', abs.endsWith('.json') ? 'application/json; charset=utf-8' : 'application/x-ndjson; charset=utf-8');
          res.end(content);
        } catch {
          res.statusCode = 404;
          res.end('not found');
        }
      });
    }
  };
};

export default defineConfig({
  plugins: [
    scalimVizReplayPlugin(),
    svelte({
      preprocess: vitePreprocess(),
      configFile: false
    })
  ],
  css: {
    postcss: {
      plugins: [tailwindcss(tailwindConfig), autoprefixer()]
    }
  },
  resolve: {
    alias: {
      $lib: resolve(__dirname, 'src/libs'),
      $components: resolve(__dirname, 'src/libs/components'),
      $ui: resolve(__dirname, 'src/libs/components/ui'),
      $hooks: resolve(__dirname, 'src/libs/hooks'),
      $utils: resolve(__dirname, 'src/libs/utils'),
      $nodes: resolve(__dirname, 'src/components'),
      $panels: resolve(__dirname, 'src/ui/panels'),
      $app: resolve(__dirname, 'src/app'),
      $domain: resolve(__dirname, 'src/domain'),
      $services: resolve(__dirname, 'src/services')
    }
  },
  server: {
    port: 5173,
    strictPort: true
  }
});
