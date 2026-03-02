import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NuqsAdapter } from 'nuqs/adapters/react';
import App from './App'
import './index.css'
import './styles/shell-2026.css'
import './styles/data-manager-2026.css'
import './styles/analysis-2026.css'
import { hasConfiguredApiRequestRewrite, resolveApiRequestUrl } from './utils';
import { bootstrapAuthSession } from './auth/supabaseAuth';
import { initializeWebMcpTools } from './webmcp';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

initializeWebMcpTools();

if (
  typeof window !== "undefined" &&
  typeof window.fetch === "function" &&
  hasConfiguredApiRequestRewrite
) {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === "string" && input.startsWith("/api")) {
      return nativeFetch(resolveApiRequestUrl(input), init);
    }
    return nativeFetch(input, init);
  };
}

const mount = () => {
  ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <NuqsAdapter>
          <App />
        </NuqsAdapter>
      </QueryClientProvider>
    </React.StrictMode>
  );
};

const bootstrapAndMount = async () => {
  try {
    await bootstrapAuthSession();
  } catch (error) {
    console.error("Auth bootstrap failed:", error);
  } finally {
    mount();
  }
};

bootstrapAndMount().catch((error) => {
  console.error("App bootstrap failed:", error);
  mount();
});
