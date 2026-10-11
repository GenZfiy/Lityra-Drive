import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Building2, MapPin, Clock, ChevronRight, X, Trash2, Search, Command, Rocket, Trophy, GitBranch } from "lucide-react";
import { Card, Button, Field, Input } from "../../components/ui/primitives.jsx";
import { PageHeader, Loading } from "../../components/ui/states.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { api, withFallback } from "../../lib/api.js";
import { useAuth } from "../../lib/auth.jsx";
import { ReadOut, Attention, bandHex } from "../../components/drive/grammar.jsx";
import CommandPalette from "../../components/drive/CommandPalette.jsx";
import { TiltCard } from "../../components/ui/Decor.jsx";
import "../../styles/recruiter-operations-pages.css";

/* Cross-drive Command Center — the operating console across every drive.
   Real data: api.drives() + api.funnel(id) per drive. */
export default function RecruiterDrives() {
  const { user } = useAuth();
  const canCreateDrive = user?.roles?.includes("super_admin") || user?.permissions?.includes("drive.drive.manage");
  const drivesA = useAsync(() => withFallback(api.drives(), []), []);
  const [creating, setCreating] = useState(false);
  const [extra, setExtra] = useState([]);
  const [removed, setRemoved] = useState(() => new Set());
  const [q, setQ] = useState("");
  const [statusF, setStatusF] = useState("all");
  const [actionError, setActionError] = useState("");
  const [pipelineInvite, setPipelineInvite] = useState(null);
  const [funnels, setFunnels] = useState({}); // driveId -> {total,by_status}
  const [invitations, setInvitations] = useState([]);

  const all = [...(drivesA.data || []), ...extra].filter((d) => !removed.has(d.id));

  useEffect(() => {
    let live = true;
    api.driveInvitations().then((rows) => { if (live) setInvitations(Array.isArray(rows) ? rows : []); }).catch(() => {});
    return () => { live = false; };
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      const entries = await Promise.all(all.map(async (d) => [d.id, await api.funnel(d.id).catch(() => ({ error: true }))]));
      if (alive) setFunnels(Object.fromEntries(entries));
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drivesA.data, extra.length]);

  if (drivesA.loading) return <Loading />;

  const query = q.trim().toLowerCase();
  const list = all.filter((d) => {
    const mq = !query || [d.title, d.company_name, d.venue].some((v) => (v || "").toLowerCase().includes(query));
    const ms = statusF === "all" || d.status === statusF;
    return mq && ms;
  });

  const stat = (d) => funnels[d.id] || null;
  const flightOf = (f) => (f?.by_status?.shortlisted || 0) + (f?.by_status?.in_round || 0);
  const healthOf = (d) => {
    if (d.status === "draft") return "neutral";
    const f = stat(d); if (!f || f.error) return "neutral";
    const sel = f.by_status?.selected || 0; const fl = flightOf(f);
    if (!f.total) return "neutral";
    if (fl > 0 && sel === 0 && f.total >= 10) return "warn";
    return "good";
  };

  const openDrives = all.filter((d) => d.status === "open").length;
  const totalPool = all.reduce((n, d) => n + (stat(d)?.total || 0), 0);
  const totalFlight = all.reduce((n, d) => n + flightOf(stat(d)), 0);
  const totalSelected = all.reduce((n, d) => n + (stat(d)?.by_status?.selected || 0), 0);
  const funnelFailures = all.filter((d) => stat(d)?.error).length;
  const funnelPending = all.filter((d) => !stat(d)).length;
  const poolHint = funnelFailures || funnelPending ? `partial · ${all.length - funnelFailures - funnelPending} of ${all.length} funnels loaded` : "across all drives";

  const actions = [];
  const drafts = all.filter((d) => d.status === "draft");
  if (drafts.length) actions.push({ priority: "high", tone: "warn", icon: Rocket, title: `${drafts.length} drive${drafts.length > 1 ? "s are" : " is"} in draft`, detail: "Open them to start receiving and screening candidates.", actions: [{ label: "Review drafts", primary: true, onClick: () => setStatusF("draft") }] });
  const stalled = all.filter((d) => healthOf(d) === "warn");
  if (stalled.length) actions.push({ priority: "high", tone: "warn", icon: GitBranch, title: `${stalled.length} drive${stalled.length > 1 ? "s" : ""} may be stalled`, detail: "Candidates are in flight but none are selected yet — check for a stage bottleneck.", actions: [{ label: "Open first", primary: true, onClick: () => { window.location.hash = ""; }, }] });
  if (totalSelected) actions.push({ priority: "medium", tone: "teal", icon: Trophy, title: `${totalSelected} candidate${totalSelected > 1 ? "s" : ""} selected across drives`, detail: "Move them to results & offers to close the loop." });

  return (
    <main className="page-composition page-composition-recruiter hire-ops hire-ops--drives"><div className="recruiter-command-page">
      <CommandPalette />
      <header className="hire-ops-intro">
        <div><span className="hire-ops-kicker">Lityra Hire · Portfolio</span><PageHeader
          title="Recruitment Command Center"
          subtitle="Every hiring mission at a glance — state, movement, and what needs attention."
        /></div>
        {canCreateDrive && <Button onClick={() => setCreating(true)}><Plus size={18} /> New drive</Button>}
      </header>

      <section className="hire-portfolio-strip" aria-label="Portfolio activity">
        <ReadOut label="Open drives" value={openDrives} hint={`${all.length} total`} />
        <ReadOut label="Candidate pool" value={totalPool} hint={poolHint} />
        <ReadOut label="In flight" value={totalFlight} hint="shortlisted + in-round" />
        <ReadOut label="Selected" value={totalSelected} hint="ready for offer" />
      </section>

      {invitations.length > 0 && <section className="my-5 rounded-2xl border border-amber-200 bg-amber-50/70 p-5" aria-label="Drive invitations">
        <div className="mb-3"><span className="hire-ops-kicker">Collaboration</span><h2 className="font-display text-lg font-semibold text-ink-900">Drive invitations</h2></div>
        <div className="grid gap-3 lg:grid-cols-2">{invitations.map((invite) => <article key={`${invite.drive_id}-${invite.kind}-${invite.participant_id}`} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-100 bg-white p-4">
          <div><h3 className="font-semibold text-ink-900">{invite.title}</h3><p className="text-sm text-slate-500">{invite.role === "adopter" ? "Company adoption invitation" : `${invite.role} invitation`} · {invite.company_name || invite.drive_type.replaceAll("_", " ")}</p>{invite.venue && <p className="text-xs text-slate-500">{invite.venue}</p>}</div>
          <div className="flex gap-2"><Button variant="secondary" onClick={() => respond(invite, "decline")}>Decline</Button><Button onClick={() => respond(invite, "accept")}>Accept</Button></div>
        </article>)}</div>
      </section>}

      {actionError && <p role="alert" className="hire-drive-error">{actionError}</p>}
      {pipelineInvite?.pipeline_drive_id && <p role="status" className="my-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
        Invitation accepted. Your company pipeline is ready to configure: <Link className="font-semibold underline" to={`/drive/recruiter/drives/${pipelineInvite.pipeline_drive_id}`}>Open company pipeline</Link>
      </p>}
      <div className="hire-portfolio-workbench">
        <aside className="hire-portfolio-rail" aria-label="Portfolio filters and priorities">
        {actions.length > 0 && (
        <section className="hire-portfolio-attention rounded-2xl border border-slate-200 bg-surface overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <h3 className="text-[13.5px] font-semibold text-ink-900 flex items-center gap-2"><Command size={16} className="text-slate-400" /> Needs attention</h3>
            <span className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">across all drives</span>
          </div>
          <Attention items={actions} />
        </section>
      )}

      <form className="hire-portfolio-filters" role="search" onSubmit={(e) => e.preventDefault()}>
        <div><span className="hire-ops-kicker">Portfolio</span><h2>Find a drive</h2><p>Search the hiring work you can access.</p></div>
        <div className="relative">
          <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input aria-label="Search drives by title, company, or venue" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title, company, venue…" className="h-9 pl-8 w-full" />
        </div>
        <label className="hire-portfolio-status"><span>Status</span><select aria-label="Filter drives by status" value={statusF} onChange={(e) => setStatusF(e.target.value)} className="h-9 px-2 rounded-md border border-slate-200 text-sm bg-surface capitalize">
          {["all", "draft", "open", "closed"].map((st) => <option key={st} value={st}>{st === "all" ? "All statuses" : st}</option>)}
        </select></label>
        <span className="text-xs text-slate-400">Showing {list.length} of {all.length}</span>
      </form>
        </aside>

      <section className="hire-portfolio-board" aria-label="Recruitment drives">
      <header className="hire-portfolio-board-heading"><div><span className="hire-ops-kicker">Live portfolio</span><h2>Hiring missions</h2></div><span>{list.length} {list.length === 1 ? "drive" : "drives"}</span></header>
      {list.length === 0 && <Card className="hire-portfolio-empty p-8 text-center text-slate-400">{all.length ? "No drives match your search." : "No drives yet — create your first one."}</Card>}

      <div className="recruiter-mission-board">
        {list.map((d) => {
          const f = stat(d); const health = healthOf(d); const fl = f && !f.error ? flightOf(f) : null; const sel = f && !f.error ? (f.by_status?.selected || 0) : null;
          return (
            <TiltCard key={d.id} strength={4} className="recruiter-mission-card rounded-2xl border border-slate-200 bg-surface p-5 hover:shadow-lift transition-shadow">
              <div className="recruiter-mission-heading">
                <span className="recruiter-mission-icon"><Building2 size={20} /></span>
                <div className="min-w-0"><h2 className="font-display font-semibold text-ink-900 tracking-[-0.01em] truncate">{d.title}</h2><p className="text-sm text-slate-500 truncate">{d.company_name}</p></div>
                <span className="inline-flex items-center gap-1.5 text-[10.5px] font-bold px-2 py-1 rounded" style={{ background: health === "good" ? "rgba(13,148,136,.1)" : health === "warn" ? "rgba(217,119,6,.12)" : "rgba(100,116,139,.1)", color: bandHex(health) }}>
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: bandHex(health) }} />
                  {d.status === "draft" ? "Draft" : health === "good" ? "On track" : health === "warn" ? "Needs attention" : "Idle"}
                </span>
              </div>
              <ol className="recruiter-mission-flow" aria-label={`${d.title} candidate funnel`}>
                {[["Candidates", (f && !f.error ? (f.total ?? 0) : "—")], ["Shortlisted", (f && !f.error ? (f.by_status?.shortlisted ?? 0) : "—")], ["In round", (f && !f.error ? (f.by_status?.in_round ?? 0) : "—")], ["Selected", sel ?? "—"]].map(([label, value], index) => <li key={label} className={index === 3 && value > 0 ? "is-success" : ""}><strong>{value}</strong><span>{label}</span></li>)}
              </ol>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-slate-500">
                {d.venue && <span className="flex items-center gap-1.5"><MapPin size={13} /> {d.venue}</span>}
                {d.reporting_time && <span className="flex items-center gap-1.5"><Clock size={13} /> {d.reporting_time}</span>}
              </div>
              <div className="flex gap-2 mt-4">
                <Button as={Link} to={`/drive/recruiter/drives/${d.id}`} variant="secondary" className="flex-1">Open drive workspace <ChevronRight size={18} /></Button>
                <button onClick={() => del(d)} aria-label="Delete drive" className="grid place-items-center h-11 w-11 rounded-md border border-slate-200 text-slate-400 hover:text-rose-600 hover:border-rose-300"><Trash2 size={17} /></button>
              </div>
            </TiltCard>
          );
        })}
      </div>
      </section>
      </div>

      {creating && <CreateDrive user={user} onClose={() => setCreating(false)} onCreated={(d) => { setExtra((e) => [...e, d]); setCreating(false); }} />}
    </div></main>
  );

  async function del(d) {
    setActionError("");
    if (!window.confirm(`Delete "${d.title}"? This permanently removes the drive and all its rounds, marks, registrations, and results.`)) return;
    try { await api.deleteDrive(d.id); } catch (error) { setActionError(error?.message || `Could not delete "${d.title}".`); return; }
    setRemoved((r) => new Set(r).add(d.id));
  }

  async function respond(invite, decision) {
    setActionError("");
    try {
      const result = await api.respondDriveInvitation(invite.drive_id, invite.kind, invite.participant_id, decision);
      if (decision === "accept" && result?.pipeline_drive_id) {
        setPipelineInvite(result);
        api.drive(result.pipeline_drive_id).then((pipeline) => {
          if (pipeline?.id) setExtra((rows) => [...rows.filter((row) => row.id !== pipeline.id), pipeline]);
        }).catch(() => {});
      }
      setInvitations((rows) => rows.filter((row) => row !== invite));
    } catch (error) { setActionError(error?.message || "Could not update this invitation."); }
  }
}

