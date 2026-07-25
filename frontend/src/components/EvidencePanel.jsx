/**
 * frontend/src/components/EvidencePanel.jsx
 * -------------------------------------------------
 * Purpose: The drawer that opens when an evaluator clicks any verdict
 * badge in the matrix. Shows the full detail behind one AI decision.
 *
 * Why this file exists: matches the Phase Guide's components/
 * EvidencePanel.jsx spec. Text now fully wired to react-i18next.
 */

import { useQuery } from "@tanstack/react-query";
import { Drawer, Descriptions, Progress, Spin, Divider, Typography } from "antd";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import VerdictBadge from "./VerdictBadge.jsx";
import DocumentViewer from "./DocumentViewer.jsx";
import OverrideForm from "./OverrideForm.jsx";
import OverrideHistory from "./OverrideHistory.jsx";

const { Paragraph } = Typography;

async function fetchEvidenceDetail(evidenceId) {
  const response = await apiClient.get(`/evidence/${evidenceId}`);
  return response.data;
}

function confidenceColor(confidence) {
  const pct = confidence * 100;
  if (pct >= 80) return "#52c41a";
  if (pct >= 60) return "#faad14";
  return "#f5222d";
}

function EvidencePanel({ evidenceId, onClose, onOverrideSuccess }) {
  const { t } = useTranslation();
  const { user } = useAuth();

  const { data: detail, isLoading, refetch } = useQuery({
    queryKey: ["evidence", evidenceId],
    queryFn: () => fetchEvidenceDetail(evidenceId),
    enabled: !!evidenceId,
  });

  return (
    <Drawer
      title={detail ? `${detail.criterion_code} -- Evidence Detail` : "Evidence Detail"}
      open={!!evidenceId}
      onClose={onClose}
      width={520}
    >
      {isLoading && <Spin size="large" />}

      {detail && (
        <>
          <Paragraph type="secondary">{detail.criterion_description}</Paragraph>

          <VerdictBadge verdict={detail.ai_verdict} />
          {detail.is_overridden && (
            <span style={{ marginLeft: 8, color: "#722ed1" }}>
              (overridden to <VerdictBadge verdict={detail.final_verdict} />)
            </span>
          )}

          <Descriptions column={1} bordered size="small" style={{ marginTop: 16 }}>
            <Descriptions.Item label={t("evidencePanel.extractedValue")}>
              {detail.raw_value || <span style={{ color: "#999" }}>{t("evidencePanel.noneFound")}</span>}
            </Descriptions.Item>
            <Descriptions.Item label={t("evidencePanel.sourceDocument")}>
              <DocumentViewer documentId={detail.document_id} docName={detail.doc_name} />
            </Descriptions.Item>
            <Descriptions.Item label={t("evidencePanel.page")}>
              {detail.page_number || "--"}
            </Descriptions.Item>
            <Descriptions.Item label={t("evidencePanel.extractedAt")}>
              {new Date(detail.extracted_at).toLocaleString()}
            </Descriptions.Item>
          </Descriptions>

          <div style={{ marginTop: 16 }}>
            <strong>{t("evidencePanel.confidence")}: {(detail.confidence * 100).toFixed(0)}%</strong>
            <Progress
              percent={detail.confidence * 100}
              strokeColor={confidenceColor(detail.confidence)}
              showInfo={false}
            />
          </div>

          <div style={{ marginTop: 16 }}>
            <strong>{t("evidencePanel.aiRationale")}</strong>
            <Paragraph>{detail.ai_rationale || t("evidencePanel.noRationale")}</Paragraph>
          </div>

          {user?.role === "EVALUATOR" && (
            <>
              <Divider />
              <strong>{t("evidencePanel.overrideVerdict")}</strong>
              <div style={{ marginTop: 8 }}>
                <OverrideForm
                  verdictId={detail.verdict_id}
                  onSuccess={() => {
                    refetch();
                    onOverrideSuccess();
                  }}
                />
              </div>
            </>
          )}

          <Divider />
          <strong>{t("evidencePanel.overrideHistory")}</strong>
          <OverrideHistory history={detail.override_history} />
        </>
      )}
    </Drawer>
  );
}

export default EvidencePanel;
