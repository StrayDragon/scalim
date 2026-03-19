import { defineConfig } from "vite";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";
import { svelte, vitePreprocess } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "tailwindcss";
import autoprefixer from "autoprefixer";
import tailwindConfig from "./tailwind.config";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    svelte({
      preprocess: vitePreprocess(),
      configFile: false
    })
  ],
  worker: {
    format: "es"
  },
  optimizeDeps: {
    // monaco-yaml's worker depends on `path-browserify` (CJS). In dev, Vite may serve it untransformed to workers,
    // which breaks with `ReferenceError: module is not defined`. Force pre-bundling to ESM.
    include: ["path-browserify"]
  },
  css: {
    postcss: {
      plugins: [tailwindcss(tailwindConfig), autoprefixer()]
    }
  },
  resolve: {
    alias: {
      $app: resolve(__dirname, "src/app"),
      $domain: resolve(__dirname, "src/domain"),
      $services: resolve(__dirname, "src/services"),
      $ui: resolve(__dirname, "src/ui"),
      $utils: resolve(__dirname, "src/libs/utils"),
      $components: resolve(__dirname, "src/libs/components"),
      $schema_blocks: resolve(__dirname, "src/libs/schema_blocks")
    }
  },
  server: {
    port: 5174,
    strictPort: true
  }
});
