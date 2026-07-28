/**
 * frontend/src/pages/AuditLog.jsx
 * --------------------------------------
 * Purpose: Auditor's page -- a filterable table of every logged action
 * platform-wide, reading from Phase 1's GET /audit endpoint.
 *
 * Why this file exists: matches the Phase Guide's pages/AuditLog.jsx
 * spec. Text now fully wired to react-i18next.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Table, Card, Row, Col, Statistic, Select, DatePicker, Spin, Alert, Tabs } from "antd";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import AppLayout from "../components/AppLayout.jsx";
import VerdictBadge from "../components/VerdictBadge.jsx";

const { RangePicker } = DatePicker;

async function fetchAuditLog(filters) {
  const params = {};
  if (filters.action) params.action = filters.action;
  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;

  const response = await apiClient.get("/audit", { params });
  return response.data;
}

async function fetchAuditStats() {
  const response = await apiClient.get("/audit/stats");
  return response.data;
}

async function fetchAllOverrides() {
  const response = await apiClient.get("/audit/overrides");
  return response.data;
}

/**
 * Purpose: Turns whatever old_value/new_value JSON exists on a
 * generic audit log row into a short, readable line of text (e.g.
 * "report_type: audit_bundle") instead of a raw JSON dump -- most
 * action types (LOGIN, REPORT_EXPORTED, GRIEVANCE_SUBMITTED) only
 * ever set one side or the other, since they're event records, not
 * before/after changes.
 *
 * Where it's used: called by the "Details" column's render function
 * below, for every action type except VERDICT_OVERRIDE (which gets
 * its own dedicated verdict-badge rendering instead).
 */
function formatGenericDetails(value) {
  if (!value || typeof value !== "object") return null;
  return Object.entries(value)
    .map(([key, val]) => `${key}: ${val}`)
    .join(", ");
}

