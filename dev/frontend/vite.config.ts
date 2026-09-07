import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API_TARGET = "http://localhost:8000";

// La démo est servie par FastAPI sous /demo (StaticFiles) -> base '/demo/' au build,
// mais le serveur de dev Vite reste à la racine pour un rechargement à chaud simple.
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "build" ? "/demo/" : "/",
  server: {
    // 5173 (le port par défaut) tombe régulièrement dans une plage de ports que Windows exclut
    // dynamiquement pour le NAT Hyper-V (souvent après un redémarrage de Docker Desktop/WSL2) —
    // `netsh interface ipv4 show excludedportrange protocol=tcp` le confirme. 5400 est en dehors
    // des plages observées. Si ça se reproduit avec CE port aussi, relancer avec `-- --port N`
    // ou réinitialiser le service : `net stop winnat && net start winnat` (PowerShell admin).
    port: 5400,
    proxy: {
      "/agent": API_TARGET,
      "/gating": API_TARGET,
      "/audit": API_TARGET,
      "/connectors": API_TARGET,
      "/settings": API_TARGET,
      "/rag": API_TARGET,
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
