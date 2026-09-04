/**
 * frontend/src/pages/ChangePassword.jsx
 * ---------------------------------------------
 * Purpose: Lets any logged-in user change their own password, proving
 * they know the current one first. Backend endpoint (POST
 * /auth/change-password) already existed and worked -- this is the
 * first and only frontend page that ever calls it.
 *
 * Where it's used: routed at /change-password (see App.jsx), reached
 * via the "Change Password" button in AppLayout.jsx's header.
 */

import { useState } from "react";
import { Form, Input, Button, Alert, Typography } from "antd";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import AppLayout from "../components/AppLayout.jsx";

const { Title } = Typography;

function ChangePassword() {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  /**
   * Purpose: Sends the current + new password to the backend. The
   * "confirm new password" field is checked client-side (via the
   * form's own validator below) before this ever runs -- the backend
   * itself only ever sees current_password and new_password, matching
   * PasswordChangeRequest's schema exactly.
   *
   * Where it gets its data: values.current_password and
   * values.new_password come from the form fields below.
   */
  async function handleSubmit(values) {
    setError(null);
    setSuccess(false);
    setSubmitting(true);
    try {
      await apiClient.post("/auth/change-password", {
        current_password: values.current_password,
        new_password: values.new_password,
      });
      setSuccess(true);
      form.resetFields();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not change password");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AppLayout>
      <div style={{ maxWidth: 400, margin: "40px auto" }}>
        <Title level={3}>{t("changePassword.title")}</Title>

        {success && (
          <Alert
            type="success"
            showIcon
            message={t("changePassword.successMessage")}
            style={{ marginBottom: 16 }}
          />
        )}
        {error && (
          <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />
        )}

        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            label={t("changePassword.currentPassword")}
            name="current_password"
            rules={[{ required: true }]}
          >
            <Input.Password />
          </Form.Item>

          <Form.Item
            label={t("changePassword.newPassword")}
            name="new_password"
            rules={[{ required: true, min: 8 }]}
            extra={t("changePassword.minLengthHint")}
          >
            <Input.Password />
          </Form.Item>

          <Form.Item
            label={t("changePassword.confirmNewPassword")}
            name="confirm_new_password"
            dependencies={["new_password"]}
            rules={[
              { required: true },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("new_password") === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error(t("changePassword.mismatchError")));
                },
              }),
            ]}
          >
            <Input.Password />
          </Form.Item>

          <Button type="primary" htmlType="submit" block loading={submitting}>
            {t("changePassword.submit")}
          </Button>
        </Form>
      </div>
    </AppLayout>
  );
}

export default ChangePassword;
