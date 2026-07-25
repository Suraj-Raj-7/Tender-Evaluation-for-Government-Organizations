/**
 * frontend/src/pages/BidderPortal.jsx
 * -----------------------------------------
 * Purpose: A bidder's home page -- lists every tender they've applied
 * to, and shows the right action per application based on tender
 * status and deadline.
 *
 * Why this file exists: matches the Phase Guide's pages/
 * BidderPortal.jsx spec. Text now fully wired to react-i18next.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Button, Spin, Alert, Modal, Upload, message } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import AppLayout from "../components/AppLayout.jsx";
import JobStatusPoller from "../components/JobStatusPoller.jsx";

async function fetchMyApplications() {
  const response = await apiClient.get("/bidders/me");
  return response.data;
}

function BidderPortal() {
  const { t } = useTranslation();
  const [uploadingFor, setUploadingFor] = useState(null);
  const [files, setFiles] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const { data: applications, isLoading, error, refetch } = useQuery({
    queryKey: ["myApplications"],
    queryFn: fetchMyApplications,
  });

  async function handleUpload() {
    if (files.length === 0) {
      message.warning("Select at least one file");
      return;
    }
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));

    setSubmitting(true);
    try {
      const response = await apiClient.post(
        `/tenders/${uploadingFor.tender_id}/bidders/${uploadingFor.id}/documents`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setJobId(response.data.job_id);
    } catch (err) {
      message.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  function renderAction(record) {
    const deadlinePassed = new Date(record.tender_deadline) < new Date();

    if (record.tender_status === "TECHNICAL_COMPLETE") {
      const verdictColor = {
        ELIGIBLE: "green",
        NOT_ELIGIBLE: "red",
        MANUAL_REVIEW: "gold",
        PENDING: "default",
      }[record.overall_verdict];
      return <Tag color={verdictColor}>{record.overall_verdict}</Tag>;
    }

    if (deadlinePassed) {
      return <Tag>{t("bidderPortal.awaitingEvaluation")}</Tag>;
    }

    return (
      <Button
        size="small"
        icon={<UploadOutlined />}
        onClick={() => {
          setUploadingFor(record);
          setFiles([]);
          setJobId(null);
        }}
      >
        {t("bidderPortal.uploadDocuments")}
      </Button>
    );
  }

  const columns = [
    { title: t("bidderPortal.tender"), dataIndex: "tender_name", key: "tender_name" },
    { title: t("common.status"), dataIndex: "tender_status", key: "tender_status", render: (s) => <Tag>{s}</Tag> },
    {
      title: t("bidderPortal.deadline"),
      dataIndex: "tender_deadline",
      key: "tender_deadline",
      render: (d) => new Date(d).toLocaleString(),
    },
    { title: t("bidderPortal.action"), key: "action", render: (_, record) => renderAction(record) },
  ];

  return (
    <AppLayout>
      <h2>{t("bidderPortal.title")}</h2>

      {isLoading && <Spin size="large" />}
      {error && <Alert type="error" message="Could not load applications" showIcon />}

      {applications && (
        <Table rowKey="id" columns={columns} dataSource={applications} pagination={false} />
      )}

      <Modal
        title={uploadingFor ? `${t("bidderPortal.uploadDocuments")} -- ${uploadingFor.tender_name}` : ""}
        open={!!uploadingFor}
        onCancel={() => setUploadingFor(null)}
        footer={null}
      >
        {!jobId && (
          <>
            <Upload
              multiple
              beforeUpload={(file) => {
                setFiles((prev) => [...prev, file]);
                return false;
              }}
              onRemove={(file) => setFiles((prev) => prev.filter((f) => f !== file))}
            >
              <Button icon={<UploadOutlined />}>{t("bidderPortal.selectFiles")}</Button>
            </Upload>
            <Button
              type="primary"
              style={{ marginTop: 12 }}
              onClick={handleUpload}
              loading={submitting}
            >
              {t("bidderPortal.upload")}
            </Button>
          </>
        )}

        {jobId && (
          <JobStatusPoller
            jobId={jobId}
            onComplete={(job) => {
              if (job.status === "DONE") {
                message.success("Documents processed successfully");
                refetch();
              }
            }}
          />
        )}
      </Modal>
    </AppLayout>
  );
}

export default BidderPortal;