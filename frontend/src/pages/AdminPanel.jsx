/**
 * frontend/src/pages/AdminPanel.jsx
 * ----------------------------------------
 * Purpose: System Admin's page -- create new officer accounts and
 * manage existing users (deactivate/reactivate/reset password).
 *
 * Why this file exists: matches the Phase Guide's pages/
 * AdminPanel.jsx spec. Text now fully wired to react-i18next.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Button, Form, Input, Select, Modal, message, Space } from "antd";
import { useTranslation } from "react-i18next";
import apiClient from "../api/client.js";
import AppLayout from "../components/AppLayout.jsx";

async function fetchUsers() {
  const response = await apiClient.get("/admin/users");
  return response.data;
}

function AdminPanel() {
  const { t } = useTranslation();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [resettingUserId, setResettingUserId] = useState(null);
  const [form] = Form.useForm();

  const { data: users, isLoading, refetch } = useQuery({
    queryKey: ["adminUsers"],
    queryFn: fetchUsers,
  });

  async function handleCreateUser(values) {
    setCreating(true);
    try {
      await apiClient.post("/admin/users", values);
      message.success("User created. Temporary password printed to server console.");
      setCreateModalOpen(false);
      form.resetFields();
      refetch();
    } catch (err) {
      message.error(err.response?.data?.detail || "Could not create user");
    } finally {
      setCreating(false);
    }
  }

  async function handleToggleStatus(userId, newStatus) {
    try {
      await apiClient.patch(`/admin/users/${userId}`, { is_active: newStatus });
      message.success(newStatus ? "User reactivated" : "User deactivated");
      refetch();
    } catch (err) {
      message.error("Could not update user status");
    }
  }

  async function handleResetPassword(userId) {
    setResettingUserId(userId);
    try {
      await apiClient.post(`/admin/users/${userId}/reset-password`);
      message.success("Password reset. New credentials sent by email.");
    } catch (err) {
      message.error("Could not reset password");
    } finally {
      setResettingUserId(null);
    }
  }

  const columns = [
    { title: t("adminPanel.username"), dataIndex: "username", key: "username" },
    { title: t("adminPanel.fullName"), dataIndex: "full_name", key: "full_name" },
    { title: t("adminPanel.role"), dataIndex: "role", key: "role", render: (r) => <Tag>{r}</Tag> },
    {
      title: t("common.status"),
      dataIndex: "is_active",
      key: "is_active",
      render: (active) => <Tag color={active ? "green" : "red"}>{active ? t("adminPanel.active") : t("adminPanel.inactive")}</Tag>,
    },
    {
      title: t("common.actions"),
      key: "actions",
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => handleToggleStatus(record.id, !record.is_active)}>
            {record.is_active ? t("adminPanel.deactivate") : t("adminPanel.reactivate")}
          </Button>
          <Button
            size="small"
            loading={resettingUserId === record.id}
            disabled={resettingUserId !== null && resettingUserId !== record.id}
            onClick={() => handleResetPassword(record.id)}
          >
            {t("adminPanel.resetPassword")}
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <AppLayout>
      <h2>{t("adminPanel.title")}</h2>

      <Button type="primary" style={{ marginBottom: 16 }} onClick={() => setCreateModalOpen(true)}>
        {t("adminPanel.createNewUser")}
      </Button>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={users}
        loading={isLoading}
        pagination={false}
      />

      <Modal
        title={t("adminPanel.createOfficerAccount")}
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={handleCreateUser}>
          <Form.Item label={t("adminPanel.username")} name="username" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label={t("adminPanel.fullName")} name="full_name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label={t("adminPanel.email")} name="email" rules={[{ required: true, type: "email" }]}>
            <Input />
          </Form.Item>
          <Form.Item label={t("adminPanel.role")} name="role" rules={[{ required: true }]}>
            <Select
              options={[
                { value: "PUBLISHER", label: "Publisher" },
                { value: "EVALUATOR", label: "Evaluator" },
                { value: "AUDITOR", label: "Auditor" },
              ]}
            />
          </Form.Item>
          <Form.Item label={t("adminPanel.department")} name="department">
            <Input />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={creating}>
            {t("adminPanel.createUser")}
          </Button>
        </Form>
      </Modal>
    </AppLayout>
  );
}

export default AdminPanel;
