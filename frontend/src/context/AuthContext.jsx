/**
 * frontend/src/context/AuthContext.jsx
 * ----------------------------------------
 * Purpose: Holds "who is currently logged in" (user info, role, JWT
 * token) in one place that any page/component in the app can read or
 * update, without passing it down manually through every component.
 *
 * Why this file exists: without a shared context, each page would need
 * its own copy of "am I logged in, and as who" -- leading to
 * inconsistent state across the app. React Context solves exactly this:
 * one source of truth, read anywhere via useAuth().
 *
 * Where it's used: main.jsx wraps the whole app in <AuthProvider>.
 * Any page calls useAuth() to read {user, role, token} or call
 * login()/logout().
 */

import { createContext, useContext, useState } from "react";

const AuthContext = createContext(null);

/**
 * Purpose: Provides the auth state to every component nested inside
 * it. On first load, checks sessionStorage in case the user refreshed
 * the page (React state resets on refresh, but sessionStorage doesn't)
 * so they aren't wrongly logged out just by reloading the browser.
 *
 * Where it's used: wraps <App /> once, in main.jsx.
 */
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem("token"));
  const [user, setUser] = useState(() => {
    const saved = sessionStorage.getItem("user");
    return saved ? JSON.parse(saved) : null;
  });

  /**
   * Purpose: Saves a successful login's token and user info, both in
   * React state (so the app re-renders immediately) and in
   * sessionStorage (so it survives a page refresh, but clears when the
   * browser tab closes -- per the Phase Guide's token storage spec).
   *
   * Where it gets its data: called by pages/Login.jsx right after a
   * successful POST /auth/login response.
   */
  function login(newToken, newUser) {
    sessionStorage.setItem("token", newToken);
    sessionStorage.setItem("user", JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
  }

  /**
   * Purpose: Clears all auth state, both in React and sessionStorage.
   * Called on explicit logout, and automatically by api/client.js's
   * response interceptor if the backend ever rejects the token.
   */
  function logout() {
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("user");
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ token, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Purpose: The hook every page/component actually calls to read auth
 * state or trigger login/logout -- e.g. `const { user, logout } = useAuth();`
 *
 * Where it's used: RoleGuard.jsx, every page component, LanguageToggle,
 * and anywhere else that needs to know who's logged in.
 */
export function useAuth() {
  return useContext(AuthContext);
}