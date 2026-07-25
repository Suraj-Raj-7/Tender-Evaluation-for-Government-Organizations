/**
 * frontend/src/pages/TenderList.jsx
 * --------------------------------------
 * Purpose: Shows every tender the logged-in user can see (all tenders
 * for most roles; only assigned tenders for Evaluators; DRAFT tenders
 * hidden from Bidders -- both filters enforced by the backend).
 *
 * Why this file exists: matches the Phase Guide's pages/TenderList.jsx
 * spec -- Ant Design Table, columns for id/name/status/value/deadline/
 * criteria count, actions that differ by role. Text now fully wired
 * to react-i18next for EN/HI support.
 */

import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Button, Spin, Alert } from "antd";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import AppLayout from "../components/AppLayout.jsx";

async function fetchTenders() {
  const response = await apiClient.get("/tenders");
  return response.data;
}

/**
 * Purpose: Maps a tender status to a muted background/text color
 * pair, matching the visual polish pass's government-platform style.
 */
function statusStyle(status) {
  const styles = {
    DRAFT: { background: "#ECEFF3", color: "#3B4A5A" },
    PUBLISHED: { background: "#E3EDFB", color: "#1D5EA8" },
    CORRIGENDUM_ISSUED: { background: "#FBF1DF", color: "#B8760F" },
    EVALUATION: { background: "#EFE9FB", color: "#6741A8" },
    TECHNICAL_COMPLETE: { background: "#E7F5EE", color: "#1E8E5A" },
    NO_QUALIFIED_BIDDERS: { background: "#FBEAEA", color: "#C4383A" },
    AWARDED: { background: "#0E2238", color: "#fff" },
    CANCELLED: { background: "#ECEFF3", color: "#64748B" },
  };
  return styles[status] || { background: "#ECEFF3", color: "#3B4A5A" };
}

function TenderList() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();

  const { data: tenders, isLoading, error } = useQuery({
    queryKey: ["tenders"],
    queryFn: fetchTenders,
  });

  const columns = [
    { title: t("tenderList.id"), dataIndex: "id", key: "id" },
    { title: t("tenderList.name"), dataIndex: "name", key: "name" },
    {
      title: t("common.status"),
      dataIndex: "status",
      key: "status",
      render: (status) => {
        const style = statusStyle(status);
        return (
          <Tag style={{ background: style.background, color: style.color, fontWeight: 600 }}>
            {status}
          </Tag>
        );
      },
    },
    {
      title: t("tenderList.value"),
      dataIndex: "estimated_value",
      key: "estimated_value",
      render: (v) => <span style={{ fontFamily: "'IBM Plex Mono', monospace" }}>₹{v}L</span>,
    },
    {
      title: t("tenderList.deadline"),
      dataIndex: "deadline",
      key: "deadline",
      render: (d) => new Date(d).toLocaleString(),
    },
    { title: t("tenderList.criteria"), dataIndex: "criteria_count", key: "criteria_count" },
    {
      title: t("common.actions"),
      key: "actions",
      render: (_, record) => (
        <>
          {user?.role === "EVALUATOR" && (
            <Button size="small" onClick={() => navigate(`/tenders/${record.id}/matrix`)}>
              {t("tenderList.evaluate")}
            </Button>
          )}
          {user?.role === "PUBLISHER" && (
            <Button size="small" onClick={() => navigate(`/tenders/${record.id}`)}>
              {t("tenderList.manage")}
            </Button>
          )}
          {user?.role === "BIDDER" && (
            <Button size="small" onClick={() => navigate(`/bidder-portal`)}>
              {t("tenderList.applyNow")}
            </Button>
          )}
        </>
      ),
    },
  ];

  return (
    <AppLayout>
      {user?.role === "PUBLISHER" && (
        <Button
          type="primary"
          style={{ marginBottom: 16 }}
          onClick={() => navigate("/tenders/create")}
        >
          {t("tenderList.createTender")}
        </Button>
      )}

      {isLoading && <Spin size="large" />}
      {error && <Alert type="error" message="Could not load tenders" showIcon />}

      {tenders && (
        <Table rowKey="id" columns={columns} dataSource={tenders} pagination={false} />
      )}
    </AppLayout>
  );
}

export default TenderList;