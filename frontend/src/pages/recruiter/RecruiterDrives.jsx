import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Building2, MapPin, Clock, ChevronRight, X, Trash2, Search, Command, Rocket, Trophy, GitBranch } from "lucide-react";
import { Card, Button, Field, Input } from "../../components/ui/primitives.jsx";
import { PageHeader, Loading } from "../../components/ui/states.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { api, withFallback } from "../../lib/api.js";
import { ReadOut, Attention, bandHex } from "../../components/drive/grammar.jsx";
import CommandPalette from "../../components/drive/CommandPalette.jsx";
import { TiltCard } from "../../components/ui/Decor.jsx";
import "../../styles/recruiter-operations-pages.css";

/* Cross-drive Command Center — the operating console across every drive.
   Real data: api.drives() + api.funnel(id) per drive. */
export default function RecruiterDrives() {
  const drivesA = useAsync(() => withFallback(api.drives(), []), []);
  const [creating, setCreating] = useState(false);
  const [extra, setExtra] = useState([]);
  const [removed, setRemoved] = useState(() => new Set());
  const [q, setQ] = useState("");
  const [statusF, setStatusF] = useState("all");
  const [actionError, setActionError] = useState("");
  const [funnels, setFunnels] = useState({}); // driveId -> {total,by_status}

  const all = [...(drivesA.data || []), ...extra].filter((d) => !removed.has(d.id));

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
        <Button onClick={() => setCreating(true)}><Plus size={18} /> New drive</Button>
      </header>

      <section className="hire-portfolio-strip" aria-label="Portfolio activity">
        <ReadOut label="Open drives" value={openDrives} hint={`${all.length} total`} />
        <ReadOut label="Candidate pool" value={totalPool} hint={poolHint} />
        <ReadOut label="In flight" value={totalFlight} hint="shortlisted + in-round" />
        <ReadOut label="Selected" value={totalSelected} hint="ready for offer" />
      </section>

      {actionError && <p role="alert" className="hire-drive-error">{actionError}</p>}
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

      {creating && <CreateDrive onClose={() => setCreating(false)} onCreated={(d) => { setExtra((e) => [...e, d]); setCreating(false); }} />}
    </div></main>
  );

  async function del(d) {
    setActionError("");
    if (!window.confirm(`Delete "${d.title}"? This permanently removes the drive and all its rounds, marks, registrations, and results.`)) return;
    try { await api.deleteDrive(d.id); } catch (error) { setActionError(error?.message || `Could not delete "${d.title}".`); return; }
    setRemoved((r) => new Set(r).add(d.id));
  }
}

function CreateDrive({ onClose, onCreated }) {
  const [form, setForm] = useState({ company_name: "", title: "", venue: "", reporting_time: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const body = { company_id: form.company_name.toLowerCase().replace(/\s+/g, "-"), ...form };
    try { const created = await api.createDrive(body); onCreated(created); }
    catch (e) { setError(e?.message || "The drive could not be created. Please try again."); }
    finally { setBusy(false); }
  }
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-invert-950/40 p-4" onClick={onClose}>
      <Card role="dialog" aria-modal="true" aria-labelledby="create-drive-title" className="w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 id="create-drive-title" className="font-display text-lg font-bold text-ink-900">New recruitment drive</h2>
          <button onClick={onClose} className="grid place-items-center h-9 w-9 rounded-md hover:bg-slate-100"><X size={18} /></button>
        </div>
        {error && <p role="alert" className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{error}</p>}
        <form onSubmit={submit} className="space-y-4">
          <Field label="Company name"><Input required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} placeholder="GenZify" /></Field>
          <Field label="Drive title"><Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="SWE Intern Drive 2027" /></Field>
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
