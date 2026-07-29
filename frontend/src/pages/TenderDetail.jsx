/**
 * frontend/src/pages/TenderDetail.jsx
 * -----------------------------------------
 * Purpose: Publisher's tender management page -- shows one tender's
 * full detail, its criteria, its corrigendum history, and a form to
 * issue a new corrigendum (amendment).
 *
 * Why this file exists: routers/tenders.py's corrigendum endpoints
 * (POST /tenders/{id}/corrigendum, GET /tenders/{id}/corrigenda) have
 * existed since Phase 1 with no frontend ever built for them --
 * TenderList.jsx's old "Manage" button pointed here, but this page
 * never existed until now.
 */

import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Descriptions, Table, Tag, Button, Form, Input, Switch, DatePicker, message, Spin, Divider } from "antd";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import AppLayout from "../components/AppLayout.jsx";

async function fetchTender(tenderId) {
  const response = await apiClient.get(`/tenders/${tenderId}`);
  return response.data;
}

async function fetchCriteria(tenderId) {
  const response = await apiClient.get(`/tenders/${tenderId}/criteria`);
  return response.data;
}

async function fetchCorrigenda(tenderId) {
  const response = await apiClient.get(`/tenders/${tenderId}/corrigenda`);
  return response.data;
}

function TenderDetail() {
  const { t } = useTranslation();
  const { tenderId } = useParams();
  const [isMaterial, setIsMaterial] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const { data: tender, isLoading: tenderLoading } = useQuery({
    queryKey: ["tender", tenderId],
    queryFn: () => fetchTender(tenderId),
  });

  const { data: criteria } = useQuery({
    queryKey: ["criteria", tenderId],
    queryFn: () => fetchCriteria(tenderId),
  });

  const { data: corrigenda, refetch: refetchCorrigenda } = useQuery({
    queryKey: ["corrigenda", tenderId],
    queryFn: () => fetchCorrigenda(tenderId),
  });

  async function handleIssueCorrigendum(values) {
    setSubmitting(true);
    try {
      await apiClient.post(`/tenders/${tenderId}/corrigendum`, {
        description: values.description,
        is_material: isMaterial,
        new_deadline: isMaterial && values.new_deadline ? values.new_deadline.toISOString() : null,
      });
      message.success("Corrigendum issued");
      form.resetFields();
      setIsMaterial(false);
      refetchCorrigenda();
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not issue corrigendum");
    } finally {
      setSubmitting(false);
    }
  }

  const criteriaColumns = [
    { title: t("tenderList.criteria"), dataIndex: "code", key: "code", width: 60 },
    { title: t("createTender.description"), dataIndex: "description", key: "description", ellipsis: true },
    { title: t("tenderDetail.category"), dataIndex: "category", key: "category", width: 120 },
  ];

  const corrigendaColumns = [
    {
      title: t("tenderDetail.issuedAt"),
      dataIndex: "issued_at",
      key: "issued_at",
      render: (d) => new Date(d).toLocaleString(),
    },
    {
      title: t("tenderDetail.material"),
      dataIndex: "is_material",
      key: "is_material",
      render: (v) => <Tag color={v ? "orange" : "default"}>{v ? t("tenderDetail.materialYes") : t("tenderDetail.materialNo")}</Tag>,
    },
    { title: t("createTender.description"), dataIndex: "description", key: "description" },
    {
      title: t("createTender.deadline"),
      dataIndex: "new_deadline",
      key: "new_deadline",
      render: (d) => (d ? new Date(d).toLocaleString() : "--"),
    },
  ];

  if (tenderLoading) return <AppLayout><Spin size="large" /></AppLayout>;

  return (
    <AppLayout>
      <h2>{tender?.name}</h2>

      <Descriptions bordered size="small" column={2} style={{ marginBottom: 24 }}>
        <Descriptions.Item label={t("common.status")}><Tag>{tender?.status}</Tag></Descriptions.Item>
        <Descriptions.Item label={t("tenderList.value")}>₹{tender?.estimated_value}L</Descriptions.Item>
        <Descriptions.Item label={t("tenderList.deadline")}>{new Date(tender?.deadline).toLocaleString()}</Descriptions.Item>
        <Descriptions.Item label={t("tenderList.criteria")}>{tender?.criteria_count}</Descriptions.Item>
      </Descriptions>

      <Divider orientation="left">{t("tenderDetail.criteriaList")}</Divider>
      <Table
        rowKey="id"
        columns={criteriaColumns}
        dataSource={criteria}
        pagination={{ pageSize: 10 }}
        size="small"
      />

      <Divider orientation="left">{t("tenderDetail.corrigendumHistory")}</Divider>
      <Table
        rowKey="id"
        columns={corrigendaColumns}
        dataSource={corrigenda}
        pagination={false}
        size="small"
        locale={{ emptyText: t("tenderDetail.noCorrigenda") }}
      />

      <Divider orientation="left">{t("tenderDetail.issueCorrigendum")}</Divider>
      <Form form={form} layout="vertical" onFinish={handleIssueCorrigendum} style={{ maxWidth: 500 }}>
        <Form.Item
          label={t("createTender.description")}
          name="description"
          rules={[{ required: true }]}
        >
          <Input.TextArea rows={3} placeholder={t("tenderDetail.corrigendumDescriptionPlaceholder")} />
        </Form.Item>

        <Form.Item label={t("tenderDetail.materialChange")}>
          <Switch checked={isMaterial} onChange={setIsMaterial} />
          <span style={{ marginLeft: 8, color: "#666", fontSize: 12 }}>
            {t("tenderDetail.materialChangeHelp")}
          </span>
        </Form.Item>

        {isMaterial && (
          <Form.Item
            label={t("tenderDetail.newDeadline")}
            name="new_deadline"
            rules={[{ required: true }]}
          >
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>
        )}

        <Button type="primary" htmlType="submit" loading={submitting}>
          {t("tenderDetail.issueButton")}
        </Button>
      </Form>
    </AppLayout>
  );
}

export default TenderDetail;