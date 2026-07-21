import tailwindcss from "@tailwindcss/vite";
import adapter from "@sveltejs/adapter-static";
import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    tailwindcss(),
    sveltekit({
      compilerOptions: {
        runes: ({ filename }) =>
          filename.split(/[/\\]/).includes("node_modules") ? undefined : true,
      },
      adapter: adapter({
        pages: "build",
        assets: "build",
        // Use a distinct filename for the SPA fallback so it doesn't
        // clobber the prerendered "/" (marketing) page's index.html —
        // that collision was silently overwriting the SEO'd homepage
        // with the empty SPA shell on every build.
        fallback: "200.html",
        precompress: false,
        strict: true,
      }),
    }),
  ],
  server: {
    proxy: {
      "/api": {
        target: process.env.BACKEND_URL || "http://localhost:4321",
        changeOrigin: true,
      },
    },
    allowedHosts: [
      "testing.bolodb.dev",
      "localhost",
      "app.bolodb.dev",
      "bolodb.dev",
    ],
  },
});