function AuditLog() {
  const { t } = useTranslation();
  const [action, setAction] = useState(null);
  const [dateRange, setDateRange] = useState(null);

  const filters = {
    action,
    dateFrom: dateRange?.[0]?.toISOString(),
    dateTo: dateRange?.[1]?.toISOString(),
  };

  const { data: entries, isLoading, error } = useQuery({
    queryKey: ["auditLog", filters],
    queryFn: () => fetchAuditLog(filters),
  });

  const { data: stats } = useQuery({
    queryKey: ["auditStats"],
    queryFn: fetchAuditStats,
  });

  const { data: overrides, isLoading: overridesLoading } = useQuery({
    queryKey: ["allOverrides"],
    queryFn: fetchAllOverrides,
  });

  const overrideCount = entries?.filter((e) => e.action === "VERDICT_OVERRIDE").length || 0;

  const columns = [
    { title: t("auditLog.timestamp"), dataIndex: "timestamp", key: "timestamp", render: (t) => new Date(t).toLocaleString() },
    { title: t("auditLog.userId"), dataIndex: "user_id", key: "user_id" },
    { title: t("auditLog.action"), dataIndex: "action", key: "action" },
    { title: t("auditLog.entityType"), dataIndex: "entity_type", key: "entity_type" },
    { title: t("auditLog.entityId"), dataIndex: "entity_id", key: "entity_id" },
    {
      title: t("auditLog.details"),
      key: "details",
      render: (_, record) => {
        // VERDICT_OVERRIDE reliably has a final_verdict on both sides
        // -- show it as a readable badge-to-badge change. Every other
        // action type (LOGIN, REPORT_EXPORTED, GRIEVANCE_SUBMITTED,
        // etc.) is an event record, not a before/after change, so it
        // gets a clean "key: value" summary instead.
        const oldVerdict = record.old_value?.final_verdict;
        const newVerdict = record.new_value?.final_verdict;

        if (oldVerdict && newVerdict) {
          return (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <VerdictBadge verdict={oldVerdict} />
              <span style={{ color: "#999" }}>→</span>
              <VerdictBadge verdict={newVerdict} />
            </span>
          );
        }

        const oldDetails = formatGenericDetails(record.old_value);
        const newDetails = formatGenericDetails(record.new_value);
        const combined = [oldDetails, newDetails].filter(Boolean).join(" | ");

        return combined || <span style={{ color: "#bbb" }}>--</span>;
      },
    },
  ];

  const overrideColumns = [
    { title: t("auditLog.timestamp"), dataIndex: "overridden_at", key: "overridden_at", render: (t) => new Date(t).toLocaleString() },
    { title: t("auditLog.officer"), dataIndex: "officer_name", key: "officer_name" },
    { title: t("auditLog.tender"), dataIndex: "tender_name", key: "tender_name" },
    { title: t("auditLog.bidder"), dataIndex: "bidder_company_name", key: "bidder_company_name" },
    { title: t("auditLog.criterion"), dataIndex: "criterion_code", key: "criterion_code" },
    {
      title: t("auditLog.oldToNew"),
      key: "change",
      render: (_, record) => (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <VerdictBadge verdict={record.from_verdict} />
          <span style={{ color: "#999" }}>→</span>
          <VerdictBadge verdict={record.to_verdict} />
        </span>
      ),
    },
    { title: t("auditLog.reason"), dataIndex: "reason", key: "reason" },
  ];

  return (
    <AppLayout>
      <h2>{t("auditLog.title")}</h2>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}><Card><Statistic title={t("auditLog.totalActionsShown")} value={entries?.length || 0} /></Card></Col>
        <Col span={8}><Card><Statistic title={t("auditLog.overridesShown")} value={overrideCount} valueStyle={{ color: "#722ed1" }} /></Card></Col>
        <Col span={8}><Card><Statistic title={t("auditLog.extractionErrors")} value={stats?.extraction_error_count ?? 0} valueStyle={{ color: "#C4383A" }} /></Card></Col>
      </Row>

      <Tabs
        defaultActiveKey="all"
        items={[
          {
            key: "all",
            label: t("auditLog.allActionsTab"),
            children: (
              <>
                <div style={{ marginBottom: 16, display: "flex", gap: 12 }}>
                  <Select
                    placeholder={t("auditLog.filterByAction")}
                    allowClear
                    style={{ width: 220 }}
                    value={action}
                    onChange={setAction}
                    options={[
                      { value: "LOGIN", label: "LOGIN" },
                      { value: "VERDICT_OVERRIDE", label: "VERDICT_OVERRIDE" },
                      { value: "DOCUMENT_VIEWED", label: "DOCUMENT_VIEWED" },
                      { value: "TENDER_CREATED", label: "TENDER_CREATED" },
                      { value: "EVALUATION_COMPLETE", label: "EVALUATION_COMPLETE" },
                      { value: "REPORT_EXPORTED", label: "REPORT_EXPORTED" },
                      { value: "GRIEVANCE_SUBMITTED", label: "GRIEVANCE_SUBMITTED" },
                      { value: "NOTIFICATION_SENT", label: "NOTIFICATION_SENT" },
                    ]}
                  />
                  <RangePicker showTime onChange={setDateRange} />
                </div>

                {isLoading && <Spin size="large" />}
                {error && <Alert type="error" message="Could not load audit log" showIcon />}

                {entries && (
                  <Table rowKey="id" columns={columns} dataSource={entries} pagination={{ pageSize: 20 }} />
                )}
              </>
            ),
          },
          {
            key: "overrides",
            label: t("auditLog.overridesTab"),
            children: (
              <>
                {overridesLoading && <Spin size="large" />}
                {overrides && (
                  <Table rowKey="id" columns={overrideColumns} dataSource={overrides} pagination={{ pageSize: 20 }} />
                )}
              </>
            ),
          },
        ]}
      />
    </AppLayout>
  );
}

export default AuditLog;