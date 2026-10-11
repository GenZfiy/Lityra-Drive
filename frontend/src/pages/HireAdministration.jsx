import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, ArrowUpRight, Building2, RefreshCw, ShieldCheck, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { Badge, Button, Card, Field, Input, StatTile } from "../components/ui/primitives.jsx";
import { EmptyState, Loading, PageHeader } from "../components/ui/states.jsx";

const label = (value = "") => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const errorText = (e, fallback) => e?.message || fallback;

function Alert({ children }) {
  return children ? <div role="alert" className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{children}</div> : null;
}

export function TrainingCentersAdmin() {
  return <div className="page-composition">
    <PageHeader title="Training Centers" subtitle="Training center operations are managed in Lityra Learn." />
    <Card className="max-w-3xl p-6 sm:p-8">
      <div className="flex items-start gap-4">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-brand-500/10 text-brand-700"><Building2 size={23} /></span>
        <div>
          <h2 className="font-display text-lg font-semibold text-ink-900">Keep training data in its owning product</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Hire and Learn have separate APIs, databases, and sign-in sessions. Hire does not expose training-center, program, batch, or participant management endpoints, so this page does not make requests to the Learn API or show fabricated records.</p>
          <a className="mt-5 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700" href="https://litrya-lms.netlify.app/lms/training-centers" target="_blank" rel="noreferrer">Open Lityra Learn <ArrowUpRight size={16} /></a>
          <p className="mt-3 text-xs text-slate-500">Sign in to Learn separately with an account assigned training-center permissions.</p>
        </div>
      </div>
    </Card>
  </div>;
}

export function InstitutionAnalyticsAdmin() {
  const { user } = useAuth();
  const [data, setData] = useState(null); const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setData(await api.dashboard(user?.roles?.[0] || "hire_admin")); }
    catch (e) { setError(errorText(e, "Institution analytics could not be loaded.")); }
    finally { setLoading(false); }
  }, [user?.roles]);
  useEffect(() => { load(); }, [load]);
  if (loading) return <Loading label="Loading scoped analytics…" />;
  return <div className="page-composition">
    <PageHeader title="Institution Analytics" subtitle="Live aggregate data returned by Hire analytics, scoped to your account." right={<Button variant="secondary" onClick={load}><RefreshCw size={15} /> Refresh</Button>} />
    <Alert>{error}</Alert>
    {data && <>
      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatTile icon={Building2} label="Institutions with analytics facts" value={data.colleges ?? 0} />
        <StatTile icon={Users} label="Learners represented in facts" value={data.learners ?? 0} tone="teal" />
        <StatTile icon={Activity} label="Drives represented in facts" value={data.drives ?? 0} tone="amber" />
      </div>
      <Card className="p-5"><div className="mb-4 flex items-center gap-2"><Activity size={18} className="text-brand-600" /><h2 className="font-semibold text-ink-900">Readiness ranking</h2></div>
        {(data.top_colleges || []).length ? <div className="overflow-x-auto"><table className="w-full min-w-[480px] text-left text-sm"><thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500"><tr><th className="py-3">Rank</th><th>Institution ID</th><th>Readiness index</th></tr></thead><tbody>{data.top_colleges.map((row) => <tr key={row.college_id} className="border-b border-slate-100"><td className="py-3">{row.rank}</td><td className="font-medium text-ink-900">{row.college_id}</td><td>{row.readiness_index}</td></tr>)}</tbody></table></div> : <EmptyState title="No institution ranking available" hint="The backend only returns cross-institution rankings to platform-scoped users. Other roles see scoped aggregate counts." />}
      </Card>
      <p className="mt-3 text-xs text-slate-500">Counts reflect analytics facts available to your scope, not a census of all user or institution records.</p>
    </>}
  </div>;
}

