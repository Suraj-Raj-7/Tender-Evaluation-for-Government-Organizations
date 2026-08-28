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
import { Table, Tag, Button, Spin, Alert, Modal, Upload, Input, List, Popconfirm, message } from "antd";
import { UploadOutlined, FileTextOutlined, DeleteOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import AppLayout from "../components/AppLayout.jsx";

const { TextArea } = Input;

async function fetchMyApplications() {
  const response = await apiClient.get("/bidders/me");
  return response.data;
}

async function fetchBidderDocuments(bidderId) {
  const response = await apiClient.get(`/bidders/${bidderId}/documents`);
  return response.data;
}

/**
 * Purpose: Downloads one document's actual bytes (through the
 * authenticated apiClient) and opens it in a new tab -- same pattern
 * as DocumentViewer.jsx and TenderList.jsx's View NIT button.
 *
 * Where it's used: called by the "View" button in the already-
 * uploaded-documents list inside the upload modal below.
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

function BidderPortal() {
  const { t } = useTranslation();
  const [uploadingFor, setUploadingFor] = useState(null);
  const [files, setFiles] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [grievanceFor, setGrievanceFor] = useState(null);
  const [grievanceText, setGrievanceText] = useState("");
  const [submittingGrievance, setSubmittingGrievance] = useState(false);

  const { data: applications, isLoading, error, refetch } = useQuery({
    queryKey: ["myApplications"],
    queryFn: fetchMyApplications,
  });

  const { data: existingDocuments, refetch: refetchDocuments } = useQuery({
    queryKey: ["bidderDocuments", uploadingFor?.id],
    queryFn: () => fetchBidderDocuments(uploadingFor.id),
    enabled: !!uploadingFor,
  });

    /**
   * Purpose: Removes a document the bidder previously uploaded --
   * only meaningful before the deadline, since nothing is ever
   * AI-processed until the Evaluator begins evaluation (see
   * begin-evaluation on the backend), so deleting is a clean,
   * side-effect-free action with nothing downstream to worry about.
   *
   * Where it's used: called by the Delete button in the "already
   * uploaded" document list below, after the user confirms via
   * Popconfirm.
   */
  async function handleDeleteDocument(documentId) {
    try {
      await apiClient.delete(`/documents/${documentId}`);
      message.success("Document deleted");
      refetchDocuments();
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not delete document");
    }
  }

  async function handleSubmitGrievance() {
    if (grievanceText.trim().length < 20) {
      message.warning("Description must be at least 20 characters");
      return;
    }
    setSubmittingGrievance(true);
    try {
      await apiClient.post(`/grievances?tender_id=${grievanceFor.tender_id}`, {
        description: grievanceText,
      });
      message.success("Grievance submitted");
      setGrievanceFor(null);
      setGrievanceText("");
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not submit grievance");
    } finally {
      setSubmittingGrievance(false);
    }
  }

  async function handleUpload() {
    if (files.length === 0) {
      message.warning("Select at least one file");
      return;
    }
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));

    setSubmitting(true);
    try {
      await apiClient.post(
        `/tenders/${uploadingFor.tender_id}/bidders/${uploadingFor.id}/documents`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      message.success("Documents uploaded");
      setFiles([]);
      refetchDocuments();
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

      return (
        <>
          <Tag color={verdictColor}>{record.overall_verdict}</Tag>
          {record.overall_verdict === "NOT_ELIGIBLE" && (
            <Button
              size="small"
              style={{ marginLeft: 8 }}
              onClick={() => {
                setGrievanceFor(record);
                setGrievanceText("");
              }}
            >
              {t("bidderPortal.raiseGrievance")}
            </Button>
          )}
        </>
      );
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
        {existingDocuments && existingDocuments.length > 0 && (
          <>
            <p style={{ fontWeight: 600, marginBottom: 4 }}>{t("bidderPortal.alreadyUploaded")}</p>
            <List
              size="small"
              bordered
              style={{ marginBottom: 16 }}
              dataSource={existingDocuments}
              renderItem={(doc) => (
                <List.Item
                  actions={[
                    <Button
                      key="view"
                      size="small"
                      icon={<FileTextOutlined />}
                      onClick={() => viewDocument(doc.id)}
                    >
                      {t("bidderPortal.view")}
                    </Button>,
                    <Popconfirm
                      key="delete"
                      title={t("bidderPortal.confirmDelete")}
                      onConfirm={() => handleDeleteDocument(doc.id)}
                      okText={t("bidderPortal.yesDelete")}
                      cancelText={t("bidderPortal.cancel")}
                    >
                      <Button size="small" danger icon={<DeleteOutlined />}>
                        {t("bidderPortal.delete")}
                      </Button>
                    </Popconfirm>,
                  ]}
                >
                  <span>{doc.original_filename}</span>
                  <span style={{ color: "#999", fontSize: 12, marginLeft: 8 }}>
                    {new Date(doc.uploaded_at).toLocaleString()}
                  </span>
                </List.Item>
              )}
            />
          </>
        )}
        {existingDocuments && existingDocuments.length === 0 && (
          <p style={{ color: "#999", marginBottom: 12 }}>{t("bidderPortal.noDocumentsYet")}</p>
        )}

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
          disabled={submitting}
        >
          {t("bidderPortal.upload")}
        </Button>
      </Modal>

      <Modal
        title={grievanceFor ? `${t("bidderPortal.raiseGrievance")} -- ${grievanceFor.tender_name}` : ""}
        open={!!grievanceFor}
        onCancel={() => setGrievanceFor(null)}
        onOk={handleSubmitGrievance}
        confirmLoading={submittingGrievance}
        okText={t("bidderPortal.submitGrievance")}
      >
        <p style={{ color: "#666", fontSize: 13 }}>
          {t("bidderPortal.grievanceHelp")}
        </p>
        <TextArea
          rows={5}
          placeholder={t("bidderPortal.grievancePlaceholder")}
          value={grievanceText}
          onChange={(e) => setGrievanceText(e.target.value)}
        />
      </Modal>
    </AppLayout>
  );
}

export default BidderPortal;