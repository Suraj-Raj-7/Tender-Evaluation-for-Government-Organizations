/**
 * frontend/src/pages/GrievancesPage.jsx
 * ---------------------------------------------
 * Purpose: Auditor's page for reviewing bidder grievances -- lists
 * every grievance platform-wide, and lets the Auditor open one to see
 * full detail and move it through SUBMITTED -> UNDER_REVIEW ->
 * RESOLVED, recording resolution notes.
 *
 * Why this file exists: the backend has supported submitting and
 * storing grievances since Phase 1, and resolving them since this
 * session's PATCH /grievances/{id} endpoint -- but no frontend page
 * ever existed to actually view or act on them. This closes that gap.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Drawer, Select, Input, Button, message, Spin } from "antd";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import AppLayout from "../components/AppLayout.jsx";

const { TextArea } = Input;

async function fetchGrievances() {
  const response = await apiClient.get("/grievances");
  return response.data;
}

async function fetchGrievanceDetail(id) {
  const response = await apiClient.get(`/grievances/${id}`);
  return response.data;
}

/**
 * Purpose: Maps a grievance status to a color, matching the visual
 * pattern used elsewhere in the app for tender/verdict status tags.
 */
function statusColor(status) {
  const colors = {
    SUBMITTED: "gold",
    UNDER_REVIEW: "blue",
    RESOLVED: "green",
  };
  return colors[status] || "default";
}

function GrievancesPage() {
  const { t } = useTranslation();
  const [selectedId, setSelectedId] = useState(null);
  const [newStatus, setNewStatus] = useState(null);
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const { data: grievances, isLoading, error, refetch } = useQuery({
    queryKey: ["grievances"],
    queryFn: fetchGrievances,
  });

  const { data: detail, isLoading: detailLoading, refetch: refetchDetail } = useQuery({
    queryKey: ["grievanceDetail", selectedId],
    queryFn: () => fetchGrievanceDetail(selectedId),
    enabled: !!selectedId,
  });

  function openDrawer(id) {
    setSelectedId(id);
    setNewStatus(null);
    setResolutionNotes("");
  }

  async function handleUpdateStatus() {
    if (!newStatus) {
      message.warning("Select a status first");
      return;
    }
    setSaving(true);
    try {
      await apiClient.patch(`/grievances/${selectedId}`, {
        status: newStatus,
        resolution_notes: resolutionNotes || undefined,
      });
      message.success("Grievance updated");
      refetchDetail();
      refetch();
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not update grievance");
    } finally {
      setSaving(false);
    }
  }

  const columns = [
    { title: t("grievances.id"), dataIndex: "id", key: "id" },
    {
      title: t("common.status"),
      dataIndex: "status",
      key: "status",
      render: (s) => <Tag color={statusColor(s)}>{s}</Tag>,
    },
    { title: t("grievances.description"), dataIndex: "description", key: "description", ellipsis: true },
    {
      title: t("grievances.submittedAt"),
      dataIndex: "submitted_at",
      key: "submitted_at",
      render: (d) => new Date(d).toLocaleString(),
    },
    {
      title: t("common.actions"),
      key: "actions",
      render: (_, record) => (
        <Button size="small" onClick={() => openDrawer(record.id)}>
          {t("grievances.review")}
        </Button>
      ),
    },
  ];

  return (
    <AppLayout>
      <h2>{t("grievances.title")}</h2>

      {isLoading && <Spin size="large" />}
      {error && <p style={{ color: "red" }}>Could not load grievances</p>}

      {grievances && (
        <Table rowKey="id" columns={columns} dataSource={grievances} pagination={{ pageSize: 20 }} />
      )}

      <Drawer
        title={detail ? `${t("grievances.grievance")} #${detail.id}` : ""}
        open={!!selectedId}
        onClose={() => setSelectedId(null)}
        width={480}
      >
        {detailLoading && <Spin size="large" />}

        {detail && (
          <>
            <p><strong>{t("common.status")}:</strong> <Tag color={statusColor(detail.status)}>{detail.status}</Tag></p>
            <p><strong>{t("grievances.tenderId")}:</strong> {detail.tender_id}</p>
            <p><strong>{t("grievances.submittedAt")}:</strong> {new Date(detail.submitted_at).toLocaleString()}</p>
            <p><strong>{t("grievances.description")}:</strong></p>
            <p>{detail.description}</p>

            {detail.resolved_at && (
              <>
                <p><strong>{t("grievances.resolvedAt")}:</strong> {new Date(detail.resolved_at).toLocaleString()}</p>
                <p><strong>{t("grievances.resolutionNotes")}:</strong></p>
                <p>{detail.resolution_notes}</p>
              </>
            )}

            <hr style={{ margin: "16px 0" }} />

            <p><strong>{t("grievances.updateStatus")}</strong></p>
            <Select
              style={{ width: "100%", marginBottom: 8 }}
              placeholder={t("grievances.selectNewStatus")}
              value={newStatus}
              onChange={setNewStatus}
              options={[
                { value: "SUBMITTED", label: "SUBMITTED" },
                { value: "UNDER_REVIEW", label: "UNDER_REVIEW" },
                { value: "RESOLVED", label: "RESOLVED" },
              ]}
            />
            <TextArea
              rows={3}
              placeholder={t("grievances.resolutionNotesPlaceholder")}
              value={resolutionNotes}
              onChange={(e) => setResolutionNotes(e.target.value)}
              style={{ marginBottom: 8 }}
            />
            <Button type="primary" onClick={handleUpdateStatus} loading={saving} block>
              {t("grievances.save")}
            </Button>
          </>
        )}
      </Drawer>
    </AppLayout>
  );
}

export default GrievancesPage;