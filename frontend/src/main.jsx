/**
 * frontend/src/main.jsx
 * --------------------------
 * Purpose: The real entry point of the app. Wraps everything the app
 * needs at the root level: routing, server-state management, auth,
 * language, and (new) a global visual theme matching a navy/gold
 * "government platform" palette instead of Ant Design's defaults.
 *
 * Why this file exists: Every provider below needs to wrap <App />
 * exactly once, at the top. ConfigProvider's theme tokens here affect
 * every Ant Design component app-wide (buttons, tags, tables) without
 * needing to restyle each component individually.
 */

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider, message } from "antd";
import { AuthProvider } from "./context/AuthContext.jsx";
import App from "./App.jsx";
import "./i18n.js";

// Ant Design's message toasts default to disappearing after 3
// seconds -- too fast to comfortably read a full sentence (e.g. a
// success confirmation with real detail). 5 seconds gives enough
// time without lingering awkwardly. Set once, globally, rather than
// passing a duration to every individual message.success/error call
// across the app.
message.config({ duration: 5 });

const queryClient = new QueryClient();

// Navy/gold palette + IBM Plex typography, applied globally so every
// Ant Design component (buttons, tags, tables, forms) picks it up
// automatically -- purely visual, no behavior change.
const theme = {
  token: {
    colorPrimary: "#16324F",
    colorLink: "#16324F",
    fontFamily: "'IBM Plex Sans', sans-serif",
    borderRadius: 6,
  },
};

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <ConfigProvider theme={theme}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </ConfigProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
);