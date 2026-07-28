/**
 * frontend/src/pages/EvaluationMatrix.jsx
 * ----------------------------------------------
 * Purpose: The core Evaluator/Auditor page -- shows every bidder as a
 * row and every criterion as a column, powered entirely by the single
 * GET /tenders/{id}/matrix endpoint built in Phase 4. Clicking any
 * verdict badge opens the Evidence Panel drawer.
 *
 * Why this file exists: matches the Phase Guide's pages/
 * EvaluationMatrix.jsx spec. Text now fully wired to react-i18next.
 */

import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Table, Card, Row, Col, Statistic, Button, Spin, Alert, message, Tooltip, Space } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import AppLayout from "../components/AppLayout.jsx";
import VerdictBadge from "../components/VerdictBadge.jsx";
import EvidencePanel from "../components/EvidencePanel.jsx";
import { useAuth } from "../context/AuthContext.jsx";

async function fetchMatrix(tenderId) {
  const response = await apiClient.get(`/tenders/${tenderId}/matrix`);
  return response.data;
}

async function fetchTender(tenderId) {
  const response = await apiClient.get(`/tenders/${tenderId}`);
  return response.data;
}

/**
 * Purpose: Downloads a PDF report from the backend and triggers the
 * browser's native "save file" behavior. Axios itself can't save a
 * file to disk -- this fetches the PDF as a blob (raw binary), builds
 * a temporary in-memory URL for it, and clicks a hidden link to it,
 * which is the standard way to force a download from JS.
 *
 * Where it gets its data: url and filename are passed in by the two
 * export button handlers below. apiClient's request interceptor
 * still attaches the JWT automatically, same as any other call.
 *
 * Where it's used: called by handleExportAuditBundle() and
 * handleExportTQList() below.
 */
async function downloadReport(url, filename) {
  const response = await apiClient.get(url, { responseType: "blob" });
  const blobUrl = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(blobUrl);
}

function countByOverallVerdict(bidders) {
  const counts = { ELIGIBLE: 0, NOT_ELIGIBLE: 0, MANUAL_REVIEW: 0, PENDING: 0 };
  bidders.forEach((b) => {
    counts[b.overall_verdict] = (counts[b.overall_verdict] || 0) + 1;
  });
  return counts;
}

function EvaluationMatrix() {
  const { t } = useTranslation();
  const { tenderId } = useParams();
  const { user } = useAuth();
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(null);
  const [exportingAuditBundle, setExportingAuditBundle] = useState(false);
  const [exportingTqList, setExportingTqList] = useState(false);

  const { data: matrixData, isLoading, error, refetch } = useQuery({
    queryKey: ["matrix", tenderId],
    queryFn: () => fetchMatrix(tenderId),
  });

  const { data: tenderData, refetch: refetchTender } = useQuery({
    queryKey: ["tender", tenderId],
    queryFn: () => fetchTender(tenderId),
  });

  const isAlreadyComplete = tenderData?.status === "TECHNICAL_COMPLETE";

  async function handleMarkComplete() {
    try {
      await apiClient.post(`/tenders/${tenderId}/complete`);
      message.success("Evaluation marked complete");
      refetch();
      refetchTender();
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not mark complete");
    }
  }

  async function handleExportAuditBundle() {
    setExportingAuditBundle(true);
    try {
      await downloadReport(
        `/reports/${tenderId}/audit-bundle`,
        `audit_bundle_tender_${tenderId}.pdf`
      );
      message.success("Audit bundle downloaded");
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not export audit bundle");
    } finally {
      setExportingAuditBundle(false);
    }
  }

  async function handleExportTqList() {
    setExportingTqList(true);
    try {
      await downloadReport(
        `/reports/${tenderId}/tq-list`,
        `tq_list_tender_${tenderId}.pdf`
      );
      message.success("TQ list downloaded");
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not export TQ list");
    } finally {
      setExportingTqList(false);
    }
  }

  if (isLoading) return <AppLayout><Spin size="large" /></AppLayout>;
  if (error) return <AppLayout><Alert type="error" message="Could not load matrix" showIcon /></AppLayout>;

  const counts = countByOverallVerdict(matrixData.bidders);

  const columns = [
    { title: t("matrix.bidder"), dataIndex: "company_name", key: "company_name", fixed: "left", width: 200 },
    ...matrixData.criteria.map((criterion) => ({
      title: (
        <Tooltip title={criterion.description} placement="top">
          <span style={{ cursor: "help", borderBottom: "1px dashed #8FA4BC" }}>
            {criterion.code}
          </span>
        </Tooltip>
      ),
      key: criterion.code,
      width: 90,
      render: (_, bidderRow) => {
        const cell = bidderRow.evidence[criterion.code];
        if (!cell) {
          return <VerdictBadge verdict="MISSING" />;
        }
        return (
          <VerdictBadge
            verdict={cell.final_verdict}
            isOverridden={cell.is_overridden}
            onClick={() => setSelectedEvidenceId(cell.evidence_id)}
          />
        );
      },
    })),
    {
      title: t("matrix.overall"),
      key: "overall_verdict",
      fixed: "right",
      width: 130,
      render: (_, bidderRow) => <VerdictBadge verdict={bidderRow.overall_verdict} />,
    },
  ];

  return (
    <AppLayout>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}><Card><Statistic title={t("matrix.eligible")} value={counts.ELIGIBLE} valueStyle={{ color: "green" }} /></Card></Col>
        <Col span={6}><Card><Statistic title={t("matrix.notEligible")} value={counts.NOT_ELIGIBLE} valueStyle={{ color: "red" }} /></Card></Col>
        <Col span={6}><Card><Statistic title={t("matrix.manualReview")} value={counts.MANUAL_REVIEW} valueStyle={{ color: "goldenrod" }} /></Card></Col>
        <Col span={6}><Card><Statistic title={t("matrix.totalBidders")} value={matrixData.bidders.length} /></Card></Col>
      </Row>

      <Space style={{ marginBottom: 16 }}>
        {user?.role === "EVALUATOR" && (
          isAlreadyComplete ? (
            <Button disabled>{t("matrix.evaluationAlreadyComplete")}</Button>
          ) : (
            <Button type="primary" onClick={handleMarkComplete}>
              {t("matrix.markComplete")}
            </Button>
          )
        )}
        {(user?.role === "EVALUATOR" || user?.role === "AUDITOR") && (
          <>
            <Button
              icon={<DownloadOutlined />}
              loading={exportingAuditBundle}
              onClick={handleExportAuditBundle}
            >
              {t("matrix.exportAuditBundle")}
            </Button>
            <Button
              icon={<DownloadOutlined />}
              loading={exportingTqList}
              onClick={handleExportTqList}
            >
              {t("matrix.exportTqList")}
            </Button>
          </>
        )}
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={matrixData.bidders}
        scroll={{ x: "max-content" }}
        pagination={false}
      />

      <EvidencePanel
        evidenceId={selectedEvidenceId}
        onClose={() => setSelectedEvidenceId(null)}
        onOverrideSuccess={() => {
          setSelectedEvidenceId(null);
          refetch();
        }}
      />
    </AppLayout>
  );
}

export default EvaluationMatrix;