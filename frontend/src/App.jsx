/**
 * frontend/src/App.jsx
 * -------------------------
 * Purpose: Defines every page's URL route, and wraps each protected
 * route with RoleGuard so only the correct role(s) can actually see
 * it -- not just rely on the backend rejecting the API call.
 */

import { Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login.jsx";
import RegisterBidder from "./pages/RegisterBidder.jsx";
import TenderList from "./pages/TenderList.jsx";
import CreateTender from "./pages/CreateTender.jsx";
import EvaluationMatrix from "./pages/EvaluationMatrix.jsx";
import BidderPortal from "./pages/BidderPortal.jsx";
import AdminPanel from "./pages/AdminPanel.jsx";
import AuditLog from "./pages/AuditLog.jsx";
import GrievancesPage from "./pages/GrievancesPage.jsx";
import RoleGuard from "./components/RoleGuard.jsx";

const ALL_ROLES = ["SYSTEM_ADMIN", "PUBLISHER", "BIDDER", "EVALUATOR", "AUDITOR"];

function App() {
  return (
    <Routes>
      {/* Public routes -- no login required */}
      <Route path="/login" element={<Login />} />
      <Route path="/register-bidder" element={<RegisterBidder />} />

      {/* Open to any logged-in role */}
      <Route
        path="/tenders"
        element={<RoleGuard allowedRoles={ALL_ROLES}><TenderList /></RoleGuard>}
      />

      {/* Publisher only */}
      <Route
        path="/tenders/create"
        element={<RoleGuard allowedRoles={["PUBLISHER"]}><CreateTender /></RoleGuard>}
      />

      {/* Evaluator + Auditor only */}
      <Route
        path="/tenders/:tenderId/matrix"
        element={<RoleGuard allowedRoles={["EVALUATOR", "AUDITOR"]}><EvaluationMatrix /></RoleGuard>}
      />

      {/* Bidder only */}
      <Route
        path="/bidder-portal"
        element={<RoleGuard allowedRoles={["BIDDER"]}><BidderPortal /></RoleGuard>}
      />

      {/* System Admin only */}
      <Route
        path="/admin"
        element={<RoleGuard allowedRoles={["SYSTEM_ADMIN"]}><AdminPanel /></RoleGuard>}
      />

      {/* Auditor + System Admin, matching backend's GET /audit permissions */}
      <Route
        path="/audit-log"
        element={<RoleGuard allowedRoles={["AUDITOR", "SYSTEM_ADMIN"]}><AuditLog /></RoleGuard>}
      />

      {/* Auditor only, matching backend's grievance-review permissions */}
      <Route
        path="/grievances"
        element={<RoleGuard allowedRoles={["AUDITOR"]}><GrievancesPage /></RoleGuard>}
      />

      <Route path="/" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default App;