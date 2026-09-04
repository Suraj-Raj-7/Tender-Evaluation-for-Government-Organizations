/**
 * frontend/src/components/AppLayout.jsx
 * -------------------------------------------
 * Purpose: The shared page frame every authenticated page renders
 * inside -- header (title, role-aware nav, breadcrumb, language
 * toggle, user avatar, logout) plus the page content below it.
 *
 * Why this file exists: without this, every page would rebuild the
 * same header individually. Visual polish pass (navy/gold palette,
 * avatar, breadcrumb) applied here only -- top nav layout kept exactly
 * as-is per decision to preserve horizontal space for wide tables
 * (the 37-column evaluation matrix needs the width).
 *
 * Where it's used: wraps every real page's content (see App.jsx).
 */

import { Layout, Space, Typography, Button, Menu } from "antd";
import { useTranslation } from "react-i18next";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import LanguageToggle from "./LanguageToggle.jsx";

const { Header, Content } = Layout;
const { Title, Text } = Typography;

function getNavItemsForRole(role) {
  const items = [{ key: "/tenders", label: "Tenders" }];

  if (role === "BIDDER") {
    items.push({ key: "/bidder-portal", label: "My Applications" });
  }
  if (role === "SYSTEM_ADMIN") {
    items.push({ key: "/admin", label: "Admin Panel" });
  }
  if (role === "AUDITOR" || role === "SYSTEM_ADMIN") {
    items.push({ key: "/audit-log", label: "Audit Log" });
  }
  if (role === "AUDITOR") {
    items.push({ key: "/grievances", label: "Grievances" });
  }

  return items;
}

/**
 * Purpose: Builds a short breadcrumb label ("TenderIQ / evaluator")
 * from the current route and role, matching the pattern of showing
 * where in the app the user currently is. Kept as a simple lookup
 * rather than a per-page prop, so no other page file needs editing.
 *
 * Where it's used: rendered once by AppLayout, above the page content.
 */
function getBreadcrumb(pathname, role) {
  const roleLabel = (role || "").toLowerCase().replace("_", " ");
  return `TenderIQ / ${roleLabel}`;
}

/**
 * Purpose: Builds a two-letter avatar label from a username/email, so
 * the header shows a recognizable circle instead of only plain text.
 *
 * Where it's used: called once by AppLayout below.
 */
function getInitials(username) {
  if (!username) return "?";
  const clean = username.split("@")[0];
  return clean.slice(0, 2).toUpperCase();
}

function AppLayout({ children }) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const navItems = getNavItemsForRole(user?.role);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "#0E2238",
          padding: "0 24px",
          height: 64,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <div style={{ lineHeight: 1.1 }}>
            <Title
              level={4}
              style={{ color: "white", margin: 0, lineHeight: 1.2, whiteSpace: "nowrap" }}
            >
              Tender<span style={{ color: "#B8860B" }}>IQ</span>
            </Title>
            <Text
              style={{
                color: "#8FA4BC",
                fontSize: 10.5,
                letterSpacing: 0.4,
                display: "block",
                lineHeight: 1,
              }}
            >
              {getBreadcrumb(location.pathname, user?.role)}
            </Text>
          </div>

          <Menu
            theme="dark"
            mode="horizontal"
            selectedKeys={[location.pathname]}
            onClick={({ key }) => navigate(key)}
            items={navItems}
            style={{ background: "transparent", minWidth: 300, borderBottom: "none" }}
          />
        </div>

        <Space size="large">
          <LanguageToggle />
          {user && (
            <Space size="small">
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  background: "#1B3D5F",
                  color: "white",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                {getInitials(user.username)}
              </div>
              <Text style={{ color: "white" }}>
                {user.username} ({user.role})
              </Text>
            </Space>
          )}
          {/* New: lets any role reach the Change Password page (see
              App.jsx's /change-password route) without needing
              Swagger -- previously the backend endpoint had no
              frontend entry point at all. */}
          <Button onClick={() => navigate("/change-password")}>
            {t("common.changePassword")}
          </Button>
          <Button onClick={handleLogout}>{t("common.logout")}</Button>
        </Space>
      </Header>

      <Content style={{ padding: 24 }}>{children}</Content>
    </Layout>
  );
}

export default AppLayout;