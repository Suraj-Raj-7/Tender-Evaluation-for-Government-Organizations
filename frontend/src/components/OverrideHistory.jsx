/**
 * frontend/src/components/OverrideHistory.jsx
 * --------------------------------------------------
 * Purpose: Lists every past override for one verdict, in
 * chronological order -- who changed it, from what to what, and why.
 *
 * Where it gets its data: history is the override_history array from
 * GET /evidence/{id} (Phase 4's endpoint already returns this sorted
 * oldest-first).
 *
 * Where it's used: rendered at the bottom of EvidencePanel.jsx.
 */

import { List, Tag } from "antd";
import VerdictBadge from "./VerdictBadge.jsx";

function OverrideHistory({ history }) {
  if (!history || history.length === 0) {
    return <p style={{ color: "#999" }}>No overrides yet.</p>;
  }

  return (
    <List
      size="small"
      dataSource={history}
      renderItem={(item) => (
        <List.Item>
          <div>
            <Tag>{item.officer_id}</Tag>
            <VerdictBadge verdict={item.from_verdict} />
            {" -> "}
            <VerdictBadge verdict={item.to_verdict} />
            <div style={{ marginTop: 4, fontSize: 12, color: "#666" }}>
              {item.reason}
            </div>
            <div style={{ fontSize: 11, color: "#999" }}>
              {new Date(item.overridden_at).toLocaleString()}
            </div>
          </div>
        </List.Item>
      )}
    />
  );
}

export default OverrideHistory;