import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

// Chromium blocks fetch()/ES-module (`<script type="module">`) loading of
// other local files when a page is opened via file:// (research.md §10) --
// vite-plugin-singlefile inlines everything into one script, but Vite's own
// HTML injection still tags that script `type="module"` and leaves a
// modulepreload-polyfill fetch() call in the bundle. Since nothing is
// code-split (codeSplitting: false below) and this app has no top-level
// `import`/`export`/`await` of its own, the inlined bundle is already valid
// as a plain classic script -- this tiny post-process plugin strips the
// leftover module markers so the shipped index.html matches that reality.
function stripModuleMarkers() {
  return {
    name: "rkby-strip-module-markers",
    enforce: "post",
    // Runs as a Rollup generateBundle hook, same as viteSingleFile's own
    // inlining step -- registered after it in the plugins array below, so
    // it sees the already-inlined HTML (transformIndexHtml runs too early,
    // before inlining has replaced the <script src="..."> reference).
    generateBundle(_options, bundle) {
      for (const fileName of Object.keys(bundle)) {
        if (!fileName.endsWith(".html")) continue;
        const asset = bundle[fileName];
        asset.source = asset.source.replace(
          /<script type="module"( crossorigin)?>/g,
          "<script>",
        );
      }
    },
  };
}

export default defineConfig({
  base: "./",
  plugins: [
    viteSingleFile({ removeViteModuleLoader: true }),
    stripModuleMarkers(),
  ],
  build: {
    modulePreload: false,
    rollupOptions: {
      output: {
        // Vite 8/Rolldown option (see vite-plugin-singlefile's own
        // useRecommendedBuildConfig) -- keep everything in one chunk so
        // there is nothing left for a module loader to fetch.
        codeSplitting: false,
      },
    },
  },
});
