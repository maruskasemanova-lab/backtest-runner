import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { resolveApiRequestUrl } from './utils';
import { bootstrapAuthSession } from './auth/supabaseAuth';

if (typeof window !== "undefined" && typeof window.fetch === "function") {
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
      <App />
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