export function PlacementReadinessAdmin() {
  const { user } = useAuth();
  const [rows, setRows] = useState([]); const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      if (user?.permissions?.includes("analytics.platform.view")) setRows(await api.ranking());
      else {
        const colleges = user?.college_ids || [];
        const results = await Promise.all(colleges.map((id) => api.collegeReadiness(id)));
        setRows(results.map((row, i) => ({ rank: i + 1, ...row })));
      }
    } catch (e) { setRows([]); setError(errorText(e, "Placement readiness is unavailable for this scope.")); }
    finally { setLoading(false); }
  }, [user?.permissions, user?.college_ids]);
  useEffect(() => { load(); }, [load]);
  if (loading) return <Loading label="Loading placement readiness…" />;
  return <div className="page-composition">
    <PageHeader title="Placement Readiness" subtitle="Institution-level readiness scores from recorded analytics facts." right={<Button variant="secondary" onClick={load}><RefreshCw size={15} /> Refresh</Button>} />
    <Alert>{error}</Alert>
    <Card className="overflow-hidden p-0"><div className="border-b border-slate-100 p-5"><h2 className="font-semibold text-ink-900">Authorized institution scores</h2><p className="mt-1 text-sm text-slate-500">Student-level eligibility is not included in this endpoint.</p></div>
      {rows.length ? <div className="overflow-x-auto"><table className="w-full min-w-[540px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Rank</th><th className="px-5 py-3">Institution</th><th className="px-5 py-3">Readiness</th><th className="px-5 py-3">Available metrics</th></tr></thead><tbody>{rows.map((row, index) => <tr key={row.college_id} className="border-t border-slate-100"><td className="px-5 py-3">{row.rank || index + 1}</td><td className="px-5 py-3 font-medium text-ink-900">{row.college_id}</td><td className="px-5 py-3"><Badge tone={Number(row.readiness_index) >= 70 ? "teal" : "amber"}>{row.readiness_index}</Badge></td><td className="px-5 py-3 text-slate-600">{row.metrics ? Object.values(row.metrics).filter((v) => v != null).length : "—"}</td></tr>)}</tbody></table></div> : <EmptyState title="No readiness records in your scope" hint={user?.scope_level === "branch" ? "Branch readiness is not modeled by the current analytics facts API." : "No analytics facts are available for your institution assignment yet."} />}
    </Card>
  </div>;
}

export function InstitutionsAdmin() {
  const { user } = useAuth();
  const canManage = (user?.roles || []).some((r) => ["super_admin", "company_admin"].includes(r));
  const canCreate = user?.roles?.includes("super_admin");
  const [rows, setRows] = useState([]); const [query, setQuery] = useState(""); const [error, setError] = useState(""); const [loading, setLoading] = useState(true); const [draft, setDraft] = useState({ name: "", slug: "", timezone: "Asia/Kolkata" }); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { const result = canManage ? await api.organizations() : await api.myOrganization(); setRows(Array.isArray(result) ? result : (result ? [result] : [])); }
    catch (e) { setError(errorText(e, "Institutions could not be loaded.")); }
    finally { setLoading(false); }
  }, [canManage]);
  useEffect(() => { load(); }, [load]);
  const visible = useMemo(() => rows.filter((r) => `${r.name} ${r.slug} ${r.tenant_id}`.toLowerCase().includes(query.toLowerCase())), [rows, query]);
  async function create(event) { event.preventDefault(); setBusy(true); setError(""); try { await api.createOrganization(draft); setDraft({ name: "", slug: "", timezone: "Asia/Kolkata" }); await load(); } catch (e) { setError(errorText(e, "Institution could not be created.")); } finally { setBusy(false); } }
  async function rename(row) { const name = window.prompt("Institution name", row.name); if (!name || name === row.name) return; setError(""); try { await api.updateOrganization(row.id, { name }); await load(); } catch (e) { setError(errorText(e, "Institution could not be updated.")); } }
  async function remove(row) { if (!window.confirm(`Deactivate ${row.name}? This soft-deletes the organization.`)) return; setError(""); try { await api.deleteOrganization(row.id); await load(); } catch (e) { setError(errorText(e, "Institution could not be deactivated.")); } }
  if (loading) return <Loading label="Loading institutions…" />;
  return <div className="page-composition">
    <PageHeader title="Institutions" subtitle={canManage ? "Organizations available to your Hire platform scope." : "Your current organization and tenant configuration."} right={<Button variant="secondary" onClick={load}><RefreshCw size={15} /> Refresh</Button>} />
    <Alert>{error}</Alert>
    {canCreate && <Card className="mb-5 p-5"><h2 className="mb-4 font-semibold text-ink-900">Add institution</h2><form onSubmit={create} className="grid gap-3 sm:grid-cols-3"><Field label="Name"><Input required value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></Field><Field label="URL slug"><Input required pattern="[a-z0-9-]+" value={draft.slug} onChange={(e) => setDraft({ ...draft, slug: e.target.value })} placeholder="example-college" /></Field><Field label="Timezone"><Input value={draft.timezone} onChange={(e) => setDraft({ ...draft, timezone: e.target.value })} /></Field><Button type="submit" disabled={busy} className="sm:col-span-3">{busy ? "Creating…" : "Create institution"}</Button></form></Card>}
    <Card className="overflow-hidden p-0"><div className="border-b border-slate-100 p-3"><Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search institutions" aria-label="Search institutions" /></div>
      {visible.length ? <div className="divide-y divide-slate-100">{visible.map((row) => <article key={row.id} className="flex flex-wrap items-center justify-between gap-4 p-5"><div><h2 className="font-semibold text-ink-900">{row.name}</h2><p className="mt-1 text-xs text-slate-500">{row.slug} · tenant {row.tenant_id} · {row.timezone}</p><p className="mt-2 text-xs text-slate-500">Custom domain: {row.custom_domain || "not configured"} · SMTP: {row.smtp_configured ? "configured" : "not configured"}</p></div>{canManage && <div className="flex gap-2"><Button variant="secondary" size="sm" onClick={() => rename(row)}>Edit name</Button>{canCreate && <Button variant="danger" size="sm" onClick={() => remove(row)}>Deactivate</Button>}</div>}</article>)}</div> : <EmptyState title="No institutions found" hint="The Hire organization API returned no matching records." />}
    </Card>
  </div>;
}

