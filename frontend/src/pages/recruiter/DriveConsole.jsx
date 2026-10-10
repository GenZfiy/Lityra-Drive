import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft, Briefcase, Users, SlidersHorizontal, Rocket,
  Plus, Check, ChevronRight, Award, BarChart3, Trophy, MessagesSquare,
  ChevronUp, ChevronDown, Trash2, CheckCircle2, Search, Command, GitBranch,
  Gauge, Calendar, ShieldAlert, X, Compass, Target, Eye, ClipboardList, Star, Send, Scale,
  FileSearch, ShieldCheck,
} from "lucide-react";
import { Card, Badge, Button, Field, Input } from "../../components/ui/primitives.jsx";
import { Loading } from "../../components/ui/states.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { api, withFallback, sseStream } from "../../lib/api.js";
import ResultsTab from "./ResultsTab.jsx";
import InterviewsTab from "./InterviewsTab.jsx";
import RoundsTab from "./RoundsTab.jsx";
import AnalyticsTab from "./AnalyticsTab.jsx";
import { ReadOut, Ribbon, Attention, AIObservation, SignalCard, band, bandHex, initials, hueFor } from "../../components/drive/grammar.jsx";
import CommandPalette from "../../components/drive/CommandPalette.jsx";
import "../../styles/recruiter-operations-pages.css";

/* The Drive as the operating unit. Surfaces are framed around
   State → Context → Evidence → Action, all on the existing real APIs. */
const TAB_DEFS = {
  command: { label: "Command Center", icon: Command },
  workspace: { label: "Workspace", icon: ClipboardList },
  pipeline: { label: "Pipeline", icon: GitBranch },
  candidates: { label: "Candidates", icon: Users },
  interviews: { label: "Interviews", icon: MessagesSquare },
  rounds: { label: "Rounds & Marks", icon: CheckCircle2 },
  evidence: { label: "Evidence", icon: FileSearch },
  decisions: { label: "Decisions", icon: Trophy },
  analytics: { label: "Analytics", icon: BarChart3 },
  configure: { label: "Configure", icon: SlidersHorizontal },
};

// The backend's real Drive roles are recruiter / company_admin / super_admin.
// Hiring-Manager / Interviewer / Leadership are honest PERSPECTIVE LENSES over
// the same real data — they reshape the operating surface, not permissions.
const LENSES = {
  recruiter: { label: "Recruiter", home: "command", tabs: ["command", "pipeline", "candidates", "interviews", "rounds", "evidence", "decisions", "analytics", "configure"] },
  manager: { label: "Hiring Manager", home: "candidates", tabs: ["candidates", "evidence", "decisions", "analytics", "command"] },
  interviewer: { label: "Interviewer", home: "workspace", tabs: ["workspace", "candidates", "interviews"] },
  leadership: { label: "Leadership", home: "analytics", tabs: ["analytics", "command", "pipeline"] },
};

