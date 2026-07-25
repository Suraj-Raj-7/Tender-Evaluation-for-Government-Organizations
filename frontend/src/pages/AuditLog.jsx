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
import { Table, Card, Row, Col, Statistic, Select, DatePicker, Spin, Alert } from "antd";
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

  const overrideCount = entries?.filter((e) => e.action === "VERDICT_OVERRIDE").length || 0;

  const columns = [
    { title: t("auditLog.timestamp"), dataIndex: "timestamp", key: "timestamp", render: (t) => new Date(t).toLocaleString() },
    { title: t("auditLog.userId"), dataIndex: "user_id", key: "user_id" },
    { title: t("auditLog.action"), dataIndex: "action", key: "action" },
    { title: t("auditLog.entityType"), dataIndex: "entity_type", key: "entity_type" },
    { title: t("auditLog.entityId"), dataIndex: "entity_id", key: "entity_id" },
    {
      title: t("auditLog.oldToNew"),
      key: "change",
      render: (_, record) => {
        // AuditLog rows can be any action type, not just overrides --
        // old_value/new_value only reliably contains a final_verdict
        // key for VERDICT_OVERRIDE entries. For any other action,
        // fall back to the raw JSON so nothing is silently hidden.
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

        return record.old_value || record.new_value
          ? `${JSON.stringify(record.old_value)} -> ${JSON.stringify(record.new_value)}`
          : "--";
      },
    },
  ];

  return (
    <AppLayout>
      <h2>{t("auditLog.title")}</h2>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}><Card><Statistic title={t("auditLog.totalActionsShown")} value={entries?.length || 0} /></Card></Col>
        <Col span={8}><Card><Statistic title={t("auditLog.overridesShown")} value={overrideCount} valueStyle={{ color: "#722ed1" }} /></Card></Col>
      </Row>

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
          ]}
        />
        <RangePicker showTime onChange={setDateRange} />
      </div>

      {isLoading && <Spin size="large" />}
      {error && <Alert type="error" message="Could not load audit log" showIcon />}

      {entries && (
        <Table rowKey="id" columns={columns} dataSource={entries} pagination={{ pageSize: 20 }} />
      )}
    </AppLayout>
  );
}

export default AuditLog;