import { defineConfig } from "astro/config";

// SITE e BASE si impostano in CI (GitHub Pages pubblica sotto /<repo>/).
export default defineConfig({
  site: process.env.SITE_URL || "https://michaelpito.github.io",
  base: process.env.BASE_PATH || "/",
  trailingSlash: "always",
  build: { format: "directory" },
});