function CreateDrive({ user, onClose, onCreated }) {
  const collegeOrganizer = (user?.roles || []).some((role) => ["tpo", "college_admin", "dean", "principal"].includes(role));
  const [form, setForm] = useState({ drive_type: collegeOrganizer ? "college_hosted" : "company_off_campus", company_name: "", title: "", venue: "", reporting_time: "", host_college_id: "", college_ids: "", company_ids: "", nomination_required: false, company_confirmation_required: false, host_confirmation_required: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const { college_ids, company_ids, ...fields } = form;
    const body = { ...fields,
      college_ids: college_ids.split(",").map((id) => id.trim()).filter(Boolean),
      company_ids: company_ids.split(",").map((id) => id.trim()).filter(Boolean),
    };
    if (!collegeOrganizer && form.drive_type !== "joint" && form.drive_type !== "multi_college") body.college_ids = [];
    try { const created = await api.createDrive(body); onCreated(created); }
    catch (e) { setError(e?.message || "The drive could not be created. Please try again."); }
    finally { setBusy(false); }
  }
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-invert-950/40 p-4" onClick={onClose}>
      <Card role="dialog" aria-modal="true" aria-labelledby="create-drive-title" className="w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 id="create-drive-title" className="font-display text-lg font-bold text-ink-900">New recruitment drive</h2>
          <button onClick={onClose} className="grid place-items-center h-9 w-9 rounded-md hover:bg-slate-100"><X size={18} /></button>
        </div>
        {error && <p role="alert" className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{error}</p>}
        <form onSubmit={submit} className="space-y-4">
          <Field label="Drive organization model"><select required value={form.drive_type} onChange={(e) => setForm({ ...form, drive_type: e.target.value })} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm">
            {collegeOrganizer && <><option value="college_hosted">College-hosted drive</option><option value="college_adopted">College drive seeking company adoption</option></>}
            {!collegeOrganizer && <><option value="company_off_campus">Company off-campus drive</option><option value="company_hosted">Company drive hosted at a college</option>{(user?.roles || []).some((role) => ["company_admin", "super_admin"].includes(role)) && <><option value="joint">Jointly organized drive</option><option value="multi_college">Multi-college pooled drive</option></>}</>}
          </select></Field>
          <p className="text-xs text-slate-500">Recruiting decisions remain with the company. Colleges only receive the coordination access assigned to them.</p>
          {(!collegeOrganizer || form.drive_type === "college_adopted") && <Field label="Recruiting company name"><Input required={!collegeOrganizer || form.drive_type === "college_adopted"} value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} placeholder="Company name" /></Field>}
          {collegeOrganizer && <Field label={form.drive_type === "college_adopted" ? "Company to invite as adopter (tenant ID)" : "Recruiting company tenant IDs (comma-separated)"}><Input required={form.drive_type === "college_adopted"} value={form.company_ids} onChange={(e) => setForm({ ...form, company_ids: e.target.value })} placeholder="company-tenant-id" /></Field>}
          <Field label="Drive title"><Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="SWE Intern Drive 2027" /></Field>
          {(form.drive_type === "company_hosted" || form.drive_type === "joint" || form.drive_type === "multi_college") && <Field label="Host college ID"><Input required={form.drive_type === "company_hosted"} value={form.host_college_id} onChange={(e) => setForm({ ...form, host_college_id: e.target.value })} placeholder="College ID" /></Field>}
          {(form.drive_type === "joint" || form.drive_type === "multi_college") && <Field label="Participating college IDs (comma-separated)"><Input required value={form.college_ids} onChange={(e) => setForm({ ...form, college_ids: e.target.value })} placeholder="college-id-1, college-id-2" /></Field>}
          {collegeOrganizer && <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={form.nomination_required} onChange={(e) => setForm({ ...form, nomination_required: e.target.checked })} /> Require college nomination instead of direct applications</label>}
          {collegeOrganizer && form.drive_type === "college_hosted" && <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={form.company_confirmation_required} onChange={(e) => setForm({ ...form, company_confirmation_required: e.target.checked })} /> Require a recruiting company to accept before publishing</label>}
          {!collegeOrganizer && ["joint", "multi_college"].includes(form.drive_type) && form.host_college_id && <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={form.host_confirmation_required} onChange={(e) => setForm({ ...form, host_confirmation_required: e.target.checked })} /> Require the host college to accept before publishing</label>}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Venue"><Input value={form.venue} onChange={(e) => setForm({ ...form, venue: e.target.value })} placeholder="Aditya College" /></Field>
            <Field label="Reporting time"><Input value={form.reporting_time} onChange={(e) => setForm({ ...form, reporting_time: e.target.value })} placeholder="9:00 AM" /></Field>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create drive"}</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
