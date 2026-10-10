import { useEffect, useState } from "react";
import { CalendarPlus, Video, Star, Check, X, UserCheck } from "lucide-react";
import { Card, Badge, Button, Field, Input } from "../../components/ui/primitives.jsx";
import { Loading } from "../../components/ui/states.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { api, withFallback } from "../../lib/api.js";
import "../../styles/recruiter-operations-pages.css";

const DEC_TONE = { select: "teal", reject: "rose", hold: "amber", next_round: "brand" };

export default function InterviewsTab({ id }) {
  const loaded = useAsync(() => withFallback(api.driveInterviews(id), []), [id]);
  const [rows, setRows] = useState(null);
  const emptyForm = { candidate_id: "", round_order: "", stage: "technical", mode: "online", link: "", slot: "", interviewers: [{ name: "", email: "" }] };
  const [form, setForm] = useState(emptyForm);
  // Candidates who cleared the most recent round — those eligible to interview.
  const [eligible, setEligible] = useState([]);
  const [names, setNames] = useState({});   // candidate_id -> { name, roll, email }
  const [rounds, setRounds] = useState([]); // drive workflow rounds
  const [marksDraft, setMarksDraft] = useState({}); // ivId -> { marks, max }
  const [actionError, setActionError] = useState("");
  const list = rows ?? loaded.data ?? [];
  const draftFor = (ivId) => marksDraft[ivId] || { marks: "", max: "100" };

  // Map an interview stage to its round in the pipeline, by matching keywords in
  // the round label/type (technical → the technical-interview round, hr → HR).
  const STAGE_KW = { technical: ["technical", "tech", "face to face", "f2f"], hr: ["hr", "human"], ppo: ["ppo", "hr"] };
  function roundForStage(stage) {
    const kws = STAGE_KW[stage] || [stage];
    const r = rounds.find((rd) => kws.some((k) => `${rd.label || ""} ${rd.type || ""}`.toLowerCase().includes(k)));
    return r?.order;
  }
  // Infer a sensible stage from the round the recruiter picked.
  function stageForRound(rd) {
    const t = `${rd?.label || ""} ${rd?.type || ""}`.toLowerCase();
    if (t.includes("hr") || t.includes("human")) return "hr";
    if (t.includes("ppo")) return "ppo";
    return "technical";
  }
  // The round an interview belongs to (explicit choice → stored round_id → stage).
  function orderForInterview(iv) {
    if (iv.round_order != null) return iv.round_order;
    if (iv.round_id != null && `${iv.round_id}`.match(/^\d+$/)) return Number(iv.round_id);
    return roundForStage(iv.stage);
  }

  useEffect(() => {
    (async () => {
      try {
        const wf = await api.getWorkflow(id).catch(() => []);
        setRounds(wf || []);
        let orders = (wf || []).map((r) => r.order).filter((o) => o != null);
        if (!orders.length) orders = [1, 2, 3, 4, 5];   // fallback if no workflow defined
        orders = [...new Set(orders)].sort((a, b) => b - a);   // newest round first
        let cleared = [];
        let anyCandidates = [];
        for (const order of orders) {
          const resp = await api.roundScores(id, order).catch(() => null);
          const scores = resp?.scores || [];                  // { scores, round } shape
          if (!scores.length) continue;
          if (!anyCandidates.length) anyCandidates = scores;   // latest round with candidates
          const c = scores.filter((s) => s.cleared);
          if (c.length) { cleared = c; break; }               // prefer cleared/selected
        }
        // Prefer the cleared/selected shortlist; otherwise show everyone in the drive.
        setEligible(cleared.length ? cleared : anyCandidates);
      } catch { setEligible([]); }
    })();
  }, [id]);

  // Resolve candidate names/rolls for the eligible list + every scheduled
  // interview, so the list shows people instead of raw UUIDs.
  const idsKey = list.map((iv) => iv.candidate_id).join(",");
  useEffect(() => {
    const map = {};
    eligible.forEach((c) => {
      map[c.candidate_id] = { name: c.candidate_name, roll: c.candidate_roll, email: c.candidate_email };
    });
    const missing = [...new Set(list.map((iv) => iv.candidate_id).filter((cid) => cid && !map[cid]))];
    (async () => {
      if (missing.length) {
        try {
          const r = await api.resolveCandidates(missing);
          Object.entries(r || {}).forEach(([cid, info]) => {
            map[cid] = { name: info.full_name || info.name, roll: info.roll_number || info.roll, email: info.email };
          });
        } catch { /* fall back to the id */ }
      }
      setNames(map);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eligible, idsKey]);

  if (loaded.loading) return <Loading />;

  function upsert(iv) {
    setRows((list.some((x) => x.id === iv.id) ? list.map((x) => (x.id === iv.id ? { ...x, ...iv } : x)) : [...list, iv]));
  }

  async function schedule(e) {
    e.preventDefault();
    setActionError("");
    const interviewers = form.interviewers.filter((iw) => iw.email.trim());
    // Persist the chosen round in round_id (as its order) so the link survives reloads.
    const round_id = form.round_order !== "" ? String(form.round_order) : null;
    let iv;
    try { iv = await api.scheduleInterview({ drive_id: id, ...form, round_id, interviewers, slot: form.slot.replace("T", " ") }); }
    catch (error) { setActionError(error?.message || "The interview could not be scheduled. Check the details and try again."); return; }
    upsert({ id: iv.id, candidate_id: form.candidate_id, stage: form.stage, mode: form.mode,
             round_order: form.round_order !== "" ? Number(form.round_order) : undefined,
             status: "scheduled", decision: null, avg_rating: null });
    setForm(emptyForm);
  }

  function addInterviewer() {
    setForm((f) => ({ ...f, interviewers: [...f.interviewers, { name: "", email: "" }] }));
  }
  function removeInterviewer(i) {
    setForm((f) => ({ ...f, interviewers: f.interviewers.filter((_, j) => j !== i) }));
  }
  function updateInterviewer(i, field, value) {
    setForm((f) => ({ ...f, interviewers: f.interviewers.map((iw, j) => (j === i ? { ...iw, [field]: value } : iw)) }));
  }

  // Push an interview action into the candidate's matching round marks sheet, so
  // technical/HR interview results show up (and clear) in Rounds & Marks.
  function syncRound(iv, patch) {
    const order = iv && orderForInterview(iv);
    if (order != null && iv.candidate_id) {
      api.setRoundScore(id, order, { candidate_id: iv.candidate_id, ...patch }).catch(() => {});
    }
  }

  async function rate(ivId, competency, score) {
    setActionError("");
    try { await api.rateInterview(ivId, { competency, score }); } catch (error) { setActionError(error?.message || "The interview rating could not be saved."); return; }
    upsert({ id: ivId, avg_rating: score });
    // rating (out of 5) → the round's marks sheet
    syncRound(list.find((x) => x.id === ivId), { marks: score, max_marks: 5 });
  }
  async function decide(ivId, decision) {
    setActionError("");
    try { await api.decideInterview(ivId, { decision }); } catch (error) { setActionError(error?.message || "The interview decision could not be saved."); return; }
    upsert({ id: ivId, decision, status: "completed" });
    // Select → mark cleared in that round; Reject → not cleared.
    syncRound(list.find((x) => x.id === ivId), { cleared: decision === "select" });
  }

  function setDraft(ivId, field, value) {
    setMarksDraft((d) => ({ ...d, [ivId]: { ...draftFor(ivId), [field]: value } }));
  }
  async function saveMarks(iv) {
    setActionError("");
    const d = draftFor(iv.id);
    if (d.marks === "" || d.marks == null) return;
    const marks = Number(d.marks);
    const max = Number(d.max) || 100;
    if (Number.isNaN(marks)) return;
    // Save the marks into the linked round's marks sheet.
    syncRound(iv, { marks, max_marks: max });
    // Reflect an out-of-5 rating on the interview so its avg shows too.
    const score = Math.max(1, Math.min(5, Math.round((marks / max) * 5)));
    try { await api.rateInterview(iv.id, { competency: "technical", score }); } catch (error) { setActionError(error?.message || "The interview score could not be saved."); return; }
    upsert({ id: iv.id, marks, max_marks: max, avg_rating: score });
  }

  return (
    <section className="page-composition page-composition-recruiter-detail hire-ops hire-ops--interviews"><div className="hire-interviews-workspace">
      {/* Schedule form */}
      <aside aria-labelledby="interview-scheduler-title"><Card className="hire-interview-scheduler p-6 h-fit">
        <div className="hire-interview-scheduler-title"><span className="hire-ops-kicker">01 · Schedule</span><h2 id="interview-scheduler-title" className="font-display font-semibold text-ink-900"><CalendarPlus size={18} aria-hidden="true" /> Book an interview</h2><p>Connect a candidate with a round and an interview panel.</p></div>
        <form onSubmit={schedule} className="space-y-3">
          <Field label="Candidate">
            {eligible.length > 0 ? (
              <select required value={form.candidate_id}
                onChange={(e) => setForm({ ...form, candidate_id: e.target.value })}
                className="w-full h-11 px-3 rounded-md border border-slate-200 bg-surface text-ink-900">
                <option value="">Select a candidate…</option>
                {eligible.map((c) => (
                  <option key={c.candidate_id} value={c.candidate_id}>
                    {c.candidate_roll ? `${c.candidate_roll} · ` : ""}{c.candidate_name || c.candidate_id}
                    {c.cleared ? "  ✓ cleared" : ""}{c.percentage != null ? `  (${Math.round(c.percentage)}%)` : ""}
                  </option>
                ))}
              </select>
            ) : (
              <Input required value={form.candidate_id}
                onChange={(e) => setForm({ ...form, candidate_id: e.target.value })}
                placeholder="No cleared candidates yet — enter a candidate id" />
            )}
          </Field>
          {rounds.length > 0 && (
            <Field label="Round (from Rounds & Marks)">
              <select value={form.round_order}
                onChange={(e) => {
                  const order = e.target.value === "" ? "" : Number(e.target.value);
                  const rd = rounds.find((r) => r.order === order);
                  setForm((f) => ({ ...f, round_order: e.target.value === "" ? "" : order,
                                    stage: rd ? stageForRound(rd) : f.stage }));
                }}
                className="w-full h-11 px-3 rounded-md border border-slate-200 bg-surface text-ink-900">
                <option value="">Not linked to a round</option>
                {rounds.map((r) => (
                  <option key={r.order} value={r.order}>{r.order}. {r.label || r.type}</option>
                ))}
              </select>
            </Field>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-ink-900 mb-1.5">Stage</label>
              <select value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })}
                className="w-full h-11 px-3 rounded-md border border-slate-200 bg-surface text-ink-900">
                {["technical", "hr", "ppo"].map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-ink-900 mb-1.5">Mode</label>
              <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}
                className="w-full h-11 px-3 rounded-md border border-slate-200 bg-surface text-ink-900">
                {["online", "in_person"].map((m) => <option key={m}>{m}</option>)}
              </select>
            </div>
          </div>
          <Field label="Date & time">
            <input type="datetime-local" value={form.slot}
              onChange={(e) => setForm({ ...form, slot: e.target.value })}
              className="w-full h-11 px-3 rounded-md border border-slate-200 bg-surface text-ink-900" />
          </Field>
          <Field label="Meeting link">
            <Input value={form.link} onChange={(e) => setForm({ ...form, link: e.target.value })}
              placeholder="https://meet.google.com/… or Zoom link" />
          </Field>
          {form.link.trim() && (
            <p className="-mt-2 text-xs text-teal-600 flex items-center gap-1">
              <Check size={12} /> This link will be emailed to the candidate on Schedule.
            </p>
          )}

          <div className="pt-2 border-t border-slate-100">
            <p className="text-sm font-medium text-ink-900 mb-2 flex items-center gap-1.5">
              <UserCheck size={15} className="text-brand-500" /> Assigned to (interviewers)
            </p>
            <div className="space-y-2.5">
              {form.interviewers.map((iw, i) => (
                <div key={i} className="rounded-lg border border-slate-100 p-2.5 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-400">Interviewer {i + 1}</span>
                    {form.interviewers.length > 1 && (
                      <button type="button" onClick={() => removeInterviewer(i)}
                        className="text-slate-300 hover:text-rose-500"><X size={14} /></button>
                    )}
                  </div>
                  <Input value={iw.name} placeholder="Name (e.g. Ravi Kumar)"
                    onChange={(e) => updateInterviewer(i, "name", e.target.value)} />
                  <Input type="email" value={iw.email} placeholder="interviewer@company.com"
                    onChange={(e) => updateInterviewer(i, "email", e.target.value)} />
                </div>
              ))}
              <button type="button" onClick={addInterviewer}
                className="w-full h-9 rounded-lg border border-dashed border-slate-200 text-slate-500 hover:border-brand-300 hover:text-brand-600 text-sm font-medium flex items-center justify-center gap-1.5">
                <UserCheck size={14} /> Add another interviewer
              </button>
              {form.interviewers.some((iw) => iw.email.trim()) && (
                <p className="text-xs text-teal-600 flex items-center gap-1">
                  <Check size={12} /> All interviewers with an email will be sent the interview details.
                </p>
              )}
            </div>
          </div>

          <Button type="submit" className="w-full"><CalendarPlus size={16} /> Schedule</Button>
        </form>
      </Card></aside>

      {/* Interview list */}
      <section className="hire-interview-agenda" aria-labelledby="interview-agenda-title">
        <header className="hire-interview-agenda-heading"><div><span className="hire-ops-kicker">02 · Panel agenda</span><h2 id="interview-agenda-title" className="font-display font-semibold text-ink-900">Scheduled interviews</h2><p>Review the panel, appointment, and candidate outcome in one place.</p></div>{!loaded.live && <span role="status" className="hire-source-state">Live interview data is unavailable.</span>}</header>
        {actionError && <p role="alert" className="hire-interview-error">{actionError}</p>}
        {list.length === 0 && <Card className="hire-interview-empty p-6"><p className="text-sm text-slate-500">No interviews scheduled.</p></Card>}
        <ol className="hire-interview-agenda-list">{list.map((iv, index) => (
          <li key={iv.id} className="hire-interview-record">
            <div className="hire-interview-sequence" aria-hidden="true">{String(index + 1).padStart(2, "0")}</div>
            <Card className="hire-interview-record-card p-5">
            <div className="hire-interview-record-heading">
              <div className="min-w-0">
                <p className="font-display font-semibold text-ink-900">
                  {names[iv.candidate_id]?.name || iv.candidate_id}
                  {names[iv.candidate_id]?.roll && (
                    <span className="ml-2 text-xs font-normal text-slate-400">· {names[iv.candidate_id].roll}</span>
                  )}
                </p>
                {names[iv.candidate_id]?.email && (
                  <p className="text-xs text-slate-400 truncate">{names[iv.candidate_id].email}</p>
                )}
                <p className="text-sm text-slate-500 capitalize flex items-center gap-2 mt-0.5">
                  {iv.mode === "online" && <Video size={14} />} {iv.stage} · {iv.mode.replace("_", " ")}
                  {(() => {
                    const r = rounds.find((rd) => rd.order === orderForInterview(iv));
                    return r ? <span className="normal-case text-xs text-brand-600">· {r.label || r.type}</span> : null;
                  })()}
                </p>
              </div>
              {iv.decision ? (
                <Badge tone={DEC_TONE[iv.decision] || "slate"}>{iv.decision.replace("_", " ")}</Badge>
              ) : (
                <Badge tone="slate">{iv.status}</Badge>
              )}
            </div>

            <dl className="hire-interview-meta">
              <div><dt>Appointment</dt><dd>{iv.slot || "Time not set"}</dd></div>
              <div><dt>Interviewers</dt><dd>{(iv.interviewers || []).map((person) => person.name || person.email).filter(Boolean).join(", ") || "Panel not assigned"}</dd></div>
              {iv.link && <div><dt>Meeting</dt><dd><a href={iv.link} target="_blank" rel="noreferrer">Open meeting link</a></dd></div>}
            </dl>

            {iv.avg_rating != null && (
              <p className="mt-3 text-sm text-slate-600 flex items-center gap-1.5">
                <Star size={15} className="text-amber-500" /> Avg rating {iv.avg_rating}/5
              </p>
            )}

            {!iv.decision && (
              <div className="mt-4 border-t border-slate-100 pt-4 flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Marks</label>
                  <input type="number" value={draftFor(iv.id).marks} placeholder="0"
                    onChange={(e) => setDraft(iv.id, "marks", e.target.value)}
                    onBlur={() => saveMarks(iv)}
                    className="w-20 h-10 px-2.5 rounded-md border border-slate-200 bg-surface text-ink-900 text-sm" />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Out of</label>
                  <input type="number" value={draftFor(iv.id).max} placeholder="100"
                    onChange={(e) => setDraft(iv.id, "max", e.target.value)}
                    onBlur={() => saveMarks(iv)}
                    className="w-20 h-10 px-2.5 rounded-md border border-slate-200 bg-surface text-ink-900 text-sm" />
                </div>
                <Button size="sm" variant="secondary" onClick={() => saveMarks(iv)}>Save marks</Button>
                <div className="flex-1" />
                <Button size="sm" variant="secondary" onClick={() => decide(iv.id, "reject")}>
                  <X size={14} /> Reject
                </Button>
                <Button size="sm" onClick={() => decide(iv.id, "select")}>
                  <Check size={14} /> Select
                </Button>
              </div>
            )}
            {iv.decision === "select" && (
              <p className="mt-3 text-sm text-teal-600 flex items-center gap-1.5">
                <UserCheck size={15} /> Recommended for offer
              </p>
            )}
            </Card>
          </li>
        ))}</ol>
      </section>
    </div></section>
  );
}
