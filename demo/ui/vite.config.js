import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /state, /run, /test belong to demo/web_demo.py (port 8765)
const api = "http://localhost:8765";
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/state": api, "/run": api, "/test": api } },
});
