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

const STAFF = ["super_admin", "company_admin", "recruiter", "college_admin"];

function Protected({ children, bare = false, skipGate = false, roles }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="grid min-h-screen place-items-center text-slate-400">Loading…</div>;
  if (!user) return <Navigate to="/hire/login" replace />;
  if (roles && !roles.some((role) => (user.roles || []).includes(role))) return <Navigate to="/drive" replace />;
  if (!skipGate && (user.roles || []).includes("student") && !STAFF.some((role) => (user.roles || []).includes(role)) && !accessGrant.value)
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
      <Route path="/drive/recruiter/access-codes" element={hireStaff(<DriveAccessCodes />)} />
      <Route path="/drive/notifications" element={hire(<Notifications />)} />
      <Route path="/drive/profile" element={hire(<Profile />)} />
      <Route path="/drive/settings" element={hire(<Settings />)} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </Suspense>;
}
