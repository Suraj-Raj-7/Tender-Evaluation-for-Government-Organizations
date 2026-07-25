/**
 * frontend/src/components/RoleGuard.jsx
 * ---------------------------------------------
 * Purpose: Wraps a page component and only renders it if the logged-in
 * user's role is allowed. Redirects to /login if no one is logged in
 * at all; shows a clear "not permitted" message if logged in but with
 * the wrong role -- instead of the page silently trying to load and
 * failing on its first API call with a raw 403.
 *
 * Why this file exists: matches the Phase Guide's components/
 * RoleGuard.jsx spec. Until now, nothing on the frontend actually
 * stopped a user from navigating to a page their role shouldn't see --
 * the backend correctly rejected the underlying API calls, but the
 * page itself would still attempt to render first.
 *
 * Where it's used: wraps every protected <Route>'s element in App.jsx.
 */

import { Navigate } from "react-router-dom";
import { Result } from "antd";
import { useAuth } from "../context/AuthContext.jsx";

function RoleGuard({ allowedRoles, children }) {
  const { user } = useAuth();

  // Not logged in at all -- send them to the login page.
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // Logged in, but this role isn't allowed on this specific page.
  if (!allowedRoles.includes(user.role)) {
    return (
      <Result
        status="403"
        title="Not Authorized"
        subTitle={`Your role (${user.role}) does not have access to this page.`}
      />
    );
  }

  return children;
}

export default RoleGuard;