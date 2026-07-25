/**
 * frontend/src/components/DocumentViewer.jsx
 * -------------------------------------------------
 * Purpose: A button that opens a source document in a new browser tab.
 * Since GET /documents/{id} requires a JWT header (a plain <a> link
 * can't send one), this fetches the file's raw bytes through our
 * authenticated apiClient first, then opens them as a local blob URL.
 *
 * Where it gets its data: documentId and docName are passed in by
 * EvidencePanel.jsx, from the evidence detail response.
 *
 * Where it's used: rendered inside EvidencePanel, next to the source
 * document reference.
 */

import { Button, message } from "antd";
import { FileTextOutlined } from "@ant-design/icons";
import apiClient from "../api/client.js";

/**
 * Purpose: Downloads the document's actual bytes (with auth attached
 * automatically by apiClient's interceptor) and opens them in a new
 * tab as a temporary local blob URL -- the browser then renders the
 * PDF/image using its own built-in viewer.
 *
 * Where it's used: wired to the button below, on click.
 */
async function openDocument(documentId) {
  try {
    const response = await apiClient.get(`/documents/${documentId}`, {
      responseType: "blob",
    });
    const blobUrl = URL.createObjectURL(response.data);
    window.open(blobUrl, "_blank");
  } catch (err) {
    message.error("Could not open document");
  }
}

function DocumentViewer({ documentId, docName }) {
  if (!documentId) {
    return <span style={{ color: "#999" }}>No source document</span>;
  }

  return (
    <Button
      icon={<FileTextOutlined />}
      size="small"
      onClick={() => openDocument(documentId)}
    >
      {docName || "View document"}
    </Button>
  );
}

export default DocumentViewer;