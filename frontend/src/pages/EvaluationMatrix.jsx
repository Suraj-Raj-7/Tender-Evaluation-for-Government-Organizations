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
import { Table, Card, Row, Col, Statistic, Button, Spin, Alert, message, Tooltip, Space, Modal, Drawer, List } from "antd";
import { ExclamationCircleFilled, DownloadOutlined, ReloadOutlined, FileTextOutlined, PlayCircleOutlined } from "@ant-design/icons";
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

/**
 * Purpose: Fetches metadata for every document one bidder has
 * uploaded -- used by the "View Documents" drawer, so an Evaluator
 * can always reach a bidder's raw submitted files directly, even if
 * AI extraction never ran or failed for them entirely.
 *
 * Where it's used: called by the query powering the documents drawer
 * below, whenever documentsDrawerBidder is set.
 */
async function fetchBidderDocuments(bidderId) {
  const response = await apiClient.get(`/bidders/${bidderId}/documents`);
  return response.data;
}

/**
 * Purpose: Downloads one document's actual bytes and opens it in a
 * new tab -- same pattern used in DocumentViewer.jsx, TenderList.jsx,
 * and BidderPortal.jsx.
 *
 * Where it's used: called by the "View" button inside the documents
 * drawer below.
 */
async function viewDocument(documentId) {
  try {
    const response = await apiClient.get(`/documents/${documentId}`, { responseType: "blob" });
    const blobUrl = URL.createObjectURL(response.data);
    window.open(blobUrl, "_blank");
  } catch (err) {
    message.error("Could not open document");
  }
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
  const [beginningEvaluation, setBeginningEvaluation] = useState(false);
  const [reEvaluatingBidderId, setReEvaluatingBidderId] = useState(null);
  const [documentsDrawerBidder, setDocumentsDrawerBidder] = useState(null);

  const { data: matrixData, isLoading, error, refetch } = useQuery({
    queryKey: ["matrix", tenderId],
    queryFn: () => fetchMatrix(tenderId),
    // Keep polling every 3 seconds while any bidder's evaluation is
    // still running (overall_verdict stays PENDING until their
    // process_one_bidder job finishes) -- stops automatically once
    // every bidder has settled to a real verdict.
    refetchInterval: (query) => {
      const bidders = query.state.data?.bidders;
      const anyPending = bidders?.some((b) => b.overall_verdict === "PENDING");
      return anyPending ? 3000 : false;
    },
  });

  const { data: tenderData, refetch: refetchTender } = useQuery({
    queryKey: ["tender", tenderId],
    queryFn: () => fetchTender(tenderId),
  });

  const { data: drawerDocuments, isLoading: drawerLoading } = useQuery({
    queryKey: ["bidderDocuments", documentsDrawerBidder?.id],
    queryFn: () => fetchBidderDocuments(documentsDrawerBidder.id),
    enabled: !!documentsDrawerBidder,
  });

  const isAlreadyComplete = tenderData?.status === "TECHNICAL_COMPLETE";
  const evaluationNotYetBegun = tenderData?.status === "PUBLISHED" || tenderData?.status === "CORRIGENDUM_ISSUED";
  const deadlinePassed = tenderData ? new Date(tenderData.deadline) < new Date() : false;

  async function performMarkComplete() {
    try {
      await apiClient.post(`/tenders/${tenderId}/complete`);
      message.success("Evaluation marked complete");
      refetch();
      refetchTender();
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not mark complete");
    }
  }

  function handleMarkComplete() {
    Modal.confirm({
      title: t("matrix.confirmCompleteTitle"),
      icon: <ExclamationCircleFilled />,
      content: t("matrix.confirmCompleteBody"),
      okText: t("matrix.confirmCompleteOk"),
      okType: "danger",
      cancelText: t("matrix.confirmCompleteCancel"),
      onOk: performMarkComplete,
    });
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

  /**
   * Purpose: Starts technical evaluation for every bidder on this
   * tender at once -- the moment AI evidence extraction actually
   * happens, deferred from upload time until now. Each bidder
   * processes independently in the background; the matrix will start
   * auto-refreshing (see refetchInterval above) until they all settle.
   *
   * Where it's used: called by the "Begin Evaluation" button, shown
   * only once the deadline has passed and evaluation hasn't started.
   */
  async function handleBeginEvaluation() {
    setBeginningEvaluation(true);
    try {
      const response = await apiClient.post(`/tenders/${tenderId}/begin-evaluation`);
      message.success(response.data.message);
      refetch();
      refetchTender();
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not begin evaluation");
    } finally {
      setBeginningEvaluation(false);
    }
  }

  /**
   * Purpose: Re-runs AI evidence extraction for exactly one bidder --
   * safe to click repeatedly, since any criterion the Evaluator has
   * already manually overridden is always skipped on the backend.
   *
   * Where it's used: called by the per-bidder "Re-evaluate" button in
   * the Actions column below.
   */
  async function handleReEvaluate(bidderId, companyName) {
    setReEvaluatingBidderId(bidderId);
    try {
      const response = await apiClient.post(`/tenders/${tenderId}/bidders/${bidderId}/re-evaluate`);
      message.success(response.data.message);
      refetch();
    } catch (err) {
      message.error(err.response?.data?.detail || `Could not re-evaluate ${companyName}`);
    } finally {
      setReEvaluatingBidderId(null);
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
    {
      title: t("common.actions"),
      key: "bidder_actions",
      fixed: "right",
      width: 190,
      render: (_, bidderRow) => (
        <Space direction="vertical" size="small">
          {user?.role === "EVALUATOR" && (
            <Button
              size="small"
              icon={<ReloadOutlined />}
              loading={reEvaluatingBidderId === bidderRow.id}
              disabled={reEvaluatingBidderId !== null && reEvaluatingBidderId !== bidderRow.id}
              onClick={() => handleReEvaluate(bidderRow.id, bidderRow.company_name)}
            >
              {t("matrix.reEvaluate")}
            </Button>
          )}
          <Button
            size="small"
            icon={<FileTextOutlined />}
            onClick={() => setDocumentsDrawerBidder(bidderRow)}
          >
            {t("matrix.viewDocuments")}
          </Button>
        </Space>
      ),
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

            {evaluationNotYetBegun && !deadlinePassed && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={t("matrix.waitingForDeadline", { deadline: new Date(tenderData.deadline).toLocaleString() })}
        />
      )}

      {evaluationNotYetBegun && deadlinePassed && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={t("matrix.evaluationNotStarted")}
          action={
            user?.role === "EVALUATOR" ? (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={beginningEvaluation}
                onClick={handleBeginEvaluation}
              >
                {t("matrix.beginEvaluation")}
              </Button>
            ) : null
          }
        />
      )}

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

      <Drawer
        title={documentsDrawerBidder ? `${t("matrix.documentsFor")} ${documentsDrawerBidder.company_name}` : ""}
        open={!!documentsDrawerBidder}
        onClose={() => setDocumentsDrawerBidder(null)}
        width={420}
      >
        {drawerLoading && <Spin size="large" />}
        {drawerDocuments && drawerDocuments.length === 0 && (
          <p style={{ color: "#999" }}>{t("matrix.noDocumentsForBidder")}</p>
        )}
        {drawerDocuments && drawerDocuments.length > 0 && (
          <List
            size="small"
            bordered
            dataSource={drawerDocuments}
            renderItem={(doc) => (
              <List.Item>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", gap: 8 }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {doc.original_filename}
                    </div>
                    <div style={{ color: "#999", fontSize: 12 }}>
                      {new Date(doc.uploaded_at).toLocaleString()}
                    </div>
                  </div>
                  <Button size="small" style={{ flexShrink: 0 }} onClick={() => viewDocument(doc.id)}>
                    {t("bidderPortal.view")}
                  </Button>
                </div>
              </List.Item>
            )}
          />
        )}
      </Drawer>
    </AppLayout>
  );
}

export default EvaluationMatrix;