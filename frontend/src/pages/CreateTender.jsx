/**
 * frontend/src/pages/CreateTender.jsx
 * -----------------------------------------
 * Purpose: Lets a Publisher create a new tender, then upload its NIT
 * document. Shows live processing status via JobStatusPoller, and
 * once extraction finishes, shows the extracted criteria for review.
 *
 * Why this file exists: matches the Phase Guide's pages/CreateTender.jsx
 * spec. Text now fully wired to react-i18next for EN/HI support.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Form, Input, InputNumber, DatePicker, Button, Upload, message, List, Tag } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import AppLayout from "../components/AppLayout.jsx";
import JobStatusPoller from "../components/JobStatusPoller.jsx";

function CreateTender() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [tenderId, setTenderId] = useState(null);
  const [file, setFile] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [criteria, setCriteria] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleCreateTender(values) {
    setSubmitting(true);
    try {
      const response = await apiClient.post("/tenders", {
        name: values.name,
        description: values.description,
        estimated_value: values.estimated_value,
        deadline: values.deadline.toISOString(),
      });
      setTenderId(response.data.id);
      message.success("Tender created. Now upload the NIT document.");
    } catch (err) {
      message.error("Could not create tender");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUploadDocument() {
    if (!file) {
      message.warning("Select a file first");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);

    setSubmitting(true);
    try {
      const response = await apiClient.post(
        `/tenders/${tenderId}/document`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setJobId(response.data.job_id);
    } catch (err) {
      message.error("Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleJobComplete(job) {
    if (job.status === "DONE" && !criteria) {
      const response = await apiClient.get(`/tenders/${tenderId}/criteria`);
      setCriteria(response.data);
    }
  }

  return (
    <AppLayout>
      <h2>{t("createTender.title")}</h2>

      {!tenderId && (
        <Form layout="vertical" onFinish={handleCreateTender} style={{ maxWidth: 500 }}>
          <Form.Item label={t("createTender.tenderName")} name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label={t("createTender.description")} name="description" rules={[{ required: true }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item
            label={t("createTender.estimatedValue")}
            name="estimated_value"
            rules={[{ required: true }]}
          >
            <InputNumber style={{ width: "100%" }} min={0} />
          </Form.Item>
          <Form.Item label={t("createTender.deadline")} name="deadline" rules={[{ required: true }]}>
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting}>
            {t("createTender.createButton")}
          </Button>
        </Form>
      )}

      {tenderId && !jobId && (
        <div style={{ maxWidth: 500 }}>
          <Upload
            beforeUpload={(selectedFile) => {
              setFile(selectedFile);
              return false;
            }}
            maxCount={1}
          >
            <Button icon={<UploadOutlined />}>{t("createTender.selectNit")}</Button>
          </Upload>
          <Button
            type="primary"
            style={{ marginTop: 12 }}
            onClick={handleUploadDocument}
            loading={submitting}
          >
            {t("createTender.uploadNit")}
          </Button>
        </div>
      )}

      {jobId && !criteria && (
        <JobStatusPoller jobId={jobId} onComplete={handleJobComplete} />
      )}

      {criteria && (
        <div style={{ marginTop: 24 }}>
          <h3>{criteria.length} {t("createTender.criteriaExtracted")}</h3>
          <List
            bordered
            dataSource={criteria}
            renderItem={(item) => (
              <List.Item>
                <Tag>{item.code}</Tag> {item.description}
              </List.Item>
            )}
          />
          <Button
            type="primary"
            style={{ marginTop: 16 }}
            onClick={() => navigate("/tenders")}
          >
            {t("createTender.backToList")}
          </Button>
        </div>
      )}
    </AppLayout>
  );
}

export default CreateTender;