export function AuditTrailsAdmin() {
  const [filters, setFilters] = useState({ actor_id: "", action: "", entity_type: "", partition_key: "" }); const [rows, setRows] = useState([]); const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  const load = useCallback(async () => { setLoading(true); setError(""); try { setRows(await api.auditLogs({ ...filters, limit: 100 })); } catch (e) { setError(errorText(e, "Audit records could not be loaded.")); } finally { setLoading(false); } }, [filters]);
  useEffect(() => { load(); }, [load]);
  return <div className="page-composition">
    <PageHeader title="Audit Trails" subtitle="Read-only security and administrative events. Access is enforced by the audit service." right={<Button variant="secondary" onClick={load}><RefreshCw size={15} /> Refresh</Button>} />
    <Alert>{error}</Alert>
    <Card className="mb-5 p-4"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[["actor_id", "Actor ID"], ["action", "Action"], ["entity_type", "Resource type"], ["partition_key", "Partition"]].map(([key, title]) => <Field key={key} label={title}><Input value={filters[key]} onChange={(e) => setFilters({ ...filters, [key]: e.target.value })} placeholder={`Filter ${title.toLowerCase()}`} /></Field>)}</div><p className="mt-3 text-xs text-slate-500">The current endpoint supports actor, action, entity, correlation, partition and limit filters. Date filtering and export are not exposed by this API.</p></Card>
    {loading ? <Loading label="Loading audit events…" /> : <Card className="overflow-hidden p-0">{rows.length ? <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Time</th><th className="px-4 py-3">Actor</th><th className="px-4 py-3">Action</th><th className="px-4 py-3">Resource</th><th className="px-4 py-3">Result</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-t border-slate-100"><td className="px-4 py-3 whitespace-nowrap">{row.ts ? new Date(row.ts).toLocaleString() : "—"}</td><td className="px-4 py-3">{row.actor_type} · {row.actor_id}</td><td className="px-4 py-3 font-medium text-ink-900">{row.action}</td><td className="px-4 py-3">{row.entity_type}{row.entity_id ? ` · ${row.entity_id}` : ""}</td><td className="px-4 py-3"><Badge tone="teal">Recorded</Badge></td></tr>)}</tbody></table></div> : <EmptyState title="No audit events found" hint="No events matched these filters, or the audit log is empty." />}</Card>}
  </div>;
}

export function AdminOverview() {
  const { user } = useAuth();
  const links = [
    ["Training Centers", "/drive/admin/training-centers", "training.center.view"],
    ["Institution Analytics", "/drive/admin/institution-analytics", "analytics.college.view"],
    ["Placement Readiness", "/drive/admin/placement", "analytics.college.view"],
    ["Institutions", "/drive/admin/institutions", "institution.view"],
    ["User Management", "/drive/admin/users", "auth.user.view"],
    ["Roles & Permissions", "/drive/admin/roles", "auth.role.assign"],
    ["Audit Trails", "/drive/admin/audit", "platform.audit.view"],
    ["Access IDs", "/drive/admin/access-ids", "drive.access.manage"],
  ];
  const allowed = new Set(user?.permissions || []);
  return <div className="page-composition"><PageHeader title="Administration" subtitle="Manage the Hire workspace with access determined by your assigned permissions." />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{links.filter(([, , permission], index) => (index !== 2 || ["platform", "college"].includes(user?.scope_level)) && (user?.roles?.includes("super_admin") || allowed.has(permission) || (index === 1 && ["analytics.platform.view", "analytics.branch.view", "analytics.section.view"].some((p) => allowed.has(p))) || (index === 2 && allowed.has("analytics.platform.view")) || (index === 3 && allowed.has("institution.manage")))).map(([title, to]) => <Link key={to} to={to} className="group"><Card className="h-full p-5 transition hover:-translate-y-0.5 hover:border-brand-300"><div className="flex items-center justify-between"><span className="grid h-10 w-10 place-items-center rounded-lg bg-brand-500/10 text-brand-700"><ShieldCheck size={19} /></span><ArrowUpRight size={16} className="text-slate-400 transition group-hover:text-brand-700" /></div><h2 className="mt-4 font-display font-semibold text-ink-900">{title}</h2><p className="mt-1 text-sm text-slate-500">Open permission-scoped administration.</p></Card></Link>)}</div>
    {!links.some(([, , permission]) => allowed.has(permission)) && !user?.roles?.includes("super_admin") && <Card className="p-5"><EmptyState title="No administration permissions assigned" hint="Ask your organization administrator to grant access to the relevant Hire module." /></Card>}
  </div>;
}
