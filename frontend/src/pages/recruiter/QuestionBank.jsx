import { useState, useEffect } from "react";
import { Plus, CheckCircle2, Wand2, Trash2, ClipboardList, Code2, ListChecks, AlertTriangle } from "lucide-react";
import { Card, Badge, Button, Field, Input } from "../../components/ui/primitives.jsx";
import { PageHeader, Loading } from "../../components/ui/states.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { api, withFallback } from "../../lib/api.js";
import "../../styles/recruiter-operations-pages.css";

const DIFF_TONE = { easy: "teal", medium: "amber", hard: "rose" };

export default function QuestionBank() {
  const loaded = useAsync(() => withFallback(api.listQuestions(), []), []);
  const [rows, setRows] = useState(null);
  const list = rows ?? loaded.data ?? [];

  if (loaded.loading) return <Loading />;

  return (
    <main className="page-composition page-composition-recruiter hire-ops hire-ops--questions"><div>
      <header className="hire-ops-intro"><div><span className="hire-ops-kicker">Hire · assessment studio</span><PageHeader
        title="Question Bank"
        subtitle="Author items, build a paper, and create an exam"
      /></div>{!loaded.live && <span role="status" className="hire-source-state">Live question data is unavailable.</span>}</header>
      <div className="hire-question-layout">
        <div className="space-y-6">
          <div className="hire-question-authoring"><Authoring onCreated={(q) => setRows([q, ...list])} /></div>
          <ExamBuilder />
        </div>
        <QuestionList
          list={list}
          onActivate={(id) => setRows(list.map((q) => (q.id === id ? { ...q, status: "active" } : q)))}
        />
      </div>

      <div className="mt-6">
        <div className="hire-question-paper"><PaperViewer /></div>
      </div>
    </div></main>
  );
}

function Authoring({ onCreated }) {
  const [form, setForm] = useState({
    type: "mcq", category: "aptitude", difficulty: "easy", stem: "", weight: 1,
  });
  const [opts, setOpts] = useState([
    { id: "a", text: "" },
    { id: "b", text: "" },
  ]);
  const [correct, setCorrect] = useState("a");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError(""); setBusy(true);
    const body = {
      type: form.type, category: form.category, difficulty: form.difficulty,
      stem: form.stem, weight: Number(form.weight),
      options: form.type === "mcq" ? opts.filter((o) => o.text) : [],
      answer_key: form.type === "mcq" ? { option: correct } : {},
    };
    try {
      const created = await api.createQuestion(body);
      onCreated(created);
      setForm({ ...form, stem: "" });
      setOpts([{ id: "a", text: "" }, { id: "b", text: "" }]);
    } catch (e) { setError(e?.message || "The question could not be saved."); }
    finally { setBusy(false); }
  }

  return (
    <Card className="hire-question-author-card p-6">
      <header className="hire-question-form-heading"><span className="hire-ops-kicker">01 · Item authoring</span><h2 className="font-display font-semibold text-ink-900"><Plus size={18} aria-hidden="true" /> Create a question</h2><p>Write a reusable item, define its answer key, and keep its difficulty visible to the team.</p></header>
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-3 gap-2">
          {[["type", ["mcq", "multi", "coding", "sql"]], ["category", ["aptitude", "technical", "verbal", "programming"]], ["difficulty", ["easy", "medium", "hard"]]].map(([key, options]) => (
            <div key={key}>
              <label className="block text-xs font-medium text-slate-500 mb-1 capitalize">{key}</label>
              <select
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                className="w-full h-10 px-2 rounded-md border border-slate-200 bg-surface text-sm text-ink-900"
              >
                {options.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
          ))}
        </div>
        <Field label="Question stem">
          <textarea
            required
            value={form.stem}
            onChange={(e) => setForm({ ...form, stem: e.target.value })}
            className="w-full min-h-[70px] p-3 rounded-md border border-slate-200 text-ink-900 text-sm"
            placeholder="Enter the question…"
          />
        </Field>
        {form.type === "mcq" && (
          <div>
            <label className="block text-sm font-medium text-ink-900 mb-1.5">Options (select correct)</label>
            <div className="space-y-2">
              {opts.map((o, i) => (
                <div key={o.id} className="flex items-center gap-2">
                  <input
                    type="radio" name="correct" checked={correct === o.id}
                    onChange={() => setCorrect(o.id)} className="accent-brand-500"
                  />
                  <span className="text-sm font-semibold text-slate-500 w-5">{o.id.toUpperCase()}</span>
                  <Input
                    value={o.text}
                    onChange={(e) => setOpts(opts.map((x) => (x.id === o.id ? { ...x, text: e.target.value } : x)))}
                    placeholder={`Option ${o.id.toUpperCase()}`}
                    className="h-9"
                  />
                  {opts.length > 2 && (
                    <button type="button" onClick={() => setOpts(opts.filter((x) => x.id !== o.id))}
                      className="text-slate-400 hover:text-rose-500"><Trash2 size={15} /></button>
                  )}
                </div>
              ))}
            </div>
            {opts.length < 4 && (
              <button
                type="button"
                onClick={() => setOpts([...opts, { id: "abcd"[opts.length], text: "" }])}
                className="mt-2 text-sm text-brand-600 hover:underline flex items-center gap-1"
              >
                <Plus size={14} /> Add option
              </button>
            )}
          </div>
        )}
        {error && <p role="alert" className="hire-question-error">{error}</p>}
        <Button type="submit" className="w-full" disabled={busy}>{busy ? "Saving…" : <><Plus size={16} /> Add question</>}</Button>
      </form>
    </Card>
  );
}

