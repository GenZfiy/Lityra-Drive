import { Loader2, Inbox, WifiOff } from "lucide-react";
import { useLocation } from "react-router-dom";

function pageFamily(path) {
  if (path.startsWith("/drive/recruiter")) return ["Recruiter operations", "recruiter"];
  if (path.startsWith("/drive/test")) return ["Assessment session", "assessment"];
  if (path.startsWith("/drive")) return ["Career opportunities", "opportunity"];
  if (/\/(admin|trainer|curriculum|access-codes|roles|users|institution-analytics|placement|audit|course-builder|content-studio)/.test(path)) return ["Institution studio", "institution"];
  if (/\/(assessments|certificates|wallet|achievements|skill-map)/.test(path)) return ["Progress & evidence", "evidence"];
  if (/\/(learning|lessons|lesson|practice|drill|worlds|tutor|roadmap)/.test(path)) return ["Learning journey", "learning"];
  return [path.startsWith("/lms") ? "Learn workspace" : "Workspace", "workspace"];
}

export function PageHeader({ title, subtitle, right }) {
  const { pathname } = useLocation();
  const [family, familyKey] = pageFamily(pathname);
  return (
    <header className={`app-page-header app-page-header-${familyKey} flex flex-wrap items-end justify-between gap-3 mb-6`}>
      <div>
        <p className="app-page-eyebrow">{family}</p>
        <h1 className="text-2xl font-display font-bold text-ink-900">{title}</h1>
        {subtitle && <p className="text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
      {right}
    </header>
  );
}

export function Loading({ label = "Loading…" }) {
  return (
    <div className="app-loading grid place-items-center py-20 text-slate-400">
      <Loader2 className="app-loading-icon animate-spin mb-3" size={28} />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function EmptyState({ title = "Nothing here yet", hint }) {
  return (
    <div className="app-empty grid place-items-center py-16 text-center">
      <span className="grid place-items-center h-12 w-12 rounded-xl bg-slate-100 text-slate-400 mb-3">
        <Inbox size={22} />
      </span>
      <p className="font-display font-semibold text-ink-900">{title}</p>
      {hint && <p className="text-sm text-slate-500 mt-1 max-w-sm">{hint}</p>}
    </div>
  );
}

// Small indicator: are we showing live backend data or the offline demo set?
export function DataSource({ live }) {
  if (live) return null;
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/15 text-amber-600">
      <WifiOff size={12} /> Demo data (backend offline)
    </span>
  );
}