export default function DriveConsole() {
  const { id } = useParams();
  const detail = useAsync(() => withFallback(api.drive(id), {}), [id]);
  const [tab, setTab] = useState("command");
  const [drive, setDrive] = useState(null);
  const [lens, setLens] = useState("recruiter");
  const [driveError, setDriveError] = useState("");

  if (detail.loading) return <Loading />;
  const d = drive || detail.data || {};
  const rounds = (d.rounds || []).length;
  const lensDef = LENSES[lens] || LENSES.recruiter;
  const visibleTabs = lensDef.tabs;
  const activeTab = visibleTabs.includes(tab) ? tab : lensDef.home;
  const pickLens = (l) => { setLens(l); setTab(LENSES[l].home); };
  async function openDrive() {
    setDriveError("");
    try { await api.openDrive(id); setDrive({ ...d, status: "open" }); }
    catch (error) { setDriveError(error?.message || "This drive could not be opened."); }
  }

  return (
    <main className="page-composition page-composition-recruiter hire-ops hire-ops--console"><div>
      <CommandPalette />
      <Link to="/drive/recruiter/drives" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink-900 mb-3">
        <ArrowLeft size={16} /> All drives
      </Link>

      {/* Mission header — the drive as an operating unit */}
      <header className="hire-console-hero relative overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-brand-500/[0.04] via-surface to-surface p-5 mb-5">
        <div aria-hidden className="absolute -top-16 -right-12 h-44 w-44 rounded-full bg-brand-500/10 blur-3xl pointer-events-none" />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
              <Target size={13} aria-hidden="true" /> <span>Lityra Hire · Hiring mission · {d.company_name || "—"}</span>
            </div>
            <h1 className="mt-1.5 font-display text-2xl font-bold tracking-tight text-ink-900">{d.title || "Drive"}</h1>
            <p className="mt-2 max-w-3xl text-[12.5px] leading-relaxed text-slate-500">Coordinate candidate movement, evaluation evidence, and hiring decisions in one drive workspace.</p>
            <dl className="hire-console-facts mt-3">
              <div><dt>Roles</dt><dd>{(d.roles || []).length}</dd></div>
              <div><dt>Rounds</dt><dd>{rounds}</dd></div>
              <div className="hire-console-flow"><dt>Operating flow</dt><dd>Intent <span aria-hidden="true">→</span> evidence <span aria-hidden="true">→</span> decision <span aria-hidden="true">→</span> outcome</dd></div>
            </dl>
          </div>
          <div className="hire-console-controls flex items-center gap-3 shrink-0">
            <label className="flex items-center gap-2 h-9 px-3 rounded-lg border border-slate-200 bg-surface text-[12.5px]" title="Reshape the console for a persona (a view lens, not a permission change)">
              <Eye size={14} className="text-slate-400" />
              <span className="text-slate-400">View as</span>
              <select value={lens} onChange={(e) => pickLens(e.target.value)} className="bg-transparent font-semibold text-ink-900 outline-none">
                {Object.entries(LENSES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
            </label>
            <Badge tone={d.status === "open" ? "teal" : "slate"}>{d.status || "draft"}</Badge>
            {d.status !== "open" && (
              <Button onClick={openDrive}>
                <Rocket size={17} /> Open drive
              </Button>
            )}
          </div>
        </div>
      </header>
      {driveError && <p role="alert" className="hire-drive-error">{driveError}</p>}

      {/* Operating tabs — shaped by the active lens */}
      <nav aria-label="Drive workspace sections" className="flex gap-1 border-b border-slate-200 mb-6 overflow-x-auto">
        {visibleTabs.map((tid) => {
          const t = TAB_DEFS[tid]; const Ic = t.icon;
          return (
            <button key={tid} type="button" aria-current={activeTab === tid ? "page" : undefined} onClick={() => setTab(tid)}
              className={`flex items-center gap-2 px-4 h-11 text-sm font-medium border-b-2 -mb-px whitespace-nowrap ${activeTab === tid ? "border-brand-500 text-brand-600" : "border-transparent text-slate-500 hover:text-ink-900"}`}>
              <Ic size={16} /> {t.label}
            </button>
          );
        })}
      </nav>

      {activeTab === "command" && <CommandCenter d={d} id={id} rounds={rounds} go={setTab} />}
      {activeTab === "workspace" && <InterviewerWorkspace d={d} id={id} rounds={rounds} />}
      {activeTab === "pipeline" && <PipelineView d={d} id={id} rounds={rounds} go={setTab} />}
      {activeTab === "candidates" && <CandidateIntelligence d={d} id={id} rounds={rounds} />}
      {activeTab === "interviews" && <InterviewsTab id={id} />}
      {activeTab === "rounds" && <RoundsTab id={id} />}
      {activeTab === "evidence" && <EvidenceLedger id={id} />}
      {activeTab === "decisions" && <DecisionsView id={id} />}
      {activeTab === "analytics" && <AnalyticsTab id={id} />}
      {activeTab === "configure" && <ConfigureView d={d} id={id} onChange={setDrive} />}
    </div></main>
  );
}

/* ---------- derivations from real data (no fabrication) ---------- */
function readiness(r, rounds) {
  if (r.eligible === "no") return 8;
  if (r.status === "selected") return 96;
  if (r.status === "rejected") return 12;
  // Prefer the candidate's REAL performance (avg % across their round marks) when
  // it exists — that differentiates candidates by how they actually did.
  if (r.score != null) return Math.max(0, Math.min(100, Math.round(r.score)));
  // Fallback (no marks recorded yet): a coarse pipeline-stage heuristic.
  let v = 42;
  v += rounds > 0 ? Math.round(((r.current_round || 0) / rounds) * 34) : 0;
  v += r.status === "in_round" ? 12 : r.status === "shortlisted" ? 6 : 0;
  if (r.eligible === "yes") v += 8;
  return Math.max(0, Math.min(100, v));
}
function stageBuckets(d, regs) {
  const rounds = d.rounds || [];
  const active = regs.filter((r) => r.status !== "rejected");
  const stages = [{ key: "pool", label: "Registered", count: regs.length, meta: `${regs.filter((r) => r.eligible === "no").length} ineligible`, health: regs.length ? "neutral" : "neutral" }];
  rounds.forEach((rd, i) => {
    const count = active.filter((r) => (r.current_round || 0) === rd.order && r.status !== "selected").length;
    stages.push({ key: "r" + rd.order, label: rd.label || rd.type || `Round ${rd.order}`, count, meta: rd.type || "", order: rd.order });
  });
  const sel = regs.filter((r) => r.status === "selected").length;
  stages.push({ key: "selected", label: "Selected", count: sel, meta: "ready for offer", health: sel ? "good" : "neutral" });
  // bottleneck = round stage with max occupancy
  const mid = stages.filter((s) => s.key.startsWith("r"));
  const maxC = Math.max(0, ...mid.map((s) => s.count));
  mid.forEach((s) => { s.health = s.count === 0 ? "neutral" : s.count === maxC && maxC > 1 ? "warn" : "good"; if (s.count === maxC && maxC > 1) { s.bottleneck = true; s.meta = "largest hold"; } });
  return stages;
}

function CommandCenter({ d, id, rounds, go }) {
  // Live tick — refreshes the funnel + intelligence every 25s without a full
  // reload (useAsync keeps prior data during refetch, so no flicker). A true
  // bus-backed SSE stream is the future upgrade (see architecture §15).
  const [tick, setTick] = useState(0);
  useEffect(() => { const t = setInterval(() => setTick((v) => v + 1), 25000); return () => clearInterval(t); }, []);

  const funnel = useAsync(() => withFallback(api.funnel(id), { total: 0, by_status: {} }), [id, tick]);
  const regsA = useAsync(() => withFallback(api.driveRegistrations(id), []), [id, tick]);
  const ivA = useAsync(() => withFallback(api.driveInterviews(id), []), [id]);
  // Drive-OS intelligence (evidence-backed). Non-blocking: the console renders
  // even if these peers are slow/unavailable, and falls back to derived signals.
  const insightsA = useAsync(() => withFallback(api.driveInsights(id), []), [id, tick]);
  const actionsA = useAsync(() => withFallback(api.driveActions(id), []), [id, tick]);
  // Live push of the attention queue via SSE (bounded ~60s server-side, so we
  // reconnect). Falls back to actionsA (the poll) when the stream is unavailable.
  const [liveActions, setLiveActions] = useState(null);
  useEffect(() => {
    let stop = sseStream(`/drive/v1/actions/drive/${id}/stream`, setLiveActions);
    const reconnect = setInterval(() => { stop(); stop = sseStream(`/drive/v1/actions/drive/${id}/stream`, setLiveActions); }, 62000);
    return () => { stop(); clearInterval(reconnect); };
  }, [id]);
  if ((funnel.loading && !funnel.data) || (regsA.loading && !regsA.data)) return <Loading />;

  const f = funnel.data || { total: 0, by_status: {} };
  const regs = regsA.data || [];
  const ivs = ivA.data || [];
  const inFlight = (f.by_status?.shortlisted || 0) + (f.by_status?.in_round || 0);
  const selected = f.by_status?.selected || 0;
  const total = f.total || regs.length;
  const conv = total ? Math.round((selected / total) * 100) : 0;
  const ineligible = regs.filter((r) => r.eligible === "no").length;
  const scheduled = ivs.filter((v) => v.status === "scheduled").length;
  const awaiting = regs.filter((r) => r.status === "in_round" && (r.current_round || 0) < rounds).length;
  const stages = stageBuckets(d, regs);
  const bottleneck = stages.find((s) => s.bottleneck);

  // Action intelligence — derived from real state, ranked by impact
  const actions = [];
  if (scheduled > 0) actions.push({ priority: "high", tone: "warn", icon: Calendar, title: `${scheduled} interview${scheduled > 1 ? "s" : ""} scheduled to run`, detail: "Feedback drives decisions — run and capture these to unblock movement.", actions: [{ label: "Open interviews", primary: true, onClick: () => go("interviews") }] });
  if (bottleneck) actions.push({ priority: "high", tone: "warn", icon: GitBranch, title: `${bottleneck.label} holds the largest concentration (${bottleneck.count})`, detail: "This stage is throttling downstream flow. Add evaluation capacity or advance cleared candidates.", actions: [{ label: "View pipeline", primary: true, onClick: () => go("pipeline") }] });
  if (awaiting > 0) actions.push({ priority: "medium", tone: "brand", icon: ChevronRight, title: `${awaiting} candidate${awaiting > 1 ? "s are" : " is"} mid-pipeline`, detail: "In an active round and eligible to progress once evaluated.", actions: [{ label: "Open candidates", primary: true, onClick: () => go("candidates") }] });
  if (selected > 0) actions.push({ priority: "medium", tone: "teal", icon: Trophy, title: `${selected} candidate${selected > 1 ? "s" : ""} selected`, detail: "Compile results and generate offers to close the loop.", actions: [{ label: "Go to decisions", primary: true, onClick: () => go("decisions") }] });
  if (ineligible > 0) actions.push({ priority: "medium", tone: "risk", icon: ShieldAlert, title: `${ineligible} registration${ineligible > 1 ? "s are" : " is"} ineligible`, detail: "Screened out under the current eligibility criteria.", actions: [{ label: "Review criteria", onClick: () => go("configure") }] });

  // Derived observations (deterministic, labelled)
  const obs = [];
  if (bottleneck) obs.push({ severity: "warn", title: `${bottleneck.label} is the current bottleneck`, observation: `${bottleneck.count} candidates are concentrated in this stage — the largest of any active round.`, reason: "Occupancy here exceeds every other round; downstream stages are starved until it clears.", impact: "Time-to-offer will slip unless evaluation capacity is added or cleared candidates advance.", action: { label: "Open pipeline", onClick: () => go("pipeline") } });
  obs.push({ severity: conv >= 15 ? "teal" : "brand", title: `Conversion is ${conv}% of the pool`, observation: `${selected} selected out of ${total} registered; ${inFlight} still in flight.`, reason: "Derived from the live funnel across all rounds of this drive.", impact: conv < 10 ? "Low conversion this early is expected; watch it as candidates clear later rounds." : "Healthy conversion — prioritise closing selected candidates before competing offers land.", action: { label: "Go to decisions", onClick: () => go("decisions") } });

  const top = [...regs].filter((r) => r.status !== "rejected").sort((a, b) => readiness(b, rounds) - readiness(a, rounds)).slice(0, 4);

  // Evidence-backed intelligence from the Drive-OS services (action + recruit-ai).
  // When present it leads; the funnel-derived signals above always remain as a floor.
  const TARGET = { calibration: "decisions" };
  const ACT_ICON = { evidence_conflict: ShieldAlert, panel_divergent: GitBranch, ready_decision: Trophy, coverage_gap: FileSearch };
  const ACT_JUMP = { evidence_conflict: "evidence", panel_divergent: "candidates", ready_decision: "decisions", coverage_gap: "candidates" };
  const realActions = ((liveActions ?? actionsA.data) || []).map((a) => ({
    priority: a.priority, tone: a.priority === "high" ? "warn" : a.kind === "ready_decision" ? "teal" : "brand",
    icon: ACT_ICON[a.kind] || Command, title: a.title, detail: a.detail,
    actions: [{ label: "Open", primary: true, onClick: () => go(ACT_JUMP[a.kind] || "candidates") }],
  }));
  const realObs = (insightsA.data || []).map((i) => ({
    severity: i.severity, title: i.title, observation: i.observation, reason: i.reason, impact: i.impact,
    action: i.recommended_action?.target ? { label: i.recommended_action.label, onClick: () => go(TARGET[i.recommended_action.target] || i.recommended_action.target) } : undefined,
  }));
  const mergedActions = [...realActions, ...actions];
  const observations = realObs.length ? realObs : obs;

  return (
    <div className="hire-console-command">
      <div className="flex items-center justify-end mb-2">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-400"><span className="h-1.5 w-1.5 rounded-full bg-teal-500 animate-pulse" /> {liveActions ? "Live · streaming" : "Live · auto-refreshing"}</span>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <ReadOut label="Candidate pool" value={total} hint={`${ineligible} ineligible`} />
        <ReadOut label="In flight" value={inFlight} hint="shortlisted + in-round" />
        <ReadOut label="Selected" value={selected} hint="ready for offer" />
        <ReadOut label="Conversion" value={conv} unit="%" hint="selected / pool" />
      </div>

      <div className="rounded-2xl border border-slate-200 bg-surface mb-4">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <h3 className="text-[13.5px] font-semibold text-ink-900 flex items-center gap-2"><GitBranch size={16} className="text-slate-400" /> Pipeline Ribbon — live drive state</h3>
          <span className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">click a stage to focus</span>
        </div>
        <div className="p-4"><Ribbon stages={stages} onSelect={() => go("pipeline")} /></div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 grid gap-4">
          <div className="rounded-2xl border border-slate-200 bg-surface overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
              <h3 className="text-[13.5px] font-semibold text-ink-900 flex items-center gap-2"><Command size={16} className="text-slate-400" /> Needs attention</h3>
              <span className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">{realActions.length ? "evidence-backed + derived" : "ranked by impact"}</span>
            </div>
            <Attention items={mergedActions} />
          </div>
          <div className="rounded-2xl border border-slate-200 bg-surface overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100"><h3 className="text-[13.5px] font-semibold text-ink-900 flex items-center gap-2"><Compass size={16} className="text-slate-400" /> {realObs.length ? "Evidence-backed insights" : "Drive observations"}</h3></div>
            <div className="p-4 grid gap-3">{observations.map((o, i) => <AIObservation key={i} {...o} />)}</div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-surface overflow-hidden h-fit">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <h3 className="text-[13.5px] font-semibold text-ink-900 flex items-center gap-2"><Gauge size={16} className="text-slate-400" /> Most decision-ready</h3>
            <button className="text-[11.5px] text-brand-600 font-medium" onClick={() => go("candidates")}>All</button>
          </div>
          <div className="p-3 grid gap-2">
            {top.length === 0 ? <div className="p-4 text-sm text-slate-400 text-center">No candidates yet.</div> :
              top.map((r) => {
                const nm = r.candidate_name || r.candidate_email || r.candidate_id;
                return (
                  <div key={r.candidate_id} className="flex items-center gap-3 rounded-xl border border-slate-100 p-2.5">
                    <span className="grid place-items-center h-9 w-9 rounded-lg text-white text-[12px] font-bold shrink-0" style={{ background: hueFor(nm) }}>{initials(nm)}</span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[12.5px] font-medium text-ink-900 truncate">{nm}</div>
                      <div className="text-[11px] text-slate-400 capitalize">{(r.status || "").replace("_", " ")}{r.current_round ? ` · round ${r.current_round}/${rounds}` : ""}</div>
                    </div>
                    <div className="text-right shrink-0"><div className="font-display text-[16px] font-bold leading-none tabular-nums" style={{ color: bandHex(band(readiness(r, rounds))) }}>{readiness(r, rounds)}</div><div className="text-[8.5px] uppercase tracking-wider text-slate-400">ready</div></div>
                  </div>
                );
              })}
          </div>
        </div>
      </div>
    </div>
  );
}

function PipelineView({ d, id, rounds, go }) {
  const regsA = useAsync(() => withFallback(api.driveRegistrations(id), []), [id]);
  const anA = useAsync(() => withFallback(api.driveAnalytics(id), {}), [id]);
  const [sel, setSel] = useState(null);
  if (regsA.loading) return <Loading />;
  const regs = regsA.data || [];
  const stages = stageBuckets(d, regs);
  const an = anA.data || {};
  const focus = sel ? regs.filter((r) => (sel === "selected" ? r.status === "selected" : sel === "pool" ? true : ("r" + (r.current_round || 0)) === sel)) : [];

  return (
    <section className="hire-console-pipeline" aria-label="Candidate pipeline">
      <div className="rounded-2xl border border-slate-200 bg-surface p-4 mb-4"><Ribbon stages={stages} selected={sel} onSelect={setSel} /></div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="p-5">
          <h3 className="font-display font-semibold text-ink-900 mb-3 flex items-center gap-2"><BarChart3 size={17} className="text-brand-500" /> Stage occupancy & flow</h3>
          <div className="space-y-2.5">
            {stages.map((s) => {
              const maxC = Math.max(1, ...stages.map((x) => x.count));
              return (
                <div key={s.key} className="grid grid-cols-[130px_1fr_36px] gap-3 items-center text-[12.5px]">
                  <div className="flex items-center gap-2 truncate"><span className="h-1.5 w-1.5 rounded-full" style={{ background: bandHex(s.health) }} />{s.label}</div>
                  <div className="h-5 rounded-md bg-slate-100 overflow-hidden"><span className="block h-full rounded-md" style={{ width: `${Math.round((s.count / maxC) * 100)}%`, background: s.bottleneck ? "#d97706" : "#4f46e5" }} /></div>
                  <div className="tabular-nums text-right text-slate-600">{s.count}</div>
                </div>
              );
            })}
          </div>
          {an?.written?.pass_rate != null && <p className="mt-4 text-[11.5px] text-slate-400">Written-round pass rate {an.written.pass_rate}% · avg {an.written.avg_percentage ?? 0}% (from analytics).</p>}
        </Card>
        <Card className="p-5">
          <h3 className="font-display font-semibold text-ink-900 mb-3 flex items-center gap-2"><Users size={17} className="text-brand-500" /> {sel ? `In "${stages.find((s) => s.key === sel)?.label}"` : "Select a stage"}</h3>
          {sel ? (
            focus.length ? <div className="space-y-2">{focus.slice(0, 12).map((r) => {
              const nm = r.candidate_name || r.candidate_email || r.candidate_id;
              return <div key={r.candidate_id} className="flex items-center gap-3 rounded-lg border border-slate-100 p-2.5"><span className="grid place-items-center h-8 w-8 rounded-lg text-white text-[11px] font-bold" style={{ background: hueFor(nm) }}>{initials(nm)}</span><span className="text-[12.5px] font-medium text-ink-900 truncate flex-1">{nm}</span><Badge tone={r.eligible === "yes" ? "teal" : "rose"}>{r.eligible}</Badge></div>;
            })}</div> : <p className="text-sm text-slate-400">No candidates in this stage.</p>
          ) : <p className="text-sm text-slate-400">Click a stage in the ribbon to see who’s there and why they’re held.</p>}
          <button className="mt-4 text-[12px] text-brand-600 font-medium" onClick={() => go("candidates")}>Open full candidate intelligence →</button>
        </Card>
      </div>
    </section>
  );
}

function CandidateIntelligence({ d, id, rounds }) {
  const regsA = useAsync(() => withFallback(api.driveRegistrations(id), []), [id]);
  // Evidence-backed decision confidence per candidate (from the decision queue).
  const queueA = useAsync(() => withFallback(api.decisionQueue(id), []), [id]);
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");
  const [statusF, setStatusF] = useState("all");
  const [open, setOpen] = useState(null);
  const [compareMode, setCompareMode] = useState(false);
  const [compare, setCompare] = useState([]);
  const [showCmp, setShowCmp] = useState(false);
  const [actionError, setActionError] = useState("");
  const list = rows ?? regsA.data ?? [];
  const qmap = Object.fromEntries((queueA.data || []).map((x) => [x.candidate_id, x]));
  // Rank by real evidence-backed confidence where it exists; else the readiness heuristic.
  const scoreOf = (r) => { const x = qmap[r.candidate_id]; return x && x.evidence_count > 0 ? Math.round(x.confidence || 0) : readiness(r, rounds); };

  if (regsA.loading) return <Loading />;
  const query = q.trim().toLowerCase();
  const filtered = list.filter((r) => {
    const mq = !query || [r.candidate_name, r.candidate_email, r.candidate_roll, r.candidate_id].some((v) => (v || "").toLowerCase().includes(query));
    const ms = statusF === "all" || r.status === statusF;
    return mq && ms;
  }).sort((a, b) => scoreOf(b) - scoreOf(a));
  const STATUSES = ["all", "applied", "shortlisted", "in_round", "selected", "rejected"];

  function update(cid, patch) { setRows((rows ?? regsA.data ?? []).map((r) => (r.candidate_id === cid ? { ...r, ...patch } : r))); }
  async function shortlist(cid) { setActionError(""); try { await api.shortlist(id, [cid]); update(cid, { status: "shortlisted", current_round: 1 }); return true; } catch (error) { setActionError(error?.message || "Candidate could not be shortlisted."); return false; } }
  async function advance(cid, cur) { setActionError(""); try { await api.advance(id, cid); const n = (cur || 0) + 1; update(cid, n > rounds ? { status: "selected" } : { status: "in_round", current_round: n }); return true; } catch (error) { setActionError(error?.message || "Candidate could not be advanced."); return false; } }

  const toggleCmp = (cid) => setCompare((c) => (c.includes(cid) ? c.filter((x) => x !== cid) : c.length >= 3 ? c : [...c, cid]));
  const cardClick = (r) => (compareMode ? toggleCmp(r.candidate_id) : setOpen(r));
  const selectedCands = list.filter((r) => compare.includes(r.candidate_id));

  return (
    <section className="hire-console-candidates" aria-label="Candidate intelligence">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="font-display text-lg font-semibold text-ink-900">Candidate Intelligence</h2>
          <p className="text-[12.5px] text-slate-500">Ranked by evidence‑backed decision confidence where evidence exists, else a readiness heuristic.{compareMode ? " Select up to 3 to compare." : ""}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => { setCompareMode((m) => !m); if (compareMode) setCompare([]); }}
            className={`h-9 px-3 rounded-lg border text-[12.5px] font-semibold inline-flex items-center gap-1.5 ${compareMode ? "border-brand-500 text-brand-600 bg-brand-500/5" : "border-slate-200 text-slate-600 hover:text-ink-900"}`}>
            <Scale size={14} /> {compareMode ? "Comparing" : "Compare"}
          </button>
          <div className="relative"><Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" /><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, email, roll…" className="h-9 pl-8 w-56" /></div>
          <select value={statusF} onChange={(e) => setStatusF(e.target.value)} className="h-9 px-2 rounded-md border border-slate-200 text-sm bg-surface capitalize">{STATUSES.map((s) => <option key={s} value={s}>{s === "all" ? "All statuses" : s.replace("_", " ")}</option>)}</select>
        </div>
      </div>
      {actionError && <p role="alert" className="hire-drive-error">{actionError}</p>}

      {filtered.length === 0 ? (
        <Card className="p-10 text-center text-slate-400">{list.length ? "No candidates match your search." : "No candidates have registered yet."}</Card>
      ) : (
        <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(300px,1fr))" }}>
          {filtered.map((r) => {
            const nm = r.candidate_name || r.candidate_email || r.candidate_id;
            const qr = qmap[r.candidate_id];
            const evb = qr && qr.evidence_count > 0;
            const ready = scoreOf(r);
            const riskTag = r.eligible === "no"
              ? <span className="inline-flex items-center gap-1 text-[10.5px] font-bold px-2 py-0.5 rounded bg-rose-500/10 text-rose-600"><ShieldAlert size={12} />Ineligible</span>
              : evb && qr.panel_agreement === "divergent" ? <span className="inline-flex items-center gap-1 text-[10.5px] font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-600"><GitBranch size={12} />Divergent</span>
              : r.status === "selected" ? <span className="inline-flex items-center gap-1 text-[10.5px] font-bold px-2 py-0.5 rounded bg-teal-500/10 text-teal-600"><Check size={12} />Selected</span>
                : <span className="text-[10.5px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-500 capitalize">{evb ? "evidence‑backed" : (r.status || "").replace("_", " ")}</span>;
            const next = compareMode ? (compare.includes(r.candidate_id) ? "Selected" : "Add to compare") : r.eligible === "no" ? "" : r.status === "applied" ? "Shortlist" : r.status === "selected" ? "" : "Advance";
            const baseSub = (r.candidate_roll ? `Roll ${r.candidate_roll} · ` : "") + (r.current_round ? `round ${r.current_round}/${rounds}` : "not started");
            const sub = evb ? `${baseSub} · ${qr.evidence_count} evidence${qr.coverage_pct != null ? ` · ${qr.coverage_pct}% cov` : ""}` : baseSub;
            return <SignalCard key={r.candidate_id} name={nm} sub={sub} confidence={ready} comps={[]} riskTag={riskTag} next={next} picked={compareMode && compare.includes(r.candidate_id)} onClick={() => cardClick(r)} />;
          })}
        </div>
      )}

      {open && !compareMode && <CandidateDrawer r={open} rounds={rounds} error={actionError} onClose={() => setOpen(null)} onShortlist={shortlist} onAdvance={advance} />}

      {compareMode && compare.length > 0 && (
        <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 rounded-full bg-invert-900 text-white px-4 py-2.5 shadow-xl">
          <span className="text-[12.5px]">{compare.length} selected</span>
          <button onClick={() => setShowCmp(true)} disabled={compare.length < 2} className="h-8 px-3 rounded-full bg-surface text-ink-900 text-[12px] font-semibold disabled:opacity-40">Compare {compare.length}</button>
          <button onClick={() => setCompare([])} aria-label="Clear comparison selection" className="text-white/70 hover:text-white"><X size={16} /></button>
        </div>
      )}
      {showCmp && <ComparePanel cands={selectedCands} rounds={rounds} onClose={() => setShowCmp(false)} />}
    </section>
  );
}