function DriveSelect({ value, onChange }) {
  const drives = useAsync(() => withFallback(api.drives(), []), []);
  const list = drives.data || [];
  return (
    <Field label="Attach to drive" hint="Applicants see the test only when it's attached to their drive.">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full h-11 px-3 rounded-md border border-slate-200 text-ink-900 bg-surface"
      >
        <option value="">— Select a drive —</option>
        {list.map((d) => (
          <option key={d.id} value={d.id}>{d.title} · {d.company_name} ({d.status})</option>
        ))}
      </select>
    </Field>
  );
}

const blankMcq = () => ({ type: "mcq", stem: "", options: [{ id: "a", text: "" }, { id: "b", text: "" }], correct: "a", weight: 1 });
const blankCoding = () => ({ type: "coding", stem: "", languages: ["python", "java", "c", "cpp", "javascript"], sample_cases: [{ input: "", expected: "" }], hidden_cases: [{ input: "", expected: "" }], weight: 5 });

// Round types that need a written question paper. Each such round in a drive
// gets its OWN paper (exam) — the builder asks for one per written round.
const WRITTEN_TYPES = ["aptitude", "technical", "verbal", "coding", "sql", "custom"];
const cap = (s) => (s || "").charAt(0).toUpperCase() + (s || "").slice(1);

