import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API_TARGET = "http://localhost:8000";

// La démo est servie par FastAPI sous /demo (StaticFiles) -> base '/demo/' au build,
// mais le serveur de dev Vite reste à la racine pour un rechargement à chaud simple.
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "build" ? "/demo/" : "/",
  server: {
    proxy: {
      "/agent": API_TARGET,
      "/gating": API_TARGET,
      "/audit": API_TARGET,
      "/connectors": API_TARGET,
      "/health": API_TARGET,
    },
  },
  build: {
    // Écrit directement dans app/static, déjà monté par FastAPI (voir app/main.py) et déjà
    // bind-mounté par docker-compose.yml — aucun câblage supplémentaire nécessaire.
    outDir: "../app/static",
    emptyOutDir: true,
  },
}));
