/**
 * frontend/src/components/JobStatusPoller.jsx
 * --------------------------------------------------
 * Purpose: Given a job_id, repeatedly checks GET /jobs/{id} every 3
 * seconds until the background Celery job reaches DONE or FAILED, and
 * shows a loading spinner, success result, or error message
 * accordingly. Calls onComplete(result) once when it finishes.
 *
 * Why this file exists: file uploads (NIT, bidder documents) return
 * immediately with a job_id, but the real OCR+AI work happens in the
 * background and can take anywhere from seconds to several minutes
 * (Phase 4 testing saw a real 21-page tender take ~3.5 minutes). This
 * component is the one place that knows how to wait for that safely,
 * reused by both CreateTender.jsx (tender extraction) and
 * BidderPortal.jsx (bidder evidence extraction) later.
 *
 * Where it gets its data: jobId is passed in by whichever page just
 * triggered an upload.
 */

import { useQuery } from "@tanstack/react-query";
import { Spin, Result, Progress } from "antd";
import apiClient from "../api/client.js";

/**
 * Purpose: Fetches one job's current status.
 * Where it's used: passed to useQuery below as the actual fetch function.
 */
async function fetchJobStatus(jobId) {
  const response = await apiClient.get(`/jobs/${jobId}`);
  return response.data;
}

function JobStatusPoller({ jobId, onComplete }) {
  const { data: job } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJobStatus(jobId),
    // Keep re-fetching every 3 seconds WHILE the job is still running,
    // per the Phase Guide's polling spec -- but stop polling entirely
    // once it reaches a final state (DONE/FAILED), since there's
    // nothing more to check and no reason to keep hitting the backend.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "DONE" || status === "FAILED" ? false : 3000;
    },
  });

  // Fires the parent page's callback exactly once, the moment we see
  // a final state -- e.g. so CreateTender.jsx can show the extracted
  // criteria once ready.
  if (job && (job.status === "DONE" || job.status === "FAILED") && onComplete) {
    onComplete(job);
  }

  if (!job || job.status === "PENDING" || job.status === "RUNNING") {
    return (
      <div style={{ textAlign: "center", padding: 24 }}>
        <Spin size="large" />
        <p style={{ marginTop: 12 }}>
          Processing document -- this can take up to a few minutes for large scanned files...
        </p>
      </div>
    );
  }

  if (job.status === "DONE") {
    return (
      <Result
        status="success"
        title="Processing complete"
        subTitle={
          job.result_summary?.criteria_count !== undefined
            ? `${job.result_summary.criteria_count} criteria extracted`
            : job.result_summary?.evidence_count !== undefined
            ? `${job.result_summary.evidence_count} evidence items extracted`
            : undefined
        }
      />
    );
  }

  return (
    <Result
      status="error"
      title="Processing failed"
      subTitle={job.error_message}
    />
  );
}

export default JobStatusPoller;