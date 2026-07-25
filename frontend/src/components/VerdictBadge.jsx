/**
 * frontend/src/components/VerdictBadge.jsx
 * -----------------------------------------------
 * Purpose: A small colored tag showing one verdict (PASS/FAIL/REVIEW),
 * clickable to open the full Evidence Panel. Shows a pencil icon if
 * the verdict was manually overridden by an evaluator.
 *
 * Why this file exists: matches the Phase Guide's components/
 * VerdictBadge.jsx spec. Colors updated to a muted, professional
 * palette (visual polish pass) instead of Ant Design's saturated
 * defaults -- logic and behavior unchanged.
 */

import { Tag } from "antd";
import { EditOutlined } from "@ant-design/icons";

/**
 * Purpose: Maps a verdict string to a muted background/text color
 * pair, matching a government-platform visual style rather than
 * Ant Design's bright default tag colors.
 */
function verdictStyle(verdict) {
  const styles = {
    PASS: { background: "#E7F5EE", color: "#1E8E5A" },
    FAIL: { background: "#FBEAEA", color: "#C4383A" },
    REVIEW: { background: "#FBF1DF", color: "#B8760F" },
    MISSING: { background: "#EBF0F5", color: "#5B7A99" },
    ELIGIBLE: { background: "#E7F5EE", color: "#1E8E5A" },
    NOT_ELIGIBLE: { background: "#FBEAEA", color: "#C4383A" },
    MANUAL_REVIEW: { background: "#FBF1DF", color: "#B8760F" },
    PENDING: { background: "#EBF0F5", color: "#5B7A99" },
  };
  return styles[verdict] || { background: "#EBF0F5", color: "#5B7A99" };
}

function VerdictBadge({ verdict, isOverridden, onClick }) {
  const style = verdictStyle(verdict);
  return (
    <Tag
      onClick={onClick}
      style={{
        cursor: onClick ? "pointer" : "default",
        background: style.background,
        color: style.color,
        border: isOverridden ? "1.5px solid #722ed1" : "1px solid transparent",
        fontWeight: 600,
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 12,
      }}
    >
      {isOverridden && <EditOutlined style={{ marginRight: 4 }} />}
      {verdict}
    </Tag>
  );
}

export default VerdictBadge;