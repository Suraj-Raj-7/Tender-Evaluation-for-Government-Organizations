/**
 * frontend/src/components/OverrideForm.jsx
 * -----------------------------------------------
 * Purpose: The form an Evaluator uses to change a verdict, with a
 * mandatory written reason.
 *
 * Where it's used: rendered inside EvidencePanel, only for Evaluators.
 * Text now fully wired to react-i18next.
 */

import { useState } from "react";
import { Select, Input, Button, message } from "antd";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";

const { TextArea } = Input;

function OverrideForm({ verdictId, onSuccess }) {
  const { t } = useTranslation();
  const [toVerdict, setToVerdict] = useState(null);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    if (!toVerdict || reason.trim().length < 10) {
      message.warning("Select a verdict and enter a reason of at least 10 characters");
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.post(`/verdicts/${verdictId}/override`, {
        to_verdict: toVerdict,
        reason,
      });
      message.success("Override recorded and logged");
      onSuccess();
    } catch (err) {
      message.error(err.response?.data?.detail || "Override failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <Select
        placeholder={t("evidencePanel.changeVerdictTo")}
        style={{ width: "100%", marginBottom: 8 }}
        value={toVerdict}
        onChange={setToVerdict}
        options={[
          { value: "PASS", label: "PASS" },
          { value: "FAIL", label: "FAIL" },
          { value: "REVIEW", label: "REVIEW" },
        ]}
      />
      <TextArea
        placeholder={t("evidencePanel.reasonPlaceholder")}
        rows={3}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        style={{ marginBottom: 8 }}
      />
      <Button type="primary" onClick={handleSubmit} loading={submitting} block>
        {t("evidencePanel.submitOverride")}
      </Button>
    </div>
  );
}

export default OverrideForm;