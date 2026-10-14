import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// The built page is served by src/console.py (src/console_ui/dist). For development, `npm run dev`
// serves it with hot reload and passes /api to a console running on port 8090.
export default defineConfig({
  plugins: [svelte()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8090" } },
  build: { outDir: "dist", assetsDir: "assets", target: "es2022", sourcemap: false },
});
