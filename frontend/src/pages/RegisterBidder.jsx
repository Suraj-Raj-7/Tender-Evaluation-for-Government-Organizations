/**
 * frontend/src/pages/RegisterBidder.jsx
 * --------------------------------------------
 * Purpose: Self-registration form for a new bidder company.
 *
 * Why this file exists: matches the Phase Guide's pages/
 * RegisterBidder.jsx spec. Text now fully wired to react-i18next.
 */

import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Form, Input, Button, Alert, Typography } from "antd";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";

const { Title } = Typography;

function RegisterBidder() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(values) {
    setError(null);
    setSubmitting(true);
    try {
      await apiClient.post("/auth/register-bidder", values);
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div style={{ maxWidth: 400, margin: "100px auto", textAlign: "center" }}>
        <Alert
          type="success"
          showIcon
          message={t("registerBidder.accountCreated")}
          description={t("registerBidder.accountCreatedDesc")}
        />
        <Button type="primary" style={{ marginTop: 16 }} onClick={() => navigate("/login")}>
          {t("registerBidder.goToLogin")}
        </Button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 400, margin: "60px auto" }}>
      <Title level={3} style={{ textAlign: "center" }}>
        {t("registerBidder.title")}
      </Title>

      {error && <Alert message={error} type="error" showIcon style={{ marginBottom: 16 }} />}

      <Form layout="vertical" onFinish={handleSubmit}>
        <Form.Item label={t("registerBidder.companyName")} name="company_name" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label={t("registerBidder.gstin")} name="gstin" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item
          label={t("registerBidder.email")}
          name="email"
          rules={[{ required: true, type: "email" }]}
        >
          <Input />
        </Form.Item>
        <Form.Item label={t("registerBidder.phone")} name="phone" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item
          label={t("registerBidder.password")}
          name="password"
          rules={[{ required: true, min: 8 }]}
        >
          <Input.Password />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" block loading={submitting}>
            {t("registerBidder.register")}
          </Button>
        </Form.Item>
      </Form>

      <div style={{ textAlign: "center", marginTop: 12 }}>
        <Link to="/login">{t("registerBidder.backToLogin")}</Link>
      </div>
    </div>
  );
}

export default RegisterBidder;