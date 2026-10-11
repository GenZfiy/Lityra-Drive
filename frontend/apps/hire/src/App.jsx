import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "../../../src/lib/auth.jsx";
import { accessGrant } from "../../../src/lib/api.js";
import { AppShell } from "../../../src/components/layout/AppShell.jsx";

const Login = lazy(() => import("../../../src/pages/Login.jsx"));
const Register = lazy(() => import("../../../src/pages/Register.jsx"));
const ForgotPassword = lazy(() => import("../../../src/pages/ForgotPassword.jsx"));
const Landing = lazy(() => import("../../../src/pages/StandaloneProductLanding.jsx"));
const About = lazy(() => import("../../../src/pages/About.jsx"));
const DriveAccessGate = lazy(() => import("../../../src/pages/DriveAccessGate.jsx"));
const AttendDrive = lazy(() => import("../../../src/pages/AttendDrive.jsx"));
const Drives = lazy(() => import("../../../src/pages/Drives.jsx"));
const MatchedOpportunities = lazy(() => import("../../../src/pages/MatchedOpportunities.jsx"));
const ExamPortal = lazy(() => import("../../../src/pages/ExamPortal.jsx"));
const RecruiterDrives = lazy(() => import("../../../src/pages/recruiter/RecruiterDrives.jsx"));
const DriveConsole = lazy(() => import("../../../src/pages/recruiter/DriveConsole.jsx"));
const QuestionBank = lazy(() => import("../../../src/pages/recruiter/QuestionBank.jsx"));
const DriveAccessCodes = lazy(() => import("../../../src/pages/recruiter/DriveAccessCodes.jsx"));
const Notifications = lazy(() => import("../../../src/pages/Notifications.jsx"));
const Profile = lazy(() => import("../../../src/pages/Profile.jsx"));
const Settings = lazy(() => import("../../../src/pages/Settings.jsx"));
const AccessControl = lazy(() => import("../../../src/pages/AccessControl.jsx"));
const InterviewerConsole = lazy(() => import("../../../src/pages/InterviewerConsole.jsx"));
const AdminOverview = lazy(() => import("../../../src/pages/HireAdministration.jsx").then((m) => ({ default: m.AdminOverview })));
const TrainingCentersAdmin = lazy(() => import("../../../src/pages/HireAdministration.jsx").then((m) => ({ default: m.TrainingCentersAdmin })));
const InstitutionAnalyticsAdmin = lazy(() => import("../../../src/pages/HireAdministration.jsx").then((m) => ({ default: m.InstitutionAnalyticsAdmin })));
const PlacementReadinessAdmin = lazy(() => import("../../../src/pages/HireAdministration.jsx").then((m) => ({ default: m.PlacementReadinessAdmin })));
const InstitutionsAdmin = lazy(() => import("../../../src/pages/HireAdministration.jsx").then((m) => ({ default: m.InstitutionsAdmin })));
const AuditTrailsAdmin = lazy(() => import("../../../src/pages/HireAdministration.jsx").then((m) => ({ default: m.AuditTrailsAdmin })));

const STAFF = ["super_admin", "company_admin", "recruiter", "college_admin", "tpo", "principal"];
const ACCESS_EXEMPT = [...STAFF, "interviewer"];

function Protected({ children, bare = false, skipGate = false, roles, permissions, scopeLevels }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="grid min-h-screen place-items-center text-slate-400">Loading…</div>;
  if (!user) return <Navigate to="/hire/login" replace />;
  if (roles && !roles.some((role) => (user.roles || []).includes(role))) return <Navigate to="/drive" replace />;
  if (permissions && !user.roles?.includes("super_admin")
      && !permissions.some((permission) => (user.permissions || []).includes(permission))) return <Navigate to="/drive" replace />;
  if (scopeLevels && !scopeLevels.includes(user.scope_level)) return <Navigate to="/drive" replace />;
  if (!skipGate && (user.roles || []).includes("student") && !ACCESS_EXEMPT.some((role) => (user.roles || []).includes(role)) && !accessGrant.value)
    return <Navigate to="/drive/access-gate" replace />;
  if (bare) return children;
  return <AppShell product="drive">{children}</AppShell>;
}