function CandidateDrawer({ r, rounds, error, onClose, onShortlist, onAdvance }) {
  const nm = r.candidate_name || r.candidate_email || r.candidate_id;
  const ready = readiness(r, rounds);
  const [ev, setEv] = useState({ loading: true, skills: [] });
  useEffect(() => {
    let alive = true;
    api.candidateSkills(r.candidate_id).then((res) => { if (alive) setEv({ loading: false, skills: res?.verified_skills || [] }); }).catch(() => { if (alive) setEv({ loading: false, skills: [] }); });
    return () => { alive = false; };
  }, [r.candidate_id]);

  const Mini = ({ l, v, tone }) => <div className="rounded-lg border border-slate-200 bg-surface p-2.5"><div className="text-[9.5px] font-bold uppercase tracking-wider text-slate-400">{l}</div><div className="mt-1 font-semibold text-[13px]" style={{ color: bandHex(tone) }}>{v}</div></div>;

  return (
    <>
      <div className="fixed inset-0 bg-invert-900/50 z-40" onClick={onClose} />
      <div className="fixed top-0 right-0 h-screen w-[520px] max-w-[94vw] bg-surface border-l border-slate-200 z-50 flex flex-col shadow-2xl">
        {error && <p role="alert" className="hire-drive-error mx-4 mt-4">{error}</p>}
        <div className="flex items-center gap-3 p-4 border-b border-slate-100">
          <span className="grid place-items-center h-11 w-11 rounded-xl text-white font-bold shrink-0" style={{ background: hueFor(nm) }}>{initials(nm)}</span>
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-ink-900 truncate">{nm}</div>
            <div className="text-[12px] text-slate-500 truncate">{r.candidate_email || ""}{r.candidate_roll ? ` · ${r.candidate_roll}` : ""}</div>
          </div>
          <div className="text-right mr-1"><div className="font-display text-[26px] font-bold leading-none tabular-nums" style={{ color: bandHex(band(ready)) }}>{ready}</div><div className="text-[9px] uppercase tracking-wider text-slate-400">readiness</div></div>
          <button onClick={onClose} aria-label="Close" className="grid place-items-center h-9 w-9 rounded-lg border border-slate-200 text-slate-400 hover:text-ink-900"><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <div className="mb-5">
            <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 mb-2">Should this candidate move forward?</div>
            <div className="grid grid-cols-3 gap-2.5">
              <Mini l="Eligibility" v={r.eligible === "yes" ? "Eligible" : r.eligible === "no" ? "Ineligible" : "Unknown"} tone={r.eligible === "yes" ? "good" : r.eligible === "no" ? "risk" : "neutral"} />
              <Mini l="Progression" v={r.current_round ? `Round ${r.current_round}/${rounds}` : "Not started"} tone={r.current_round ? "good" : "neutral"} />
              <Mini l="Status" v={(r.status || "").replace("_", " ")} tone={r.status === "selected" ? "good" : r.status === "rejected" ? "risk" : "neutral"} />
            </div>
          </div>

          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">Verified skill evidence</div>
              <span className="text-[10px] text-slate-400">from drive‑exam performance</span>
            </div>
            {ev.loading ? <div className="text-sm text-slate-400">Loading evidence…</div> :
              ev.skills.length ? (
                <div className="space-y-2">
                  {ev.skills.map((s, i) => (
                    <div key={i} className="flex items-center gap-3 rounded-lg border border-slate-100 p-2.5">
                      <span className="h-2 w-2 rounded-full" style={{ background: bandHex(s.level === "strong" ? "good" : s.level === "weak" ? "risk" : "warn") }} />
                      <div className="flex-1"><div className="text-[12.5px] font-semibold text-ink-900">{s.skill}</div><div className="text-[11px] text-slate-400">{s.evidence || "drive evaluation"}</div></div>
                      <Badge tone={s.level === "strong" ? "teal" : s.level === "weak" ? "rose" : "amber"}>{s.level || "—"}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-slate-200 p-4 text-center text-[12.5px] text-slate-400">
                  No evaluation evidence captured yet. Evidence appears as this candidate completes proctored rounds.
                </div>
              )}
          </div>

          <div>
            <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 mb-2">Next action</div>
            <div className="flex gap-2">
              {r.eligible === "no" ? <div className="text-sm text-slate-400">Ineligible under current criteria.</div>
                : r.status === "applied" ? <Button className="flex-1 justify-center" onClick={async () => { if (await onShortlist(r.candidate_id)) onClose(); }}>Shortlist candidate</Button>
                  : r.status === "selected" ? <Badge tone="teal"><Check size={13} /> Selected — proceed to offer</Badge>
                    : <Button className="flex-1 justify-center" onClick={async () => { if (await onAdvance(r.candidate_id, r.current_round)) onClose(); }}>Advance a round <ChevronRight size={15} /></Button>}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ---------- Candidate Comparison (derived from live data) ---------- */
function CmpRow({ l, v, tone }) {
  return <div className="flex items-center justify-between text-[12px]"><span className="text-slate-500">{l}</span><span className="font-medium" style={{ color: tone ? bandHex(tone) : "rgb(var(--c-ink-900))" }}>{v}</span></div>;
}
function ComparePanel({ cands, rounds, onClose }) {
  const [ev, setEv] = useState({});
  useEffect(() => {
    let a = true;
    Promise.all(cands.map(async (c) => [c.candidate_id, await api.candidateSkills(c.candidate_id).catch(() => ({ verified_skills: [] }))]))
      .then((e) => { if (a) setEv(Object.fromEntries(e)); });
    return () => { a = false; };
  }, [cands.map((c) => c.candidate_id).join(",")]);
  return (
    <div className="fixed inset-0 z-50 bg-invert-900/50 grid place-items-center p-4" onClick={onClose}>
      <Card className="w-full max-w-4xl max-h-[86vh] overflow-y-auto p-0" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h2 className="font-display font-semibold text-ink-900 flex items-center gap-2"><Scale size={18} className="text-brand-500" /> Candidate comparison</h2>
          <button onClick={onClose} aria-label="Close" className="grid place-items-center h-9 w-9 rounded-lg border border-slate-200 text-slate-400 hover:text-ink-900"><X size={18} /></button>
        </div>
        <div className="p-5 grid gap-4" style={{ gridTemplateColumns: `repeat(${cands.length},minmax(0,1fr))` }}>
          {cands.map((c) => {
            const nm = c.candidate_name || c.candidate_email || c.candidate_id;
            const ready = readiness(c, rounds);
            const sk = ev[c.candidate_id]?.verified_skills || [];
            return (
              <div key={c.candidate_id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-center gap-2.5">
                  <span className="grid place-items-center h-10 w-10 rounded-xl text-white font-bold" style={{ background: hueFor(nm) }}>{initials(nm)}</span>
                  <div className="min-w-0"><div className="font-semibold text-ink-900 truncate">{nm}</div><div className="text-[11px] text-slate-400 capitalize">{(c.status || "").replace("_", " ")}</div></div>
                </div>
                <div className="mt-3 text-center rounded-lg bg-slate-50 p-3"><div className="font-display text-2xl font-bold tabular-nums" style={{ color: bandHex(band(ready)) }}>{ready}</div><div className="text-[9.5px] uppercase tracking-wider text-slate-400">readiness</div></div>
                <div className="mt-3 space-y-1.5">
                  <CmpRow l="Eligibility" v={c.eligible === "yes" ? "Eligible" : c.eligible === "no" ? "Ineligible" : "—"} tone={c.eligible === "yes" ? "good" : c.eligible === "no" ? "risk" : "neutral"} />
                  <CmpRow l="Progress" v={c.current_round ? `Round ${c.current_round}/${rounds}` : "Not started"} />
                  <CmpRow l="Verified skills" v={String(sk.length)} tone={sk.length ? "good" : "neutral"} />
                </div>
                {sk.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{sk.slice(0, 6).map((s, i) => <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-teal-500/10 text-teal-700">{s.skill}</span>)}</div>}
              </div>
            );
          })}
        </div>
        <div className="p-4 border-t border-slate-100 text-[11.5px] text-slate-400">Comparison uses live registration + evaluation‑twin data. Deeper per‑competency evidence needs the evidence service (Phase 4).</div>
      </Card>
    </div>
  );
}

/* ---------- Decision Intelligence (evidence-backed queue + offers) ---------- */
function DecisionsView({ id }) {
  const qA = useAsync(() => withFallback(api.decisionQueue(id), []), [id]);
  const regsA = useAsync(() => withFallback(api.driveRegistrations(id), []), [id]);
  const [decided, setDecided] = useState({});
  const [actionError, setActionError] = useState("");
  const queue = (qA.data || []).filter((x) => !x.decision && !decided[x.candidate_id]);
  const nameOf = (cid) => { const r = (regsA.data || []).find((x) => x.candidate_id === cid); return r?.candidate_name || r?.candidate_email || cid; };

  async function decide(cid, verdict) {
    setActionError("");
    try { await api.recordDecision({ drive_id: id, candidate_id: cid, verdict }); setDecided((d) => ({ ...d, [cid]: verdict })); }
    catch (error) { setActionError(error?.message || "This decision could not be recorded."); }
  }

  return (
    <div className="grid gap-6">
      <div>
        <div className="mb-3">
          <h2 className="font-display text-lg font-semibold text-ink-900">Decision Intelligence</h2>
          <p className="text-[12.5px] text-slate-500">Finalists ranked by evidence‑backed decision confidence — coverage, panel agreement, and what's missing. Recording a decision cites the exact evidence (immutable lineage).</p>
        </div>
        {actionError && <p role="alert" className="hire-drive-error">{actionError}</p>}
        {qA.loading ? <Loading /> : queue.length === 0 ? (
          <Card className="p-8 text-center text-slate-400">No candidates are decision‑ready yet. Confidence accrues as evidence lands from assessments and interviews.</Card>
        ) : (
          <div className="grid gap-2">
            {queue.map((q) => (
              <div key={q.candidate_id} className="rounded-2xl border border-slate-200 bg-surface p-4 flex flex-wrap items-center gap-4">
                <span className="grid place-items-center h-11 w-11 rounded-xl text-white font-bold shrink-0" style={{ background: hueFor(nameOf(q.candidate_id)) }}>{initials(nameOf(q.candidate_id))}</span>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-ink-900 truncate">{nameOf(q.candidate_id)}</div>
                  <div className="text-[11.5px] text-slate-500 flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5">
                    {q.coverage_pct != null && <span>Coverage {q.coverage_pct}%</span>}
                    <span>Agreement <b className="capitalize">{q.panel_agreement}</b></span>
                    <span>{q.evidence_count} evidence</span>
                    {q.missing_competencies?.length > 0 && <span className="text-amber-600">Missing: {q.missing_competencies.join(", ")}</span>}
                  </div>
                </div>
                <div className="text-center px-2 shrink-0">
                  <div className="font-display text-2xl font-bold tabular-nums" style={{ color: bandHex(band(q.confidence || 0)) }}>{Math.round(q.confidence || 0)}</div>
                  <div className="text-[9px] uppercase tracking-wider text-slate-400">confidence</div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button size="sm" variant="secondary" onClick={() => decide(q.candidate_id, "reject")}><X size={14} /> Reject</Button>
                  <Button size="sm" variant="ghost" onClick={() => decide(q.candidate_id, "hold")}>Hold</Button>
                  <Button size="sm" onClick={() => decide(q.candidate_id, "advance")}><Check size={14} /> Advance</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <CalibrationPanel id={id} />
      <div>
        <div className="mb-3"><h2 className="font-display text-lg font-semibold text-ink-900">Results &amp; Offers</h2></div>
        <ResultsTab id={id} />
      </div>
    </div>
  );
}

/* ---------- Interviewer calibration (drift vs consensus — recruit-ai) ---------- */
function CalibrationPanel({ id }) {
  const [scope, setScope] = useState("drive");
  const driveA = useAsync(() => withFallback(api.driveCalibration(id), []), [id]);
  const crossA = useAsync(() => withFallback(api.crossCalibration(), []), []);
  const loading = scope === "drive" ? driveA.loading : crossA.loading;
  const rows = (scope === "drive" ? driveA.data : crossA.data) || [];
  if (loading && !(driveA.data || crossA.data)) return null;
  if (!(driveA.data || []).length && !(crossA.data || []).length) return null;
  return (
    <section className="hire-console-decisions" aria-label="Hiring decisions and results">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-display font-semibold text-ink-900 flex items-center gap-2"><Gauge size={17} className="text-slate-400" /> Interviewer calibration</h3>
          <p className="text-[12.5px] text-slate-500">How far each interviewer scores from the consensus, per competency. Large drift signals a calibration gap to address.</p>
        </div>
        <div className="flex rounded-lg border border-slate-200 overflow-hidden text-[11.5px] font-semibold">
          {[["drive", "This drive"], ["all", "All drives"]].map(([k, label]) => (
            <button key={k} onClick={() => setScope(k)} className={`h-8 px-3 ${scope === k ? "bg-invert-900 text-white" : "bg-surface text-slate-500 hover:text-ink-900"}`}>{label}</button>
          ))}
        </div>
      </div>
      {rows.length === 0 && <Card className="p-6 text-center text-[12.5px] text-slate-400">No calibration data {scope === "all" ? "across drives" : "for this drive"} yet.</Card>}
      <div className="rounded-2xl border border-slate-200 bg-surface overflow-hidden">
        {rows.map((c, i) => {
          const d = c.mean_delta || 0;
          const tone = Math.abs(d) < 8 ? "teal" : Math.abs(d) < 18 ? "amber" : "rose";
          const toneHex = { teal: "#0d9488", amber: "#d97706", rose: "#e11d48" }[tone];
          return (
            <div key={i} className="flex items-center gap-3 px-4 py-2.5 border-b border-slate-50 last:border-b-0">
              <span className="grid place-items-center h-8 w-8 rounded-lg text-white text-[11px] font-bold shrink-0" style={{ background: hueFor(c.interviewer_id) }}>{initials(c.interviewer_id)}</span>
              <div className="min-w-0 flex-1">
                <div className="text-[12.5px] font-medium text-ink-900 truncate">{c.interviewer_id}</div>
                <div className="text-[11px] text-slate-400 capitalize">{c.competency_key} · {c.sample_n} evaluation{c.sample_n === 1 ? "" : "s"}{c.drive_count ? ` · ${c.drive_count} drive${c.drive_count === 1 ? "" : "s"}` : ""}</div>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-28 h-1.5 rounded bg-slate-100 relative overflow-hidden">
                  <span className="absolute top-0 bottom-0 left-1/2 w-px bg-slate-300" />
                  <span className="absolute top-0 bottom-0 rounded" style={{ background: toneHex, left: d < 0 ? `${50 + Math.max(-50, d / 2)}%` : "50%", right: d > 0 ? `${50 - Math.min(50, d / 2)}%` : "50%" }} />
                </div>
                <span className="w-14 text-right text-[12px] font-semibold tabular-nums" style={{ color: toneHex }}>{d > 0 ? "+" : ""}{d} pts</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ---------- Evidence Ledger (append-only system of record — drive-evidence service) ---------- */
function EvidenceLedger({ id }) {
  const [nonce, setNonce] = useState(0);
  const evA = useAsync(() => withFallback(api.driveEvidence(id), []), [id, nonce]);
  const cfA = useAsync(() => withFallback(api.driveEvidenceConflicts(id), []), [id, nonce]);
  const regsA = useAsync(() => withFallback(api.driveRegistrations(id), []), [id]);
  const nameOf = (cid) => { const r = (regsA.data || []).find((x) => x.candidate_id === cid); return r?.candidate_name || r?.candidate_email || cid; };
  const [resolved, setResolved] = useState(() => new Set());
  const [backfilling, setBackfilling] = useState(false);
  const [actionError, setActionError] = useState("");

  async function backfill() {
    setBackfilling(true); setActionError("");
    try { await api.backfillEvidence(id); setNonce((n) => n + 1); }
    catch (error) { setActionError(error?.message || "Evidence could not be backfilled."); }
    finally { setBackfilling(false); }
  }

  if (evA.loading && !evA.data) return <Loading />;
  const ledger = evA.data ?? [];
  const conflicts = (cfA.data ?? []).filter((c) => !resolved.has(c.id));

  const SRC = { assessment: "teal", interview: "amber", coding: "slate", referral: "slate", screen: "slate" };
  const CONF = { high: "teal", medium: "amber", low: "rose" };
  const sources = [...new Set(ledger.map((e) => e.source_type))];

  async function reconcile(cid) {
    setActionError("");
    try { await api.resolveEvidenceConflict(cid); setResolved((r) => new Set(r).add(cid)); }
    catch (error) { setActionError(error?.message || "This evidence conflict could not be reconciled."); }
  }

  return (
    <section className="hire-console-evidence" aria-label="Evidence ledger">
      {actionError && <p role="alert" className="hire-drive-error">{actionError}</p>}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="font-display text-lg font-semibold text-ink-900">Evidence Ledger</h2>
          <p className="text-[12.5px] text-slate-500">The append‑only system of record. Every score traces back to a typed, sourced, confidence‑tagged row here — recorded automatically as assessments are graded.</p>
        </div>
        <Button size="sm" variant="secondary" onClick={backfill} disabled={backfilling}>
          <FileSearch size={14} /> {backfilling ? "Backfilling…" : "Backfill from marks"}
        </Button>
      </div>

      <div className="grid sm:grid-cols-3 gap-3 mb-4">
        <ReadOut label="Evidence rows" value={ledger.length} hint={sources.length ? sources.join(" · ") : "no sources yet"} />
        <ReadOut label="Candidates covered" value={new Set(ledger.map((e) => e.candidate_id)).size} hint="with at least one signal" />
        <ReadOut label="Open conflicts" value={conflicts.length} hint="divergent signals to reconcile" />
      </div>

      {conflicts.length > 0 && (
        <div className="rounded-2xl border border-amber-300 bg-amber-500/[0.04] overflow-hidden mb-4">
          <div className="px-4 py-3 border-b border-amber-200 flex items-center gap-2 text-[13px] font-semibold text-ink-900"><ShieldAlert size={16} className="text-amber-600" /> Evidence conflicts</div>
          {conflicts.map((c) => (
            <div key={c.id} className="flex items-center gap-3 px-4 py-3 border-b border-amber-100 last:border-b-0">
              <span className="grid place-items-center h-8 w-8 rounded-lg text-white text-[11px] font-bold shrink-0" style={{ background: hueFor(nameOf(c.candidate_id)) }}>{initials(nameOf(c.candidate_id))}</span>
              <div className="flex-1 min-w-0">
                <div className="text-[12.5px] font-medium text-ink-900 truncate">{nameOf(c.candidate_id)}</div>
                <div className="text-[11px] text-slate-500 capitalize">{c.competency_key} · signals diverge by <b>{Math.round(c.delta)}</b> pts</div>
              </div>
              <Button size="sm" variant="secondary" onClick={() => reconcile(c.id)}><ShieldCheck size={14} /> Reconcile</Button>
            </div>
          ))}
        </div>
      )}

      {ledger.length === 0 ? (
        <Card className="p-10 text-center text-slate-400">No evidence recorded yet. Rows accrue automatically as candidates complete assessments and interviews are evaluated.</Card>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-surface overflow-hidden">
          <div className="grid grid-cols-[1.4fr_1fr_0.85fr_0.7fr_0.9fr] gap-2 px-4 py-2.5 border-b border-slate-100 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Candidate</span><span>Competency</span><span>Source</span><span>Signal</span><span>Confidence</span>
          </div>
          <div className="max-h-[560px] overflow-y-auto">
            {ledger.map((e) => (
              <div key={e.id} className="grid grid-cols-[1.4fr_1fr_0.85fr_0.7fr_0.9fr] gap-2 px-4 py-2.5 border-b border-slate-50 last:border-b-0 items-center text-[12.5px]">
                <span className="flex items-center gap-2 min-w-0"><span className="grid place-items-center h-6 w-6 rounded-md text-white text-[9px] font-bold shrink-0" style={{ background: hueFor(nameOf(e.candidate_id)) }}>{initials(nameOf(e.candidate_id))}</span><span className="truncate text-ink-900">{nameOf(e.candidate_id)}</span></span>
                <span className="text-slate-500 capitalize truncate">{e.competency_key}</span>
                <span><Badge tone={SRC[e.source_type] || "slate"}>{e.source_type}</Badge></span>
                <span className="font-display font-bold tabular-nums" style={{ color: bandHex(band(e.signal)) }}>{Math.round(e.signal)}</span>
                <span><Badge tone={CONF[e.confidence] || "slate"}>{e.confidence}</Badge></span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

/* ---------- Interviewer Workspace (real interviews + evaluation twin) ---------- */
function InterviewerWorkspace({ id }) {
  const ivA = useAsync(() => withFallback(api.driveInterviews(id), []), [id]);
  const regsA = useAsync(() => withFallback(api.driveRegistrations(id), []), [id]);
  const nameOf = (cid) => { const r = (regsA.data || []).find((x) => x.candidate_id === cid); return r?.candidate_name || r?.candidate_email || cid; };
  const [rows, setRows] = useState(null);
  const [sel, setSel] = useState(null);
  const [actionError, setActionError] = useState("");
  const list = rows ?? ivA.data ?? [];
  if (ivA.loading) return <Loading />;

  const upsert = (iv) => setRows((prev) => { const base = prev ?? ivA.data ?? []; return base.some((x) => x.id === iv.id) ? base.map((x) => (x.id === iv.id ? { ...x, ...iv } : x)) : [...base, iv]; });
  async function rate(ivId, score) { setActionError(""); try { await api.rateInterview(ivId, { competency: "technical", score }); upsert({ id: ivId, avg_rating: score }); } catch (error) { setActionError(error?.message || "The interview rating could not be saved."); } }
  async function decide(ivId, decision) { setActionError(""); try { await api.decideInterview(ivId, { decision }); upsert({ id: ivId, decision, status: "completed" }); } catch (error) { setActionError(error?.message || "The interview decision could not be saved."); } }

  const pending = list.filter((v) => v.status !== "completed");
  const active = sel ? list.find((x) => x.id === sel) : pending[0] || list[0];

  return (
    <section className="hire-console-workspace" aria-label="Interviewer workspace">
      {actionError && <p role="alert" className="hire-drive-error">{actionError}</p>}
      <div className="mb-4">
        <h2 className="font-display text-lg font-semibold text-ink-900">Interviewer Workspace</h2>
        <p className="text-[12.5px] text-slate-500">Everything you need to evaluate — candidate context, prior evidence, and structured capture. Live interview data.</p>
      </div>
      {list.length === 0 ? <Card className="p-10 text-center text-slate-400">No interviews scheduled for this drive yet.</Card> : (
        <div className="grid lg:grid-cols-[300px_1fr] gap-4">
          <div className="grid gap-2 h-fit">
            {list.map((iv) => {
              const nm = nameOf(iv.candidate_id); const on = active && active.id === iv.id;
              return (
                <button key={iv.id} onClick={() => setSel(iv.id)} className={`text-left rounded-xl border p-3 ${on ? "border-brand-500 ring-1 ring-brand-500 bg-surface" : "border-slate-200 bg-surface hover:border-slate-300"}`}>
                  <div className="flex items-center gap-2.5">
                    <span className="grid place-items-center h-8 w-8 rounded-lg text-white text-[11px] font-bold" style={{ background: hueFor(nm) }}>{initials(nm)}</span>
                    <div className="min-w-0 flex-1"><div className="text-[12.5px] font-medium text-ink-900 truncate">{nm}</div><div className="text-[11px] text-slate-400 capitalize">{iv.stage} · {iv.mode}</div></div>
                    {iv.decision ? <Badge tone={iv.decision === "select" ? "teal" : iv.decision === "reject" ? "rose" : "amber"}>{iv.decision}</Badge> : <Badge tone="slate">{iv.status}</Badge>}
                  </div>
                </button>
              );
            })}
          </div>
          <div>{active ? <WorkspacePanel iv={active} name={nameOf(active.candidate_id)} driveId={id} onRate={rate} onDecide={decide} /> : <Card className="p-10 text-center text-slate-400">Select an interview.</Card>}</div>
        </div>
      )}
    </section>
  );
}
function WorkspacePanel({ iv, name, driveId, onRate, onDecide }) {
  const nm = name || iv.candidate_id;
  const [ev, setEv] = useState({ loading: true, skills: [] });
  const [comps, setComps] = useState([]);
  const [comp, setComp] = useState("technical");
  const [captured, setCaptured] = useState(null);
  useEffect(() => {
    let a = true;
    api.candidateSkills(iv.candidate_id).then((r) => { if (a) setEv({ loading: false, skills: r?.verified_skills || [] }); }).catch(() => { if (a) setEv({ loading: false, skills: [] }); });
    return () => { a = false; };
  }, [iv.candidate_id]);
  useEffect(() => {
    let a = true;
    api.evaluationModel(driveId).then((m) => { if (!a) return; const ks = (m?.weights || []).map((w) => ({ key: w.competency_key, name: w.name })); setComps(ks); if (ks.length) setComp(ks[0].key); }).catch(() => {});
    return () => { a = false; };
  }, [driveId]);

  // Rating a competency records the interview rating AND emits real per-competency
  // interview evidence (signal = score×20) into the ledger, feeding decisions + calibration.
  async function capture(score) {
    onRate(iv.id, score);
    try {
      await api.addEvidence({ drive_id: driveId, candidate_id: iv.candidate_id, competency_key: comp, source_type: "interview", signal: score * 20, confidence: "high", rationale: `Interview rating for ${comp}`, round_key: iv.stage });
    } catch { /* rating still recorded */ }
    setCaptured(`${comp} · ${score}/5`);
    setTimeout(() => setCaptured(null), 2500);
  }
  return (
    <div className="grid gap-4">
      <div className="rounded-2xl border border-slate-200 bg-surface p-5">
        <div className="flex items-center gap-3">
          <span className="grid place-items-center h-11 w-11 rounded-xl text-white font-bold" style={{ background: hueFor(nm) }}>{initials(nm)}</span>
          <div className="flex-1"><div className="font-semibold text-ink-900">{nm}</div><div className="text-[12px] text-slate-500 capitalize">{iv.stage} interview · {iv.mode}</div></div>
          {iv.avg_rating != null && <span className="inline-flex items-center gap-1 text-[12px] text-slate-600"><Star size={14} className="text-amber-500" />{iv.avg_rating}/5</span>}
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-surface p-5">
        <h3 className="text-[13px] font-semibold text-ink-900 mb-2 flex items-center gap-2"><ShieldAlert size={15} className="text-slate-400" /> Prior evidence</h3>
        {ev.loading ? <div className="text-sm text-slate-400">Loading…</div> : ev.skills.length ? (
          <div className="space-y-2">{ev.skills.map((s, i) => <div key={i} className="flex items-center gap-3 rounded-lg border border-slate-100 p-2.5"><span className="h-2 w-2 rounded-full" style={{ background: bandHex(s.level === "strong" ? "good" : s.level === "weak" ? "risk" : "warn") }} /><div className="flex-1"><div className="text-[12.5px] font-semibold text-ink-900">{s.skill}</div><div className="text-[11px] text-slate-400">{s.evidence || "drive evaluation"}</div></div><Badge tone={s.level === "strong" ? "teal" : s.level === "weak" ? "rose" : "amber"}>{s.level || "—"}</Badge></div>)}</div>
        ) : <div className="text-[12.5px] text-slate-400">No prior evidence yet — this is the first structured signal for this candidate.</div>}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-surface p-5">
        <h3 className="text-[13px] font-semibold text-ink-900 mb-3 flex items-center gap-2"><ClipboardList size={15} className="text-slate-400" /> Capture evaluation</h3>
        {iv.decision ? <div className="text-sm text-teal-600 flex items-center gap-2"><Check size={16} /> Decision recorded: <b className="capitalize">{iv.decision}</b></div> : (
          <div className="flex flex-wrap items-center gap-2">
            <select value={comp} onChange={(e) => setComp(e.target.value)} className="h-8 px-2 rounded-md border border-slate-200 text-[12px] bg-surface capitalize">
              {comps.length ? comps.map((c) => <option key={c.key} value={c.key}>{c.name}</option>) : <option value="technical">Technical</option>}
            </select>
            <span className="text-[11px] text-slate-400">rate</span>
            {[3, 4, 5].map((s) => <button key={s} onClick={() => capture(s)} className="grid place-items-center h-8 w-8 rounded-md bg-slate-100 hover:bg-amber-500/15 text-slate-600 text-sm font-semibold">{s}</button>)}
            {captured && <span className="text-[11px] text-teal-600">Recorded {captured}</span>}
            <div className="flex-1" />
            <Button size="sm" variant="secondary" onClick={() => onDecide(iv.id, "reject")}><X size={14} /> Reject</Button>
            <Button size="sm" onClick={() => onDecide(iv.id, "select")}><Send size={14} /> Recommend</Button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- Configure (roles & rounds + eligibility + PPO — existing real APIs) ---------- */
function ConfigureView({ d, id, onChange }) {
  return (
    <section className="hire-console-configure grid gap-6" aria-label="Drive configuration">
      <Config d={d} id={id} onChange={onChange} />
      <EvaluationModelCard id={id} />
      <div className="grid lg:grid-cols-2 gap-6">
        <Eligibility id={id} />
        <Ppo id={id} />
      </div>
    </section>
  );
}

/* Evaluation model — the weighted competencies a drive hires for (drive-competency). */
function EvaluationModelCard({ id }) {
  const [weights, setWeights] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      const m = await api.evaluationModel(id).catch(() => null);
      setWeights((m?.weights || []).map((w) => ({ competency_key: w.competency_key, name: w.name, weight: w.weight })));
      setLoaded(true);
    })();
  }, [id]);

  const total = weights.reduce((n, w) => n + (Number(w.weight) || 0), 0) || 1;
  const add = () => setWeights((w) => [...w, { competency_key: "", name: "", weight: 1 }]);
  const upd = (i, patch) => setWeights((w) => w.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const rm = (i) => setWeights((w) => w.filter((_, j) => j !== i));

  async function save() {
    const clean = weights
      .map((w) => ({ ...w, competency_key: (w.competency_key || w.name || "").toLowerCase().trim().replace(/\s+/g, "_"), name: w.name || w.competency_key, weight: Number(w.weight) > 0 ? Number(w.weight) : 1 }))
      .filter((w) => w.competency_key);
    if (!clean.length) return;
    setSaving(true);
    setError("");
    try { await api.setEvaluationModel({ drive_id: id, weights: clean }); setSaved(true); setTimeout(() => setSaved(false), 2000); }
    catch (e) { setError(e?.message || "Evaluation model could not be saved."); }
    finally { setSaving(false); }
  }

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-display font-semibold text-ink-900 flex items-center gap-2"><Scale size={17} className="text-slate-400" /> Evaluation model</h3>
        <span className="text-[11px] text-slate-400">weights normalise automatically</span>
      </div>
      <p className="text-[12.5px] text-slate-500 mb-3">The competencies this drive hires for and their relative weight. Evidence roll-ups and decision confidence use this model.</p>
      {error && <p role="alert" className="hire-drive-error mb-3">{error}</p>}
      {!loaded ? <div className="text-sm text-slate-400">Loading…</div> : (
        <div className="grid gap-2">
          {weights.length === 0 && <div className="text-[12.5px] text-slate-400 py-2">No model yet — add the competencies that matter for this drive.</div>}
          {weights.map((w, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input value={w.name} onChange={(e) => upd(i, { name: e.target.value })} placeholder="Competency (e.g. System Design)" className="flex-1" />
              <Input type="number" min="1" max="10" value={w.weight} onChange={(e) => upd(i, { weight: e.target.value })} className="w-20" />
              <span className="w-12 text-right text-[12px] tabular-nums text-slate-500">{Math.round((Number(w.weight) || 0) / total * 100)}%</span>
              <button onClick={() => rm(i)} aria-label="Remove" className="grid place-items-center h-9 w-9 rounded-md border border-slate-200 text-slate-400 hover:text-rose-600"><X size={16} /></button>
            </div>
          ))}
          <div className="flex items-center justify-between mt-1">
            <Button variant="ghost" size="sm" onClick={add}><Plus size={15} /> Add competency</Button>
            <Button size="sm" onClick={save} disabled={saving || weights.length === 0}>{saving ? "Saving…" : saved ? "Saved ✓" : "Save model"}</Button>
          </div>
        </div>
      )}
    </Card>
  );
}

const STAGE_TYPES = ["aptitude", "technical", "verbal", "coding", "sql", "gd", "interview", "hr", "custom"];
function Config({ d, id, onChange }) {
  const [roles, setRoles] = useState(d.roles || []);
  const [role, setRole] = useState({ title: "", ctc: "", positions: 1, skillsText: "" });
  const parseSkills = (text) => (text || "").split(",").map((t) => t.trim()).filter(Boolean).map((t) => { const [name, w] = t.split(":").map((x) => x.trim()); const weight = Number(w); return { name, weight: weight > 0 ? weight : 1 }; });
  const [stages, setStages] = useState([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      const wf = await api.getWorkflow(id).catch(() => null);
      if (wf && wf.length) setStages(wf.map((s) => ({ type: s.type, label: s.label || "", optional: !!s.optional })));
      else setStages((d.rounds || []).map((r) => ({ type: r.type, label: r.label || "", optional: !!r.optional })));
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function addRole(e) {
    e.preventDefault();
    setError("");
    const skills = parseSkills(role.skillsText);
    const payload = { title: role.title, ctc: role.ctc, positions: Number(role.positions), skills };
    try {
      const created = await api.addRole(id, payload);
      const next = [...roles, created]; setRoles(next); onChange({ ...d, roles: next }); setRole({ title: "", ctc: "", positions: 1, skillsText: "" });
    } catch (e) { setError(e?.message || "Role could not be added to this drive."); }
  }
  const addStage = () => setStages((s) => [...s, { type: "aptitude", label: "", optional: false }]);
  const updateStage = (i, patch) => setStages((s) => s.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const removeStage = (i) => setStages((s) => s.filter((_, j) => j !== i));
  const move = (i, dir) => setStages((s) => { const j = i + dir; if (j < 0 || j >= s.length) return s; const c = [...s]; [c[i], c[j]] = [c[j], c[i]]; return c; });
  async function savePipeline() {
    setSaving(true); setSaved(false); setError("");
    const payload = stages.map((s, i) => ({ order: i + 1, type: s.type, label: s.label || s.type, optional: s.optional }));
    try { const wf = await api.setWorkflow(id, payload); onChange({ ...d, rounds: wf }); setSaved(true); setTimeout(() => setSaved(false), 2500); }
    catch (e) { setError(e?.message || "Pipeline could not be saved."); } finally { setSaving(false); }
  }

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      {error && <p role="alert" className="hire-drive-error lg:col-span-2">{error}</p>}
      <Card className="p-6">
        <h2 className="font-display font-semibold text-ink-900 mb-4">Roles</h2>
        <div className="space-y-2 mb-4">
          {roles.map((r) => (
            <div key={r.id} className="rounded-md border border-slate-100 p-3 flex items-center justify-between">
              <div className="min-w-0">
                <p className="font-medium text-ink-900">{r.title}</p>
                <p className="text-xs text-slate-500">{r.ctc || "—"} · {r.positions} positions</p>
                {(r.skills || []).length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{r.skills.map((sk) => <span key={sk.name} className="rounded bg-brand-500/10 text-brand-700 px-1.5 py-0.5 text-[11px]">{sk.name}{sk.weight > 1 ? `·${sk.weight}` : ""}</span>)}</div>}
              </div>
              <Briefcase size={16} className="text-slate-300 shrink-0" />
            </div>
          ))}
          {roles.length === 0 && <p className="text-sm text-slate-400">No roles yet.</p>}
        </div>
        <form onSubmit={addRole} className="space-y-3 border-t border-slate-100 pt-4">
          <Field label="Role title"><Input required value={role.title} onChange={(e) => setRole({ ...role, title: e.target.value })} placeholder="Software Engineer" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="CTC"><Input value={role.ctc} onChange={(e) => setRole({ ...role, ctc: e.target.value })} placeholder="6 LPA" /></Field>
            <Field label="Positions"><Input type="number" min="1" value={role.positions} onChange={(e) => setRole({ ...role, positions: e.target.value })} /></Field>
          </div>
          <Field label="Required skills" hint="Comma-separated. Add a weight with ':' — e.g. Arrays, SQL:2, Python. Powers candidate skill-matching.">
            <Input value={role.skillsText} onChange={(e) => setRole({ ...role, skillsText: e.target.value })} placeholder="Arrays, SQL:2, Python" />
          </Field>
          <Button type="submit" variant="secondary" className="w-full"><Plus size={16} /> Add role</Button>
        </form>
      </Card>

      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-semibold text-ink-900">Round pipeline</h2>
          {saved && <Badge tone="teal"><CheckCircle2 size={13} /> Saved</Badge>}
        </div>
        <p className="text-xs text-slate-400 mb-3">Build the exact stages for this drive — reorder, rename, and mark optional rounds. The pipeline, workspaces, and analytics adapt to this.</p>
        <div className="space-y-2 mb-4">
          {stages.map((s, i) => (
            <div key={i} className="rounded-md border border-slate-200 p-2.5 flex items-center gap-2">
              <span className="grid place-items-center h-7 w-7 rounded-md bg-invert-900 text-white text-sm font-semibold shrink-0">{i + 1}</span>
              <select value={s.type} onChange={(e) => updateStage(i, { type: e.target.value })} className="h-9 px-2 rounded-md border border-slate-200 text-sm bg-surface">{STAGE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select>
              <Input value={s.label} onChange={(e) => updateStage(i, { label: e.target.value })} placeholder="Label (e.g. Aptitude Test)" className="h-9 flex-1" />
              <label className="flex items-center gap-1 text-xs text-slate-500 shrink-0" title="Optional round"><input type="checkbox" checked={s.optional} onChange={(e) => updateStage(i, { optional: e.target.checked })} className="accent-brand-500" />opt</label>
              <div className="flex flex-col shrink-0"><button onClick={() => move(i, -1)} className="text-slate-300 hover:text-ink-900 leading-none"><ChevronUp size={14} /></button><button onClick={() => move(i, 1)} className="text-slate-300 hover:text-ink-900 leading-none"><ChevronDown size={14} /></button></div>
              <button onClick={() => removeStage(i)} className="text-slate-300 hover:text-rose-500 shrink-0"><Trash2 size={15} /></button>
            </div>
          ))}
          {stages.length === 0 && <p className="text-sm text-slate-400">No rounds yet — add your first stage.</p>}
        </div>
        <div className="flex gap-2 border-t border-slate-100 pt-4">
          <Button variant="secondary" onClick={addStage} className="flex-1"><Plus size={16} /> Add stage</Button>
          <Button onClick={savePipeline} disabled={saving}>{saving ? "Saving…" : "Save pipeline"}</Button>
        </div>
      </Card>
    </div>
  );
}

function Eligibility({ id }) {
  const [form, setForm] = useState({ min_cgpa: 7, branches: "CSE, CSE-AI", max_backlogs: 0, passing_year: 2027, max_age: "" });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  async function save(e) {
    e.preventDefault();
    setError("");
    const body = { min_cgpa: Number(form.min_cgpa), branches: form.branches.split(",").map((b) => b.trim()).filter(Boolean), max_backlogs: Number(form.max_backlogs), passing_year: Number(form.passing_year), max_age: form.max_age ? Number(form.max_age) : null };
    try { await api.setEligibility(id, body); setSaved(true); setTimeout(() => setSaved(false), 2500); }
    catch (e) { setError(e?.message || "Eligibility settings could not be saved."); }
  }
  return (
    <Card className="p-6">
      <h2 className="font-display font-semibold text-ink-900 mb-4">Eligibility criteria</h2>
      {error && <p role="alert" className="hire-drive-error mb-3">{error}</p>}
      <form onSubmit={save} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Minimum CGPA"><Input type="number" step="0.1" value={form.min_cgpa} onChange={(e) => setForm({ ...form, min_cgpa: e.target.value })} /></Field>
          <Field label="Max backlogs"><Input type="number" value={form.max_backlogs} onChange={(e) => setForm({ ...form, max_backlogs: e.target.value })} /></Field>
        </div>
        <Field label="Allowed branches (comma-separated)"><Input value={form.branches} onChange={(e) => setForm({ ...form, branches: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Passing year"><Input type="number" value={form.passing_year} onChange={(e) => setForm({ ...form, passing_year: e.target.value })} /></Field>
          <Field label="Max age" hint="Optional."><Input type="number" value={form.max_age} onChange={(e) => setForm({ ...form, max_age: e.target.value })} placeholder="—" /></Field>
        </div>
        <div className="flex items-center gap-3"><Button type="submit"><Check size={17} /> Save criteria</Button>{saved && <span className="text-sm text-teal-600 flex items-center gap-1.5"><Check size={16} /> Saved</span>}</div>
      </form>
    </Card>
  );
}

function Ppo({ id }) {
  const [form, setForm] = useState({ top_pct: 15, stages: "internal_tech, hr", min_internship_score: 70 });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  async function save(e) {
    e.preventDefault();
    setError("");
    const body = { eligibility: { top_pct: Number(form.top_pct) }, stages: form.stages.split(",").map((s) => s.trim()).filter(Boolean), conversion_criteria: { min_internship_score: Number(form.min_internship_score) } };
    try { await api.setPpo(id, body); setSaved(true); setTimeout(() => setSaved(false), 2500); }
    catch (e) { setError(e?.message || "PPO settings could not be saved."); }
  }
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-1"><Award size={18} className="text-amber-500" /><h2 className="font-display font-semibold text-ink-900">PPO pipeline</h2></div>
      <p className="text-sm text-slate-500 mb-4">Pre-Placement Offer track with GenZify.</p>
      {error && <p role="alert" className="hire-drive-error mb-3">{error}</p>}
      <form onSubmit={save} className="space-y-4">
        <Field label="Eligibility — top % by assessment score"><Input type="number" value={form.top_pct} onChange={(e) => setForm({ ...form, top_pct: e.target.value })} /></Field>
        <Field label="Selection stages (comma-separated)"><Input value={form.stages} onChange={(e) => setForm({ ...form, stages: e.target.value })} /></Field>
        <Field label="Conversion — min internship score"><Input type="number" value={form.min_internship_score} onChange={(e) => setForm({ ...form, min_internship_score: e.target.value })} /></Field>
        <div className="flex items-center gap-3"><Button type="submit"><Check size={17} /> Save PPO config</Button>{saved && <span className="text-sm text-teal-600 flex items-center gap-1.5"><Check size={16} /> Saved</span>}</div>
      </form>
    </Card>
  );
}
