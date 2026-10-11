import { useEffect, useState } from "react";
import { CalendarClock, CheckCircle2, MessageSquareText, Star } from "lucide-react";
import { api } from "../lib/api.js";
import { Button, Card, Field, Input } from "../components/ui/primitives.jsx";
import { EmptyState, Loading, PageHeader } from "../components/ui/states.jsx";

export default function InterviewerConsole() {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [draft, setDraft] = useState({ competency: "technical", score: "", remark: "" });
  const [decision, setDecision] = useState({ decision: "", reason: "" });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    const rows = await api.myInterviews();
    setItems(rows || []);
    if (selected) setSelected((rows || []).find((row) => row.id === selected.id) || null);
  }

  useEffect(() => { load().catch((e) => setError(e.message || "Could not load assignments.")).finally(() => setLoading(false)); }, []);

  async function open(item) {
    setError(""); setBusy(true);
    try { setSelected(await api.interviewDossier(item.id)); }
    catch (e) { setError(e.message || "Could not open this interview."); }
    finally { setBusy(false); }
  }

  async function submit(action) {
    if (!selected) return;
    setError(""); setBusy(true);
    try { await action(); await load(); }
    catch (e) { setError(e.message || "Could not save interview feedback."); }
    finally { setBusy(false); }
  }

  if (loading) return <Loading />;
  return <div className="page-composition">
    <PageHeader title="My interviews" subtitle="Review only the interviews assigned to your account, then record structured feedback." />
    {error && <div role="alert" className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>}
    <div className="grid gap-5 xl:grid-cols-[minmax(280px,0.85fr)_minmax(0,1.5fr)]">
      <Card className="overflow-hidden p-0">
        <div className="border-b border-slate-100 px-4 py-3 font-semibold">Assigned interviews <span className="text-slate-400">({items.length})</span></div>
        {items.map((item) => <button key={item.id} onClick={() => open(item)} className={`block w-full border-b border-slate-100 px-4 py-4 text-left hover:bg-slate-50 ${selected?.id === item.id ? "bg-brand-500/5" : ""}`}>
          <strong className="block">{item.stage || "Interview"} interview</strong>
          <span className="mt-1 flex items-center gap-1 text-xs text-slate-500"><CalendarClock size={13} /> {item.slot || "Time to be confirmed"}</span>
          <span className="mt-1 block truncate text-xs text-slate-500">Candidate {item.candidate_id}</span>
          <span className="mt-1 block text-xs text-slate-500">{item.status}</span>
        </button>)}
        {!items.length && <EmptyState title="No assigned interviews" hint="A recruiter will assign interviews to this account." />}
      </Card>

      {selected ? <Card className="space-y-5 p-5">
        <div><p className="text-xs font-bold uppercase tracking-widest text-slate-500">Interview workspace</p><h2 className="mt-1 text-xl font-semibold">{selected.stage} interview</h2><p className="text-sm text-slate-500">Candidate {selected.candidate_id} · {selected.mode} · {selected.slot || "time pending"}</p></div>
        {selected.link && <a className="text-sm font-semibold text-brand-700 underline" href={selected.link} target="_blank" rel="noreferrer">Open meeting link</a>}
        <div className="rounded-xl border border-slate-100 p-4"><h3 className="mb-3 flex items-center gap-2 font-semibold"><Star size={16} /> Add feedback</h3>
          <div className="grid gap-3 sm:grid-cols-3"><Field label="Competency"><select value={draft.competency} onChange={(e) => setDraft({ ...draft, competency: e.target.value })} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3">{["technical", "communication", "problem_solving", "culture"].map((x) => <option key={x} value={x}>{x.replaceAll("_", " ")}</option>)}</select></Field>
            <Field label="Score (1–5)"><Input type="number" min="1" max="5" value={draft.score} onChange={(e) => setDraft({ ...draft, score: e.target.value })} /></Field>
            <Field label="Feedback"><Input value={draft.remark} maxLength="512" onChange={(e) => setDraft({ ...draft, remark: e.target.value })} placeholder="Evidence-based notes" /></Field></div>
          <div className="mt-3"><Button disabled={busy || !draft.score} onClick={() => submit(() => api.rateInterview(selected.id, { ...draft, score: Number(draft.score) }))}><MessageSquareText size={15} /> Save feedback</Button></div>
        </div>
        {selected.decision ? <p className="rounded-lg bg-slate-50 p-3 text-sm">Decision already recorded: <strong>{selected.decision}</strong></p> : <div className="rounded-xl border border-slate-100 p-4"><h3 className="mb-3 font-semibold">Record decision</h3><div className="grid gap-3 sm:grid-cols-2"><Field label="Decision"><select value={decision.decision} onChange={(e) => setDecision({ ...decision, decision: e.target.value })} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3"><option value="">Choose</option>{["select", "reject", "hold", "next_round"].map((x) => <option key={x}>{x}</option>)}</select></Field><Field label="Reason"><Input value={decision.reason} maxLength="512" onChange={(e) => setDecision({ ...decision, reason: e.target.value })} /></Field></div><div className="mt-3"><Button disabled={busy || !decision.decision} onClick={() => submit(() => api.decideInterview(selected.id, decision))}><CheckCircle2 size={15} /> Save decision</Button></div></div>}
        <div className="border-t border-slate-100 pt-4"><h3 className="mb-2 font-semibold">Submitted ratings</h3>{(selected.ratings || []).map((rating, index) => <p key={index} className="mb-1 text-sm text-slate-600">{rating.competency}: {rating.score}/5{rating.remark ? ` — ${rating.remark}` : ""}</p>)}</div>
      </Card> : <Card><EmptyState title="Select an interview" hint="Only assigned interviews are listed here." /></Card>}
    </div>
  </div>;
}
