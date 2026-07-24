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
      //
      // Only in production. A dev server rebuilds constantly, so polling there
      // reports a "new deploy" every minute and turns ordinary in-app
      // navigation into full page reloads — which throws away the sidebar and
      // refetches conversations on every click.
      pollInterval: process.env.NODE_ENV === "production" ? 60000 : 0,
    },
  },
};

export default config;
