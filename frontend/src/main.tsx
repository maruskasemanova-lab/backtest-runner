import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NuqsAdapter } from 'nuqs/adapters/react';
import App from './App'
import './index.css'
import { hasConfiguredApiRequestRewrite, resolveApiRequestUrl } from './utils';
import { bootstrapAuthSession } from './auth/supabaseAuth';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

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