const hire = (node) => <Protected>{node}</Protected>;
const hireStaff = (node) => <Protected roles={STAFF}>{node}</Protected>;

export default function HireApp() {
  return <Suspense fallback={<div className="grid min-h-screen place-items-center text-slate-500">Loading Lityra Hire…</div>}>
    <Routes>
      <Route path="/" element={<Landing isHire />} />
      <Route path="/about" element={<About isHire />} />
      <Route path="/login" element={<Login product="hire" />} />
      <Route path="/register" element={<Register product="hire" />} />
      <Route path="/hire/login" element={<Login product="hire" />} />
      <Route path="/hire/register" element={<Register product="hire" />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/drive/attend" element={<AttendDrive />} />
      <Route path="/drive/access-gate" element={<Protected bare skipGate><DriveAccessGate /></Protected>} />
      <Route path="/drive" element={hire(<Drives />)} />
      <Route path="/drive/opportunities" element={hire(<MatchedOpportunities />)} />
      <Route path="/drive/test/:examId" element={hire(<ExamPortal />)} />
      <Route path="/drive/recruiter/drives" element={hireStaff(<RecruiterDrives />)} />
      <Route path="/drive/recruiter/drives/:id" element={hireStaff(<DriveConsole />)} />
      <Route path="/drive/recruiter/questions" element={hireStaff(<QuestionBank />)} />
      <Route path="/drive/recruiter/access-codes" element={<Protected permissions={["drive.access.manage"]}><DriveAccessCodes /></Protected>} />
      <Route path="/drive/admin/access" element={<Protected permissions={["auth.role.manage", "auth.role.assign", "auth.user.manage", "auth.user.view"]}><AccessControl /></Protected>} />
      <Route path="/drive/admin" element={<Protected permissions={["training.center.view", "training.center.manage", "analytics.platform.view", "analytics.college.view", "analytics.branch.view", "analytics.section.view", "institution.view", "institution.manage", "auth.user.view", "auth.user.manage", "auth.role.manage", "platform.audit.view", "drive.access.manage"]}><AdminOverview /></Protected>} />
      <Route path="/drive/admin/training-centers" element={<Protected permissions={["training.center.view", "training.center.manage"]}><TrainingCentersAdmin /></Protected>} />
      <Route path="/drive/admin/institution-analytics" element={<Protected permissions={["analytics.platform.view", "analytics.college.view", "analytics.branch.view", "analytics.section.view"]}><InstitutionAnalyticsAdmin /></Protected>} />
      <Route path="/drive/admin/placement" element={<Protected permissions={["analytics.platform.view", "analytics.college.view"]} scopeLevels={["platform", "college"]}><PlacementReadinessAdmin /></Protected>} />
      <Route path="/drive/admin/institutions" element={<Protected permissions={["institution.view", "institution.manage"]}><InstitutionsAdmin /></Protected>} />
      <Route path="/drive/admin/users" element={<Protected permissions={["auth.user.view", "auth.user.manage"]}><AccessControl initialTab="users" /></Protected>} />
      <Route path="/drive/admin/roles" element={<Protected permissions={["auth.role.manage", "auth.role.assign"]}><AccessControl initialTab="roles" /></Protected>} />
      <Route path="/drive/admin/audit" element={<Protected permissions={["platform.audit.view"]}><AuditTrailsAdmin /></Protected>} />
      <Route path="/drive/admin/access-ids" element={<Protected permissions={["drive.access.manage"]}><DriveAccessCodes /></Protected>} />
      <Route path="/drive/interviews" element={<Protected permissions={["drive.interview.review"]}><InterviewerConsole /></Protected>} />
      <Route path="/drive/notifications" element={hire(<Notifications />)} />
      <Route path="/drive/profile" element={hire(<Profile />)} />
      <Route path="/drive/settings" element={hire(<Settings />)} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </Suspense>;
}
