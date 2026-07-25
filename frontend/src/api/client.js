/**
 * frontend/src/api/client.js
 * -----------------------------
 * Purpose: The single Axios instance every page/component uses to talk
 * to the FastAPI backend. Centralizes two things so no page has to
 * repeat them: (1) automatically attaching the logged-in user's JWT to
 * every request, (2) automatically logging the user out if the backend
 * ever says the token is invalid/expired (401).
 *
 * Why this file exists: without this, every single page would need to
 * manually read the token from storage and attach it to every request,
 * and manually handle what happens when a token expires mid-session.
 */

import axios from "axios";

// Talking directly to the FastAPI backend for local development.
// (A production deployment would typically route this through an
// Nginx proxy instead -- see the Phase Guide's Nginx config -- but
// that's a deployment-time concern, not needed for local dev.)
const apiClient = axios.create({
  baseURL: "http://localhost:8000",
});

/**
 * Purpose: Runs before every single outgoing request. Reads the JWT
 * saved at login time and attaches it as an Authorization header, so
 * individual pages never have to think about auth headers themselves.
 *
 * Where it gets its data: sessionStorage's "token" key, written by
 * AuthContext.jsx's login() function.
 *
 * Where it's used: automatically, by every apiClient.get/post/patch/
 * delete call anywhere in the app.
 */
apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Purpose: Runs after every response. If the backend returns 401
 * (token invalid or expired -- e.g. after 8 hours, per security.py's
 * ACCESS_TOKEN_EXPIRE_HOURS), forces a full logout and sends the user
 * back to the login page, instead of leaving them stuck on a broken page.
 *
 * Where it's used: automatically, on every response, by axios itself.
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      sessionStorage.removeItem("token");
      sessionStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default apiClient;