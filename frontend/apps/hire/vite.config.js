import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(appRoot, "../..");

export default defineConfig({
  root: appRoot,
  envDir: frontendRoot,
  publicDir: resolve(frontendRoot, "public"),
  plugins: [react()],
  define: { "import.meta.env.VITE_PRODUCT_ID": JSON.stringify("hire") },
  resolve: { preserveSymlinks: true, alias: { "@": resolve(frontendRoot, "src") } },
  server: {
    fs: { allow: [frontendRoot] },
    port: 5175,
    proxy: { "/api": {
      target: process.env.VITE_API_TARGET || "http://127.0.0.1:8000",
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ""),
    } },
  },
  build: {
    outDir: resolve(frontendRoot, "dist"),
    emptyOutDir: true,
    rollupOptions: { output: { manualChunks(id) {
      if (id.includes("/node_modules/lucide-react/")) return "lucide-vendor";
      if (id.includes("/node_modules/three/")) return "three-vendor";
    } } },
  },
});
