import { NavLink } from "react-router-dom";
import { ArrowRight, BookOpen, Briefcase, Building2, Code2, FileCheck2, Gauge, LayoutDashboard, Library, Search, Users } from "lucide-react";

const learnPath = [
  { to: "/lms/learning", label: "Learn", detail: "Lessons & courses", icon: BookOpen },
  { to: "/lms/practice", label: "Practice", detail: "Challenges & drills", icon: Code2 },
  { to: "/lms/assessments", label: "Demonstrate", detail: "Assessments", icon: FileCheck2 },
  { to: "/lms/careers", label: "Explore", detail: "Career readiness", icon: Briefcase },
];
const institutionPath = [
  { to: "/lms/admin", label: "Institution", detail: "Workspace", icon: Building2 },
  { to: "/lms/course-builder", label: "Curriculum", detail: "Build & publish", icon: Library },
  { to: "/lms/users", label: "People", detail: "Access & roles", icon: Users },
  { to: "/lms/institution-analytics", label: "Outcomes", detail: "Institution view", icon: LayoutDashboard },
];
const candidatePath = [
  { to: "/drive", label: "My drives", detail: "Registered drives", icon: Briefcase },
  { to: "/drive/opportunities", label: "Opportunities", detail: "Explore matches", icon: Search },
];
const recruiterPath = [
  { to: "/drive/recruiter/drives", label: "Drives", detail: "Plan & manage", icon: Building2 },
  { to: "/drive/recruiter/questions", label: "Assessments", detail: "Question bank", icon: FileCheck2 },
  { to: "/drive/recruiter/access-codes", label: "Access", detail: "Candidate IDs", icon: Gauge },
];

export function WorkspacePath({ product, roles = [], pathname }) {
  const isStudent = roles.includes("student");
  const isInstitutionAdmin = ["super_admin", "college_admin", "trainer", "content_manager"].some((role) => roles.includes(role));
  const canAuthor = ["super_admin", "company_admin", "college_admin", "trainer", "faculty", "hod"].some((role) => roles.includes(role));
  const isHireStaff = ["super_admin", "company_admin", "recruiter", "college_admin"].some((role) => roles.includes(role));
  const isLearningStaff = ["super_admin", "company_admin", "college_admin", "trainer", "content_manager", "faculty", "hod", "dean", "principal", "tpo"].some((role) => roles.includes(role));
  const family = product === "drive"
    ? (isHireStaff ? { label: "Recruitment pipeline", nodes: recruiterPath } : { label: "Opportunity path", nodes: candidatePath })
    : (isLearningStaff && !isStudent ? { label: "Institution studio", nodes: institutionPath } : { label: "Learning journey", nodes: learnPath });
  const nodes = family.nodes.filter((node) => {
    if (node.to === "/lms/admin") return isInstitutionAdmin;
    if (node.to === "/lms/course-builder") return canAuthor;
    if (node.to === "/lms/users") return roles.some((role) => ["super_admin", "company_admin"].includes(role));
    if (node.to === "/lms/institution-analytics") return ["super_admin", "company_admin", "college_admin", "principal", "dean", "hod", "tpo", "faculty", "trainer"].some((role) => roles.includes(role));
    return !node.to.startsWith("/drive/recruiter") || isHireStaff;
  });
  if (!nodes.length) return null;

  return (
    <nav className={`workspace-path workspace-path-${product}`} aria-label={family.label}>
      <div className="workspace-path-label"><span className="workspace-path-kicker">The pathway</span><span>{family.label}</span></div>
      <ol>
        {nodes.map(({ to, label, detail, icon: Icon }, index) => (
          <li key={to}>
            <NavLink to={to} end={to === "/drive"} aria-current={pathname === to || pathname.startsWith(`${to}/`) ? "page" : undefined} className={({ isActive }) => `workspace-path-link ${isActive ? "is-current" : ""}`}>
              <span className="workspace-path-index">0{index + 1}</span>
              <span className="workspace-path-icon"><Icon size={15} /></span>
              <span className="workspace-path-copy"><strong>{label}</strong><small>{detail}</small></span>
              {index < nodes.length - 1 && <ArrowRight size={14} className="workspace-path-arrow" aria-hidden="true" />}
            </NavLink>
          </li>
        ))}
      </ol>
    </nav>
  );
}
