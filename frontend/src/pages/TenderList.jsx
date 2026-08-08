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

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Button, Spin, Alert, Modal, Select, message } from "antd";
import { FileTextOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import AppLayout from "../components/AppLayout.jsx";

async function fetchTenders() {
  const response = await apiClient.get("/tenders");
  return response.data;
}

async function fetchEvaluators() {
  const response = await apiClient.get("/tenders/evaluators");
  return response.data;
}

/**
 * Purpose: Looks up a tender's NIT document metadata, then downloads
 * its actual bytes (through the authenticated apiClient, same pattern
 * as DocumentViewer.jsx) and opens it in a new browser tab.
 *
 * Where it's used: called by the "View NIT" button below, for any
 * role browsing the tender list.
 */
async function viewNitDocument(tenderId) {
  try {
    const metaResponse = await apiClient.get(`/tenders/${tenderId}/document`);
    const fileResponse = await apiClient.get(`/documents/${metaResponse.data.id}`, {
      responseType: "blob",
    });
    const blobUrl = URL.createObjectURL(fileResponse.data);
    window.open(blobUrl, "_blank");
  } catch (err) {
    message.error(err.response?.data?.detail || "Could not open NIT document");
  }
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
  const [assigningFor, setAssigningFor] = useState(null);
  const [selectedEvaluatorId, setSelectedEvaluatorId] = useState(null);
  const [assigning, setAssigning] = useState(false);

  const { data: tenders, isLoading, error, refetch } = useQuery({
    queryKey: ["tenders"],
    queryFn: fetchTenders,
  });

  async function handlePublish(tenderId) {
    try {
      await apiClient.patch(`/tenders/${tenderId}/status`, { status: "PUBLISHED" });
      message.success("Tender published -- now visible to bidders");
      refetch();
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not publish tender");
    }
  }

  const { data: evaluators } = useQuery({
    queryKey: ["evaluators"],
    queryFn: fetchEvaluators,
    enabled: !!assigningFor,
  });

  async function handleAssignEvaluator() {
    if (!selectedEvaluatorId) {
      message.warning("Select an evaluator first");
      return;
    }
    setAssigning(true);
    try {
      await apiClient.post(`/tenders/${assigningFor.id}/evaluators`, {
        user_id: selectedEvaluatorId,
      });
      message.success(`Evaluator assigned to ${assigningFor.name}`);
      setAssigningFor(null);
      setSelectedEvaluatorId(null);
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not assign evaluator");
    } finally {
      setAssigning(false);
    }
  }

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
          {user?.role === "AUDITOR" && (
            <Button size="small" onClick={() => navigate(`/tenders/${record.id}/matrix`)}>
              {t("tenderList.viewMatrix")}
            </Button>
          )}
          {user?.role === "PUBLISHER" && (
            <>
              {record.status === "DRAFT" && (
                <Button
                  size="small"
                  type="primary"
                  onClick={() => handlePublish(record.id)}
                >
                  {t("tenderList.publish")}
                </Button>
              )}
              <Button size="small" style={{ marginLeft: 8 }} onClick={() => navigate(`/tenders/${record.id}`)}>
                {t("tenderList.manage")}
              </Button>
              <Button
                size="small"
                style={{ marginLeft: 8 }}
                onClick={() => setAssigningFor(record)}
              >
                {t("tenderList.assignEvaluator")}
              </Button>
            </>
          )}
          <Button
            size="small"
            icon={<FileTextOutlined />}
            onClick={() => viewNitDocument(record.id)}
          >
            {t("tenderList.viewNit")}
          </Button>
          {user?.role === "BIDDER" && new Date(record.deadline) > new Date() && (
            <Button size="small" style={{ marginLeft: 8 }} onClick={() => navigate(`/bidder-portal`)}>
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

      <Modal
        title={assigningFor ? `${t("tenderList.assignEvaluator")} -- ${assigningFor.name}` : ""}
        open={!!assigningFor}
        onCancel={() => setAssigningFor(null)}
        onOk={handleAssignEvaluator}
        confirmLoading={assigning}
        okText={t("tenderList.assign")}
      >
        <Select
          style={{ width: "100%" }}
          placeholder={t("tenderList.selectEvaluator")}
          value={selectedEvaluatorId}
          onChange={setSelectedEvaluatorId}
          options={evaluators?.map((e) => ({ value: e.id, label: `${e.full_name} (${e.username})` }))}
        />
      </Modal>
    </AppLayout>
  );
}

export default TenderList;