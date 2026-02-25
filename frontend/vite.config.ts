import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

const apiProxyTarget = process.env.VITE_PROXY_API_TARGET || "http://localhost:8002";
const wsProxyTarget = process.env.VITE_PROXY_WS_TARGET || "ws://localhost:8002";

const proxyConfig = {
  "/api": {
    target: apiProxyTarget,
    changeOrigin: true,
  },
  "/ws": {
    target: wsProxyTarget,
    ws: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: proxyConfig,
  },
  preview: {
    port: 5173,
    proxy: proxyConfig,
  },
});
