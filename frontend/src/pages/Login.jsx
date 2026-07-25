/**
 * frontend/src/pages/Login.jsx
 * ---------------------------------
 * Purpose: The first page any user (except a self-registering bidder)
 * sees. Collects username + password, calls the backend's login
 * endpoint, and on success saves the token via AuthContext and
 * redirects into the app -- to a role-appropriate landing page, not
 * always the same one.
 *
 * Why this file exists: matches the Phase Guide's pages/Login.jsx
 * spec. Two fixes added after real testing:
 * (1) If someone is already logged in (e.g. navigates back to /login
 *     via browser back/forward), redirect them straight to their
 *     landing page instead of re-rendering the login form -- avoids
 *     the confusing "am I logged in or not" moment noticed during
 *     testing (browser back/forward doesn't clear sessionStorage,
 *     so the session was always still valid -- this just stops the
 *     form from showing when it shouldn't).
 * (2) Redirects to a different page depending on role, instead of
 *     always /tenders -- Bidders land on their applications, Auditors
 *     land on the audit log, everyone else lands on /tenders.
 */

import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Form, Input, Button, Alert, Typography } from "antd";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

const { Title, Text, Link } = Typography;

/**
 * Purpose: Decides which page a given role should land on right after
 * login, instead of everyone always going to /tenders.
 *
 * Where it's used: called once by handleSubmit() below, right after a
 * successful login, and again by the already-logged-in guard above
 * the form.
 */
function landingPageForRole(role) {
  if (role === "BIDDER") return "/bidder-portal";
  if (role === "AUDITOR") return "/audit-log";
  return "/tenders";
}

function Login() {
  const { t } = useTranslation();
  const { token, user, login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // FIX: if a valid session already exists (e.g. browser back/forward
  // brought the user here), skip the form entirely and go straight to
  // their landing page -- never show a login form to someone already
  // logged in.
  if (token && user) {
    return <Navigate to={landingPageForRole(user.role)} replace />;
  }

  /**
   * Purpose: Runs when the login form is submitted. Sends the
   * username/password to the backend, and on success, saves the
   * returned JWT + user info via AuthContext, then navigates to a
   * role-appropriate landing page.
   *
   * Where it gets its data: values are the form fields the user typed
   * (username, password), collected automatically by Ant Design's
   * <Form> component.
   */
  async function handleSubmit(values) {
    setError(null);
    setLoading(true);
    try {
      const response = await apiClient.post("/auth/login", values);
      const { access_token, role, user_id } = response.data;
      login(access_token, { role, user_id, username: values.username });
      navigate(landingPageForRole(role));
    } catch (err) {
      setError(t("login.error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0E2238",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          maxWidth: 380,
          width: "100%",
          background: "white",
          borderRadius: 10,
          padding: "40px 36px",
          boxShadow: "0 12px 40px rgba(0,0,0,0.25)",
        }}
      >
        <Title level={3} style={{ textAlign: "center", marginBottom: 4 }}>
          Tender<span style={{ color: "#B8860B" }}>IQ</span>
        </Title>
        <p style={{ textAlign: "center", color: "#8FA4BC", fontSize: 12, letterSpacing: 0.5, marginBottom: 24 }}>
          {t("login.title")}
        </p>

        {error && (
          <Alert message={error} type="error" showIcon style={{ marginBottom: 16 }} />
        )}

        <Form layout="vertical" onFinish={handleSubmit}>
        <Form.Item
          label={t("login.username")}
          name="username"
          rules={[{ required: true }]}
        >
          <Input autoFocus />
        </Form.Item>

        <Form.Item
          label={t("login.password")}
          name="password"
          rules={[{ required: true }]}
        >
          <Input.Password />
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            {t("login.submit")}
          </Button>
        </Form.Item>
        </Form>

        <div
          style={{
            textAlign: "center",
            marginTop: 20,
            paddingTop: 16,
            borderTop: "1px solid #F0F0F0",
          }}
        >
          <Text type="secondary" style={{ fontSize: 13 }}>
            New bidder company?{" "}
          </Text>
          <Link href="/register-bidder" strong style={{ color: "#16324F", fontSize: 13 }}>
            {t("login.registerLink")}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default Login;