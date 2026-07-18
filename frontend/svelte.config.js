import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    paths: {
      relative: false,
    },
    version: {
      // Poll for new deploys so the `updated` store flips to true once the
      // server ships a build with different content-hashed chunks. This lets
      // us force a full-page reload before navigating into a route whose old
      // lazily-loaded chunk no longer exists (stale-chunk-after-deploy).
      pollInterval: 60000,
    },
  },
};

export default config;
