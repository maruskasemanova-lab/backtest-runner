import { defineConfig, loadEnv } from "@rsbuild/core";
import { pluginReact } from "@rsbuild/plugin-react";

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

const { publicVars } = loadEnv({
  prefixes: ["VITE_"],
});

export default defineConfig({
  plugins: [pluginReact()],
  source: {
    entry: {
      index: "./src/main.tsx",
    },
    define: publicVars,
  },
  html: {
    title: "Backtest Runner - Walking Forward Visualization",
  },
  server: {
    port: 5173,
    proxy: proxyConfig,
  },
});