// Direct exam builder — author questions straight into the exam (no separate
// pool/activation). Options + correct answers are captured here; the exam saved
// to students carries only stems+options, while the answer key goes to the
// Evaluation service for auto-grading.
function ExamBuilder() {
  const [title, setTitle] = useState("Written Test");
  const [driveId, setDriveId] = useState("");
  const [timeMin, setTimeMin] = useState(60);
  const [passPct, setPassPct] = useState(60);
  const [sections, setSections] = useState([{ title: "Aptitude", questions: [] }]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  // Written rounds of the selected drive + which one this paper is for.
  const [rounds, setRounds] = useState([]);
  const [roundId, setRoundId] = useState("");
  const [existing, setExisting] = useState([]); // exams already created for the drive

  async function reloadExisting(did) {
    setExisting(await api.listExams(did).catch(() => []));
  }

  useEffect(() => {
    if (!driveId) { setRounds([]); setRoundId(""); setExisting([]); return; }
    (async () => {
      const d = await api.drive(driveId).catch(() => null);
      setRounds((d?.rounds || []).filter((r) => WRITTEN_TYPES.includes(r.type)));
      setRoundId("");
      await reloadExisting(driveId);
    })();
  }, [driveId]);

  function pickRound(r) {
    setRoundId(r.id);
    setTitle(`${cap(r.label || r.type)} — Written Test`);
    setSections([{ title: cap(r.type), questions: [] }]);
    setResult(null);
  }

  const totalQ = sections.reduce((n, s) => n + s.questions.length, 0);
  const setSec = (i, patch) => setSections((ss) => ss.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const addQ = (i, q) => setSec(i, { questions: [...sections[i].questions, q] });
  const setQ = (i, j, patch) => setSec(i, { questions: sections[i].questions.map((q, k) => (k === j ? { ...q, ...patch } : q)) });
  const removeQ = (i, j) => setSec(i, { questions: sections[i].questions.filter((_, k) => k !== j) });

  // Refuse to publish an unusable paper. A blank stem or an MCQ with no options
  // renders as an empty card the candidate cannot answer, so these are hard
  // errors — never a warning the recruiter can click past.
  function validate() {
    const errs = [];
    if (!driveId) errs.push("Select the drive this exam belongs to.");
    if (rounds.length && !roundId) errs.push("Pick which written round this paper is for.");
    if (!totalQ) errs.push("Add at least one question.");
    sections.forEach((s, i) => {
      if (!s.questions.length) errs.push(`Section ${i + 1} (${s.title || "untitled"}) has no questions.`);
      s.questions.forEach((q, j) => {
        const at = `S${i + 1} Q${j + 1}`;
        if (!(q.stem || "").trim()) errs.push(`${at}: question text is empty.`);
        if (q.type === "coding") {
          const cases = [...(q.sample_cases || []), ...(q.hidden_cases || [])]
            .filter((c) => (c.input || "").trim() || (c.expected || "").trim());
          if (!cases.length) errs.push(`${at}: add at least one test case (it cannot be auto-graded otherwise).`);
          if (!(q.languages || []).length) errs.push(`${at}: pick at least one language.`);
        } else {
          const filled = (q.options || []).filter((o) => (o.text || "").trim());
          if (filled.length < 2) errs.push(`${at}: needs at least 2 answer options.`);
          if (!filled.some((o) => o.id === q.correct)) errs.push(`${at}: mark which option is correct.`);
        }
      });
    });
    return errs;
  }

  async function create() {
    const errs = validate();
    if (errs.length) { setResult({ errors: errs }); return; }
    setBusy(true); setResult(null);
    const examSections = sections.map((s, i) => ({
      title: s.title, order: i + 1,
      questions: s.questions.map((q, j) => q.type === "coding"
        ? { id: `q-${i}-${j}`, type: "coding", stem: q.stem, languages: q.languages, sample_cases: q.sample_cases.filter((c) => c.input || c.expected), weight: Number(q.weight) || 5 }
        : { id: `q-${i}-${j}`, type: "mcq", stem: q.stem, options: q.options.filter((o) => o.text), weight: Number(q.weight) || 1 }),
    }));
    const items = [];
    sections.forEach((s, i) => s.questions.forEach((q, j) => items.push(
      q.type === "coding"
        ? { question_id: `q-${i}-${j}`, type: "coding", correct: {}, weight: Number(q.weight) || 5,
            // all cases (sample + hidden) drive auto-grading; students only see samples.
            cases: [...(q.sample_cases || []), ...(q.hidden_cases || [])].filter((c) => c.input || c.expected),
            language: (q.languages && q.languages[0]) || "python" }
        : { question_id: `q-${i}-${j}`, type: "mcq", correct: { option: q.correct }, weight: Number(q.weight) || 1 })));
    try {
      const exam = await api.createExam({ title, drive_id: driveId, round_id: roundId || null, total_time_min: Number(timeMin), sections: examSections });
      await api.upsertEvalKey({ exam_id: exam.id, items, passing_pct: Number(passPct) }).catch(() => {});
      setResult({ id: exam.id, title: exam.title });
      await reloadExisting(driveId);           // mark this round as done (green tick)
      setRoundId("");                          // ready to pick the next round
    } catch (e) {
      setResult({ error: e?.message || "Could not create exam — check the fields." });
    } finally { setBusy(false); }
  }

  return (
    <Card className="hire-exam-builder p-6">
      <header className="hire-exam-builder-heading"><span className="hire-ops-kicker">02 · Exam assembly</span><h2 className="font-display font-semibold text-ink-900"><Wand2 size={18} aria-hidden="true" /> Assemble written paper</h2><p>Choose a drive and round, then organize sections and grading rules before publication.</p></header>
      <div className="hire-exam-settings grid sm:grid-cols-2 gap-3">
        <Field label="Exam title"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Time (min)"><Input type="number" value={timeMin} onChange={(e) => setTimeMin(e.target.value)} /></Field>
          <Field label="Pass %"><Input type="number" value={passPct} onChange={(e) => setPassPct(e.target.value)} /></Field>
        </div>
      </div>
      <DriveSelect value={driveId} onChange={setDriveId} />

      {/* One paper per written round — dynamic to the drive's pipeline. */}
      {driveId && rounds.length > 0 && (
        <div className="mt-4 rounded-lg border border-brand-200 bg-brand-500/[0.04] p-4">
          <p className="text-xs font-semibold text-ink-900 mb-2 flex items-center gap-1.5">
            <ClipboardList size={14} className="text-brand-500" />
            Attach a question paper for each written round ({rounds.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {rounds.map((r) => {
              const hasPaper = existing.some((e) => e.round_id === r.id);
              const active = roundId === r.id;
              return (
                <button key={r.id} onClick={() => pickRound(r)}
                  className={`h-9 px-3 rounded-md text-sm font-medium border transition-colors ${
                    active ? "bg-invert-900 text-white border-invert-900"
                      : "bg-surface border-slate-200 text-slate-600 hover:bg-slate-50"}`}>
                  {r.order}. {cap(r.label || r.type)}
                  {hasPaper && <CheckCircle2 size={13} className="inline ml-1.5 text-teal-500 -mt-0.5" />}
                </button>
              );
            })}
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            {roundId ? "Building the paper for the selected round — save it, then pick the next round."
              : "Pick a round to build its paper. A green tick means that round already has a paper."}
          </p>
        </div>
      )}

      <div className="mt-4 space-y-4">
        {sections.map((sec, i) => (
          <div key={i} className="rounded-lg border border-slate-200 p-3">
            <div className="flex items-center gap-2 mb-2">
              <ListChecks size={15} className="text-brand-500" />
              <Input value={sec.title} onChange={(e) => setSec(i, { title: e.target.value })} className="h-9 flex-1" placeholder="Section name (e.g. Aptitude / Coding / Verbal)" />
              {sections.length > 1 && (
                <button onClick={() => setSections((ss) => ss.filter((_, j) => j !== i))} className="text-slate-300 hover:text-rose-500"><Trash2 size={15} /></button>
              )}
            </div>

            <div className="space-y-3">
              {sec.questions.map((q, j) => (
                <div key={j} className="rounded-md bg-slate-50 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <Badge tone={q.type === "coding" ? "amber" : "brand"}>{q.type === "coding" ? "Coding" : "MCQ"}</Badge>
                    <button onClick={() => removeQ(i, j)} className="text-slate-300 hover:text-rose-500"><Trash2 size={14} /></button>
                  </div>
                  <textarea value={q.stem} onChange={(e) => setQ(i, j, { stem: e.target.value })} placeholder="Question…"
                    className="w-full min-h-[52px] p-2 rounded-md border border-slate-200 text-sm text-ink-900" />
                  {q.type === "mcq" ? (
                    <div className="mt-2 space-y-1.5">
                      {q.options.map((o, k) => (
                        <div key={o.id} className="flex items-center gap-2">
                          <input type="radio" name={`c-${i}-${j}`} checked={q.correct === o.id} onChange={() => setQ(i, j, { correct: o.id })} className="accent-teal-500" title="Correct answer" />
                          <span className="text-xs font-semibold text-slate-400 w-4">{o.id.toUpperCase()}</span>
                          <Input value={o.text} onChange={(e) => setQ(i, j, { options: q.options.map((x) => (x.id === o.id ? { ...x, text: e.target.value } : x)) })} className="h-8" placeholder={`Option ${o.id.toUpperCase()}`} />
                          {q.options.length > 2 && <button onClick={() => setQ(i, j, { options: q.options.filter((x) => x.id !== o.id) })} className="text-slate-300 hover:text-rose-500"><Trash2 size={13} /></button>}
                        </div>
                      ))}
                      {q.options.length < 4 && (
                        <button onClick={() => setQ(i, j, { options: [...q.options, { id: "abcd"[q.options.length], text: "" }] })} className="text-xs text-brand-600 hover:underline flex items-center gap-1"><Plus size={12} /> Add option</button>
                      )}
                      <p className="text-[11px] text-slate-400">Select the radio next to the correct option.</p>
                    </div>
                  ) : (
                    <div className="mt-2 space-y-3">
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium text-slate-500 flex items-center gap-1"><Code2 size={12} /> Sample cases <span className="text-slate-400 font-normal">(shown to students)</span></p>
                        {q.sample_cases.map((c, k) => (
                          <div key={k} className="grid grid-cols-2 gap-2">
                            <Input value={c.input} onChange={(e) => setQ(i, j, { sample_cases: q.sample_cases.map((x, m) => (m === k ? { ...x, input: e.target.value } : x)) })} className="h-8 font-mono text-xs" placeholder="input" />
                            <Input value={c.expected} onChange={(e) => setQ(i, j, { sample_cases: q.sample_cases.map((x, m) => (m === k ? { ...x, expected: e.target.value } : x)) })} className="h-8 font-mono text-xs" placeholder="expected output" />
                          </div>
                        ))}
                        <button onClick={() => setQ(i, j, { sample_cases: [...q.sample_cases, { input: "", expected: "" }] })} className="text-xs text-brand-600 hover:underline flex items-center gap-1"><Plus size={12} /> Add sample</button>
                      </div>
                      <div className="space-y-1.5 rounded-md bg-amber-500/5 border border-amber-200 p-2">
                        <p className="text-xs font-medium text-amber-700 flex items-center gap-1"><Code2 size={12} /> Hidden cases <span className="text-amber-600/70 font-normal">(for grading — never shown)</span></p>
                        {(q.hidden_cases || []).map((c, k) => (
                          <div key={k} className="grid grid-cols-2 gap-2">
                            <Input value={c.input} onChange={(e) => setQ(i, j, { hidden_cases: q.hidden_cases.map((x, m) => (m === k ? { ...x, input: e.target.value } : x)) })} className="h-8 font-mono text-xs" placeholder="input" />
                            <Input value={c.expected} onChange={(e) => setQ(i, j, { hidden_cases: q.hidden_cases.map((x, m) => (m === k ? { ...x, expected: e.target.value } : x)) })} className="h-8 font-mono text-xs" placeholder="expected output" />
                          </div>
                        ))}
                        <button onClick={() => setQ(i, j, { hidden_cases: [...(q.hidden_cases || []), { input: "", expected: "" }] })} className="text-xs text-amber-700 hover:underline flex items-center gap-1"><Plus size={12} /> Add hidden</button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="flex gap-2 mt-3">
              <Button size="sm" variant="secondary" onClick={() => addQ(i, blankMcq())}><Plus size={14} /> MCQ</Button>
              <Button size="sm" variant="secondary" onClick={() => addQ(i, blankCoding())}><Code2 size={14} /> Coding</Button>
            </div>

            <AIGenerate onAdd={(qs) => setSec(i, { questions: [...sections[i].questions, ...qs] })} />
          </div>
        ))}
      </div>

      <button onClick={() => setSections((ss) => [...ss, { title: "New Section", questions: [] }])}
        className="mt-3 text-sm text-brand-600 hover:underline flex items-center gap-1"><Plus size={14} /> Add section</button>

      <div className="mt-4">
        <Button onClick={create} disabled={busy || !driveId || totalQ === 0} title={!driveId ? "Select a drive" : totalQ === 0 ? "Add at least one question" : ""}>
          <ClipboardList size={16} /> {busy ? "Creating…" : `Create exam (${totalQ} questions)`}
        </Button>
      </div>

      {result?.error && (
        <div className="mt-3 rounded-md bg-rose-500/10 text-rose-700 p-3 text-sm flex items-center gap-2"><AlertTriangle size={15} /> {result.error}</div>
      )}
      {result?.errors?.length > 0 && (
        <div className="mt-3 rounded-md bg-rose-500/10 text-rose-700 p-3 text-sm">
          <p className="flex items-center gap-2 font-medium">
            <AlertTriangle size={15} /> Fix these before publishing — students would see blank questions:
          </p>
          <ul className="mt-2 ml-6 list-disc space-y-1">
            {result.errors.map((e) => <li key={e}>{e}</li>)}
          </ul>
        </div>
      )}
      {result?.id && (
        <div className="mt-3 rounded-md bg-teal-500/10 text-teal-700 p-3 text-sm flex items-center gap-2">
          <CheckCircle2 size={15} /> Exam “{result.title}” created & attached — applicants can now start it.
        </div>
      )}
    </Card>
  );
}

// Per-section AI drafting. Asks Gemini for exam-ready questions, then appends
// them to the section as normal editable rows — the recruiter reviews/edits and
// nothing is saved until they hit "Create exam". The backend already validates
// and drops any malformed question, so blanks can never slip through.
function AIGenerate({ onAdd }) {
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState("");
  const [type, setType] = useState("mcq");
  const [difficulty, setDifficulty] = useState("medium");
  const [count, setCount] = useState(5);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function run() {
    if (!topic.trim()) { setErr("Enter a topic first."); return; }
    setBusy(true); setErr("");
    try {
      const r = await api.generateQuestions({
        topic: topic.trim(), type, difficulty, count: Number(count),
        category: type === "coding" ? "programming" : "aptitude",
      });
      const qs = (r.questions || []).map((q) => q.type === "coding"
        ? { type: "coding", stem: q.stem, languages: q.languages || ["python", "java", "c", "cpp", "javascript"],
            sample_cases: q.sample_cases?.length ? q.sample_cases : [{ input: "", expected: "" }],
            hidden_cases: q.hidden_cases || [], weight: q.weight || 5 }
        : { type: "mcq", stem: q.stem, options: q.options, correct: q.correct, weight: q.weight || 1 });
      if (!qs.length) { setErr("No usable questions came back — try a more specific topic."); return; }
      onAdd(qs);
      setOpen(false); setTopic("");
    } catch (e) {
      // The server sends a specific reason (quota hit / provider error / not
      // configured) — show it verbatim rather than a generic message.
      setErr(e?.message || "Generation failed — please try again.");
    } finally { setBusy(false); }
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)}
        className="mt-2 text-sm text-violet-600 hover:underline flex items-center gap-1">
        <Wand2 size={14} /> Generate with AI
      </button>
    );
  }
  return (
    <div className="mt-3 rounded-md border border-violet-200 bg-violet-500/5 p-3 space-y-2">
      <p className="text-xs font-medium text-violet-700 flex items-center gap-1"><Wand2 size={13} /> Generate questions with AI</p>
      <Input value={topic} onChange={(e) => setTopic(e.target.value)} className="h-9"
        placeholder="Topic — e.g. Time & Work, Arrays, Reading Comprehension" />
      <div className="grid grid-cols-3 gap-2">
        <select value={type} onChange={(e) => setType(e.target.value)} className="h-9 rounded-md border border-slate-200 text-sm px-2">
          <option value="mcq">MCQ</option>
          <option value="coding">Coding</option>
        </select>
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="h-9 rounded-md border border-slate-200 text-sm px-2">
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
        <Input type="number" min={1} max={15} value={count} onChange={(e) => setCount(e.target.value)} className="h-9" title="How many" />
      </div>
      {err && <p className="text-xs text-rose-600">{err}</p>}
      <div className="flex gap-2">
        <Button size="sm" onClick={run} disabled={busy}><Wand2 size={13} /> {busy ? "Generating…" : "Generate"}</Button>
        <Button size="sm" variant="secondary" onClick={() => { setOpen(false); setErr(""); }} disabled={busy}>Cancel</Button>
      </div>
    </div>
  );
}

// Admin question-paper viewer: pick a drive → its exams → view the full paper
// with the correct answers highlighted (MCQ) and coding test cases shown.
function PaperViewer() {
  const [driveId, setDriveId] = useState("");
  const [exams, setExams] = useState([]);
  const [rounds, setRounds] = useState([]);
  const [paper, setPaper] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setPaper(null); setExams([]); setRounds([]);
    if (!driveId) return;
    api.listExams(driveId).then((r) => setExams(r || [])).catch(() => setExams([]));
    api.drive(driveId).then((d) => setRounds(d?.rounds || [])).catch(() => setRounds([]));
  }, [driveId]);

  async function view(eid) {
    setBusy(true); setPaper(null);
    try { setPaper(await api.examPaper(eid)); }
    catch (e) { setPaper({ error: e?.message || "Could not load the paper." }); }
    finally { setBusy(false); }
  }

  async function del(eid) {
    if (!window.confirm("Delete this question paper? This cannot be undone.")) return;
    await api.deleteExam(eid).catch(() => {});
    setExams((xs) => xs.filter((x) => x.id !== eid));
    setPaper(null);
  }

  return (
    <Card className="hire-question-paper-viewer p-6">
      <h2 className="font-display font-semibold text-ink-900 mb-1 flex items-center gap-2">
        <ClipboardList size={18} className="text-brand-500" /> View question paper &amp; answers
      </h2>
      <p className="text-sm text-slate-500 mb-4">Pick a drive and an exam to review its questions with the correct answers.</p>
      <DriveSelect value={driveId} onChange={setDriveId} />

      {exams.length > 0 && (
        <div className="mt-4 space-y-3">
          {[...rounds, { id: null, label: "Other / unlinked papers", type: "" }].map((r) => {
            const roundIds = new Set(rounds.map((x) => x.id));
            // The catch-all group also collects orphans: a round_id that no longer
            // matches any round in the pipeline (e.g. after re-saving it).
            const rExams = r.id
              ? exams.filter((e) => e.round_id === r.id)
              : exams.filter((e) => !e.round_id || !roundIds.has(e.round_id));
            if (!rExams.length) return null;
            return (
              <div key={r.id || "other"}>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">
                  {r.id ? `${r.order}. ${cap(r.label || r.type)}` : "Other papers"}
                </p>
                <div className="flex flex-wrap gap-2">
                  {rExams.map((ex) => (
                    <div key={ex.id} className="inline-flex items-center rounded-md border border-slate-200 overflow-hidden">
                      <button onClick={() => view(ex.id)}
                        className="h-8 px-3 text-sm text-slate-600 hover:bg-slate-50 inline-flex items-center gap-1.5">
                        <ClipboardList size={14} /> {ex.title} ({ex.sections} sec)
                      </button>
                      <button onClick={() => del(ex.id)} title="Delete this paper"
                        className="h-8 px-2 border-l border-slate-200 text-slate-300 hover:text-rose-500 hover:bg-rose-50">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {driveId && exams.length === 0 && <p className="mt-3 text-sm text-slate-400">No exams for this drive yet.</p>}
      {busy && <p className="mt-4 text-sm text-slate-400">Loading paper…</p>}
      {paper?.error && <p className="mt-4 text-sm text-rose-600">{paper.error}</p>}

      {paper && !paper.error && (
        <div className="mt-5 space-y-5">
          <h3 className="font-display font-semibold text-ink-900">{paper.title} · {paper.total_time_min} min</h3>
          {paper.sections.map((sec, si) => (
            <div key={si} className="rounded-lg border border-slate-200 p-4">
              <p className="text-sm font-semibold text-brand-600 mb-3">Section {si + 1}: {sec.title}</p>
              <ol className="space-y-4">
                {sec.questions.map((q, qi) => (
                  <li key={q.id || qi} className="text-sm">
                    <div className="flex items-start gap-2">
                      <span className="text-slate-400">Q{qi + 1}.</span>
                      <div className="flex-1">
                        <p className="font-medium text-ink-900 whitespace-pre-wrap">{q.stem}</p>
                        <Badge tone={q.type === "coding" ? "amber" : "slate"} className="mt-1">{q.type === "coding" ? "Coding" : "MCQ"}</Badge>
                        {q.type !== "coding" ? (
                          <div className="mt-2 space-y-1">
                            {(q.options || []).map((o) => {
                              const oid = o.id, text = o.text;
                              const isCorrect = q.correct && q.correct.option === oid;
                              return (
                                <div key={oid} className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md border ${isCorrect ? "border-teal-400 bg-teal-500/10" : "border-slate-200"}`}>
                                  <span className="text-xs font-semibold text-slate-400 w-4">{String(oid).toUpperCase()}</span>
                                  <span className={isCorrect ? "text-teal-700 font-medium" : "text-slate-700"}>{text}</span>
                                  {isCorrect && <CheckCircle2 size={14} className="text-teal-600 ml-auto" />}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="mt-2 space-y-1">
                            <p className="text-xs font-medium text-slate-500">Test cases (used to grade):</p>
                            {(q.cases || []).map((c, ci) => (
                              <div key={ci} className="grid grid-cols-2 gap-2 font-mono text-xs">
                                <span className="rounded bg-slate-50 px-2 py-1 truncate" title={c.input}>in: {c.input}</span>
                                <span className="rounded bg-slate-50 px-2 py-1 truncate" title={c.expected}>out: {c.expected}</span>
                              </div>
                            ))}
                            {!(q.cases || []).length && <p className="text-xs text-slate-400">No test cases stored.</p>}
                          </div>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function QuestionList({ list, onActivate }) {
  const [error, setError] = useState("");
  async function activate(id) {
    setError("");
    try { await api.activateQuestion(id); onActivate(id); }
    catch (e) { setError(e?.message || "This question could not be activated."); }
  }
  return (
    <Card className="p-0 overflow-hidden">
      <header className="hire-question-bank-heading p-5 border-b border-slate-100">
        <div><span className="hire-ops-kicker">Item library</span><h2 className="font-display font-semibold text-ink-900">Questions</h2></div><span className="hire-question-count">{list.length}</span>
      </header>
      {error && <p role="alert" className="hire-question-error mx-5 mt-4">{error}</p>}
      <ol className="hire-question-records divide-y divide-slate-100">
        {list.map((q) => (
          <li key={q.id} className="hire-question-record p-4 flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink-900 truncate">{q.stem}</p>
              <div className="flex gap-1.5 mt-1">
                <Badge tone="slate">{q.type}</Badge>
                <Badge tone="brand">{q.category}</Badge>
                <Badge tone={DIFF_TONE[q.difficulty] || "slate"}>{q.difficulty}</Badge>
              </div>
            </div>
            {q.status === "active" ? (
              <Badge tone="teal"><CheckCircle2 size={13} /> active</Badge>
            ) : (
              <Button size="sm" variant="secondary" onClick={() => activate(q.id)}>Activate</Button>
            )}
          </li>
        ))}
        {list.length === 0 && <li className="p-6 text-sm text-slate-400">No questions yet — author one on the left.</li>}
      </ol>
    </Card>
  );
}
