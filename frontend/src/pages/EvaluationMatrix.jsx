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
import { Table, Card, Row, Col, Statistic, Button, Spin, Alert, message, Tooltip } from "antd";
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

  const { data: matrixData, isLoading, error, refetch } = useQuery({
    queryKey: ["matrix", tenderId],
    queryFn: () => fetchMatrix(tenderId),
  });

  async function handleMarkComplete() {
    try {
      await apiClient.post(`/tenders/${tenderId}/complete`);
      message.success("Evaluation marked complete");
      refetch();
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not mark complete");
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

      {user?.role === "EVALUATOR" && (
        <Button type="primary" style={{ marginBottom: 16 }} onClick={handleMarkComplete}>
          {t("matrix.markComplete")}
        </Button>
      )}

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