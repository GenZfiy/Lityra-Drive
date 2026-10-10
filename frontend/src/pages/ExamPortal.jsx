import "../styles/learner-candidate-pages.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Clock, ShieldCheck, ChevronRight, CheckCircle2, AlertTriangle, Eye, ShieldAlert,
  ArrowLeft, Code2, Terminal, Play, Calculator as CalcIcon, X,
} from "lucide-react";
import { Card, Badge, Button } from "../components/ui/primitives.jsx";

import { api } from "../lib/api.js";
import { attachProctoring, SIGNAL_LABEL } from "../lib/proctor.js";

// Proctored exam experience. Wires to the live Exam Engine (start → server
// timer → save → submit) with a demo paper fallback, and reports proctoring
// signals to the Anti-Cheating service. Auto-submits on the violation threshold.
const DEMO_EXAM = {
  id: "exam-demo",
  title: "TCS NQT — Mock Assessment",
  total_time_min: 3,
  sections: [
    {
      id: "s1",
      title: "Aptitude",
      questions: [
        { id: "q1", stem: "What is 12 × 8?", options: [["a", "84"], ["b", "96"], ["c", "108"]] },
        { id: "q2", stem: "Next in series: 2, 6, 12, 20, ?", options: [["a", "28"], ["b", "30"], ["c", "32"]] },
      ],
    },
    {
      id: "s2",
      title: "Logical Reasoning",
      questions: [{ id: "q3", stem: "If CAT = 24, DOG = 26, then PIG = ?", options: [["a", "28"], ["b", "32"], ["c", "35"]] }],
    },
  ],
};
const VIOLATION_LIMIT = 5; // 5 flags → auto-submit (backend also decides via weighted score)

const TYPE_LABEL = {
  mcq: "MCQ", multi: "Multi-select", true_false: "True / False",
  coding: "Coding", sql: "SQL", verbal: "Verbal", assertion: "Assertion–Reason",
  fill_blank: "Fill in the blank", match: "Match", output: "Predict output",
};

const LANGS = ["python", "java", "c", "cpp", "javascript"];
const LANG_LABEL = { python: "Python", java: "Java", c: "C", cpp: "C++", javascript: "JavaScript" };

// Code question: language + editor + Run against sample cases + capture answer.
// Hidden-case grading still happens server-side on submit.
function CodeAnswer({ q, answer, onSave }) {
  const [code, setCode] = useState(answer?.code || q.starter || "");
  const allowed = q.languages && q.languages.length ? q.languages : LANGS;
  const [avail, setAvail] = useState(null); // languages actually runnable on the server
  const [lang, setLang] = useState(answer?.language || allowed[0] || "python");
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState(null);

  // Only offer languages the server can actually run (via /coding/languages).
  useEffect(() => {
    let alive = true;
    api.codingLanguages()
      .then((r) => { if (alive) setAvail(Object.entries(r.languages || {}).filter(([, v]) => v).map(([k]) => k)); })
      .catch(() => { if (alive) setAvail(null); });
    return () => { alive = false; };
  }, []);

  const langs = avail ? allowed.filter((l) => avail.includes(l)) : allowed;
  const effLangs = langs.length ? langs : allowed;

  async function doRun() {
    onSave({ code, language: lang });
    setRunning(true); setRun(null);
    try {
      setRun(await api.runCode(lang, code, q.sample_cases || []));
    } catch (e) {
      setRun({ error: e?.message || "Run failed" });
    } finally { setRunning(false); }
  }

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-slate-500 flex items-center gap-1.5"><Code2 size={14} /> Write your solution</span>
        <select value={lang} onChange={(e) => { setLang(e.target.value); onSave({ code, language: e.target.value }); }}
          className="h-8 px-2 rounded-md border border-slate-200 text-xs bg-surface">
          {effLangs.map((l) => <option key={l} value={l}>{LANG_LABEL[l] || l}</option>)}
        </select>
      </div>
      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        onBlur={() => onSave({ code, language: lang })}
        spellCheck={false}
        className="w-full min-h-[190px] p-3 rounded-md border border-slate-200 font-mono text-sm text-ink-900 bg-slate-50 focus:bg-surface"
        placeholder="// write your code here"
      />

      <div className="flex items-center gap-2 mt-2">
        <Button size="sm" variant="secondary" onClick={doRun} disabled={running}>
          <Play size={14} /> {running ? "Running…" : "Run sample tests"}
        </Button>
        {run && !run.error && (
          <Badge tone={run.passed === run.total ? "teal" : "rose"}>
            {run.passed}/{run.total} passed
          </Badge>
        )}
      </div>

      {run?.error && (
        <p className="mt-2 text-xs text-rose-600">{run.error}</p>
      )}
      {run?.compile_failed && (
        <pre className="mt-2 text-xs bg-rose-500/10 text-rose-700 p-2 rounded-md whitespace-pre-wrap overflow-x-auto">{run.compile_log || "Compilation failed"}</pre>
      )}

      {(run?.cases || q.sample_cases || []).length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-slate-500 mb-1.5 flex items-center gap-1.5"><Terminal size={13} /> Sample test cases</p>
          <div className="space-y-1.5">
            {(run?.cases || (q.sample_cases || []).map((c) => ({ ...c }))).map((c, i) => (
              <div key={i} className={`rounded p-2 text-xs font-mono ${run?.cases ? (c.passed ? "bg-teal-500/10" : "bg-rose-500/10") : "bg-slate-100"}`}>
                <div className="grid grid-cols-2 gap-2">
                  <div><span className="text-slate-400">in » </span>{c.input}</div>
                  <div><span className="text-slate-400">expected » </span>{c.expected}</div>
                </div>
                {run?.cases && (
                  <div className="mt-1 flex items-center gap-2">
                    {c.passed
                      ? <span className="text-teal-600 flex items-center gap-1"><CheckCircle2 size={12} /> passed</span>
                      : <span className="text-rose-600 flex items-center gap-1"><AlertTriangle size={12} /> {c.timed_out ? "time limit" : "got: " + (c.stdout || "(no output)").trim()}</span>}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      <p className="text-xs text-slate-400 mt-2">Saved automatically · evaluated against hidden test cases on submit.</p>
    </div>
  );
}

function fmt(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Safe scientific expression evaluator (no eval). Tokenises the button-built
// expression, converts to RPN with a shunting-yard, then evaluates. Supports
// + − × ÷, powers (^), √, brackets, unary minus, π and e.
function evalExpr(input) {
  const s = String(input)
    .replace(/×/g, "*").replace(/÷/g, "/").replace(/−/g, "-")
    .replace(/π/g, `(${Math.PI})`).replace(/(?<![a-z])e(?![a-z])/g, `(${Math.E})`)
    .replace(/√/g, "sqrt");
  const toks = [];
  let i = 0;
  const isD = (c) => (c >= "0" && c <= "9");
  while (i < s.length) {
    const c = s[i];
    if (c === " ") { i++; continue; }
    if (isD(c) || c === ".") {
      let n = ""; while (i < s.length && (isD(s[i]) || s[i] === ".")) { n += s[i++]; }
      toks.push({ t: "num", v: parseFloat(n) }); continue;
    }
    if (/[a-z]/i.test(c)) { let f = ""; while (i < s.length && /[a-z]/i.test(s[i])) { f += s[i++]; } toks.push({ t: "fn", v: f }); continue; }
    if ("+-*/^".includes(c)) { toks.push({ t: "op", v: c }); i++; continue; }
    if (c === "(") { toks.push({ t: "lp" }); i++; continue; }
    if (c === ")") { toks.push({ t: "rp" }); i++; continue; }
    throw new Error("bad");
  }
  // mark unary minus
  const m = [];
  for (const tk of toks) {
    if (tk.t === "op" && tk.v === "-") {
      const p = m[m.length - 1];
      m.push(!p || p.t === "op" || p.t === "lp" || p.t === "fn" ? { t: "op", v: "u" } : tk);
    } else m.push(tk);
  }
  const prec = { u: 5, "^": 4, "*": 3, "/": 3, "+": 2, "-": 2 };
  const right = { "^": 1, u: 1 };
  const out = [], ops = [];
  for (const tk of m) {
    if (tk.t === "num") out.push(tk);
    else if (tk.t === "fn") ops.push(tk);
    else if (tk.t === "op") {
      while (ops.length) {
        const top = ops[ops.length - 1];
        if (top.t === "fn" || (top.t === "op" && (prec[top.v] > prec[tk.v] || (prec[top.v] === prec[tk.v] && !right[tk.v])))) out.push(ops.pop());
        else break;
      }
      ops.push(tk);
    } else if (tk.t === "lp") ops.push(tk);
    else if (tk.t === "rp") {
      while (ops.length && ops[ops.length - 1].t !== "lp") out.push(ops.pop());
      if (!ops.length) throw new Error("paren");
      ops.pop();
      if (ops.length && ops[ops.length - 1].t === "fn") out.push(ops.pop());
    }
  }
  while (ops.length) { const o = ops.pop(); if (o.t === "lp") throw new Error("paren"); out.push(o); }
  const st = [];
  const fns = { sqrt: Math.sqrt, sin: Math.sin, cos: Math.cos, tan: Math.tan, log: Math.log10, ln: Math.log, abs: Math.abs };
  for (const tk of out) {
    if (tk.t === "num") st.push(tk.v);
    else if (tk.t === "op" && tk.v === "u") st.push(-st.pop());
    else if (tk.t === "op") {
      const b = st.pop(), a = st.pop();
      st.push(tk.v === "+" ? a + b : tk.v === "-" ? a - b : tk.v === "*" ? a * b : tk.v === "/" ? a / b : Math.pow(a, b));
    } else if (tk.t === "fn") {
      const f = fns[tk.v]; if (!f) throw new Error("fn");
      st.push(f(st.pop()));
    }
  }
  if (st.length !== 1 || !isFinite(st[0])) throw new Error("eval");
  return Math.round(st[0] * 1e10) / 1e10;
}

// In-exam scientific calculator: √, x², powers, brackets, π — for quantitative
// drives. Expression-based (safe evaluator, no eval — only its own buttons feed
// it). Fixed bottom-right, toggled from the exam header.
function Calculator({ onClose }) {
  const [expr, setExpr] = useState("");
  const [result, setResult] = useState("0");
  const [done, setDone] = useState(false); // last press was "="

  function push(val, kind) {
    let base = expr;
    if (done) { base = kind === "op" ? result : ""; setDone(false); }
    setExpr(base + val);
  }
  function equals() {
    try { setResult(String(evalExpr(expr || "0"))); setDone(true); }
    catch { setResult("Error"); setDone(true); }
  }
  const clearAll = () => { setExpr(""); setResult("0"); setDone(false); };
  const back = () => { if (!done) setExpr(expr.slice(0, -1)); };

  const main = done ? result : (expr || "0");
  const sub = done ? expr : "";

  const B = ({ children, onClick, cls = "" }) => (
    <button onClick={onClick}
      className={`h-10 rounded-md text-sm font-medium active:scale-95 transition ${cls || "bg-slate-100 hover:bg-slate-200 text-ink-900"}`}>
      {children}
    </button>
  );
  const opc = "bg-brand-500/10 text-brand-600 hover:bg-brand-500/20";
  const fnc = "bg-amber-500/10 text-amber-700 hover:bg-amber-500/20";

  return (
    <div className="fixed bottom-6 right-6 z-50 w-72 rounded-xl border border-slate-200 bg-surface shadow-lift p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-slate-500 flex items-center gap-1"><CalcIcon size={13} /> Scientific calculator</span>
        <button onClick={onClose} className="text-slate-400 hover:text-ink-900" title="Close"><X size={15} /></button>
      </div>
      <div className="mb-2 rounded-md bg-invert-900 text-white px-3 py-2 text-right">
        <div className="h-4 text-xs text-slate-400 truncate">{sub}</div>
        <div className="font-display text-2xl tabular-nums truncate">{main}</div>
      </div>
      <div className="grid grid-cols-5 gap-1.5">
        <B onClick={clearAll} cls="bg-rose-500/10 text-rose-600 hover:bg-rose-500/20">C</B>
        <B onClick={() => push("(", "open")} cls={fnc}>(</B>
        <B onClick={() => push(")", "op")} cls={fnc}>)</B>
        <B onClick={() => push("√(", "fn")} cls={fnc}>√</B>
        <B onClick={back} cls="bg-slate-200 hover:bg-slate-300">⌫</B>

        <B onClick={() => push("7", "num")}>7</B>
        <B onClick={() => push("8", "num")}>8</B>
        <B onClick={() => push("9", "num")}>9</B>
        <B onClick={() => push("^2", "op") } cls={fnc}>x²</B>
        <B onClick={() => push("÷", "op")} cls={opc}>÷</B>

        <B onClick={() => push("4", "num")}>4</B>
        <B onClick={() => push("5", "num")}>5</B>
        <B onClick={() => push("6", "num")}>6</B>
        <B onClick={() => push("^", "op")} cls={fnc}>xʸ</B>
        <B onClick={() => push("×", "op")} cls={opc}>×</B>

        <B onClick={() => push("1", "num")}>1</B>
        <B onClick={() => push("2", "num")}>2</B>
        <B onClick={() => push("3", "num")}>3</B>
        <B onClick={() => push("π", "num")} cls={fnc}>π</B>
        <B onClick={() => push("−", "op")} cls={opc}>−</B>

        <B onClick={() => push("0", "num")}>0</B>
        <B onClick={() => push(".", "num")}>.</B>
        <B onClick={equals} cls="col-span-2 bg-invert-900 text-white hover:bg-invert-800">=</B>
        <B onClick={() => push("+", "op")} cls={opc}>+</B>
      </div>
    </div>
  );
}

// The drive test — launched from a drive (/drive/test/:examId). Shows the
// instructions/precautions gate first, then the proctored, sectioned paper.
export default function ExamPortal() {
  const { examId } = useParams();
  const nav = useNavigate();
  const [live, setLive] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);

  async function begin() {
    setError(null);
    setStarting(true);
    try {
      const s = await api.examStart(examId);
      setLive({ sessionId: s.session_id, exam: s });
    } catch (e) {
      setError(e?.message || "Could not start the test. Please contact your coordinator.");
    } finally {
      setStarting(false);
    }
  }

  if (live) return <Runner live={live} onExit={() => nav("/drive")} />;
  return <div className="page-composition page-composition-candidate learner-screen-exam-portal"><Instructions onAgree={begin} onBack={() => nav("/drive")} error={error} starting={starting} /></div>;
}

const DOS = [
  "Ensure a stable internet connection and sufficient battery/power.",
  "Keep a valid photo ID ready if asked by the proctor.",
  "Stay in full-screen — the timer is server-controlled and keeps running.",
  "Answer within the section; you can revisit questions until you submit.",
];
const DONTS = [
  "Do NOT switch tabs, minimise, or leave full-screen — each is recorded.",
  "Do NOT copy, paste, or right-click during the test.",
  "Do NOT open developer tools or take screenshots.",
  "Do NOT refresh or close the window — your session will be flagged.",
];

function Instructions({ onAgree, onBack, error, starting }) {
  const [agreed, setAgreed] = useState(false);
  return (
    <div className="max-w-3xl mx-auto">
      <button onClick={onBack} className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink-900 mb-4">
        <ArrowLeft size={15} /> Back to my drives
      </button>
      <Card className="p-6 lg:p-8">
        <div className="flex items-center gap-3">
          <span className="grid place-items-center h-12 w-12 rounded-lg bg-amber-500/15 text-amber-600">
            <ShieldCheck size={26} />
          </span>
          <div>
            <h1 className="text-xl font-display font-bold text-ink-900">Before you start</h1>
            <p className="text-slate-500 text-sm">This is a proctored, timed assessment. Read the instructions carefully.</p>
          </div>
        </div>

        {error && (
          <div className="mt-5 rounded-md bg-rose-500/10 text-rose-700 p-3 text-sm flex items-center gap-2">
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        <div className="grid sm:grid-cols-2 gap-4 mt-6">
          <div className="rounded-lg border border-teal-200 bg-teal-500/5 p-4">
            <p className="font-semibold text-teal-700 flex items-center gap-2 mb-2"><CheckCircle2 size={16} /> Do</p>
            <ul className="space-y-1.5">
              {DOS.map((t) => <li key={t} className="text-sm text-slate-600 flex gap-2"><span className="text-teal-500 mt-0.5">•</span>{t}</li>)}
            </ul>
          </div>
          <div className="rounded-lg border border-rose-200 bg-rose-500/5 p-4">
            <p className="font-semibold text-rose-700 flex items-center gap-2 mb-2"><ShieldAlert size={16} /> Don't</p>
            <ul className="space-y-1.5">
              {DONTS.map((t) => <li key={t} className="text-sm text-slate-600 flex gap-2"><span className="text-rose-500 mt-0.5">•</span>{t}</li>)}
            </ul>
          </div>
        </div>

        <label className="mt-6 flex items-start gap-3 cursor-pointer">
          <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="mt-1 accent-brand-500 h-4 w-4" />
          <span className="text-sm text-ink-900">
            I have read and understood the instructions above. I agree to be monitored and understand that
            violations may auto-submit my test.
          </span>
        </label>

        <Button className="mt-6" size="lg" disabled={!agreed || starting} onClick={onAgree}>
          {starting ? "Starting…" : "Start test"} <ChevronRight size={18} />
        </Button>
      </Card>
    </div>
  );
}

function Runner({ exam: demoExam, live, onExit }) {
  // Normalize live vs demo shape.
  const exam = live ? { ...live.exam, sections: live.exam.sections } : demoExam;
  const sessionId = live?.sessionId || null;
  const totalSec = (exam.total_time_min || 3) * 60;

  const [remaining, setRemaining] = useState(
    live?.exam?.remaining_sec != null ? live.exam.remaining_sec : totalSec,
  );
  const [answers, setAnswers] = useState(live?.exam?.answers || {});
  const [secIdx, setSecIdx] = useState(0);
  const [submitted, setSubmitted] = useState(null);
  const [violations, setViolations] = useState(0);
  const [log, setLog] = useState([]);
  const [toast, setToast] = useState(null);
  const [showCalc, setShowCalc] = useState(false);
  const timer = useRef();
  const vRef = useRef(0);
  const submittedRef = useRef(false); // one-shot guard: stops counting/submitting twice

  const flat = useMemo(
    () => exam.sections.flatMap((s) => s.questions.map((q) => q.id)),
    [exam],
  );

  // ----- proctoring -----
  useEffect(() => {
    // Best-effort: register a proctor session with the backend.
    if (sessionId) {
      api.proctorStart({ exam_session_id: sessionId, candidate_id: "self", drive_id: exam.drive_id })
        .catch(() => {});
    }
    const detach = attachProctoring({
      onViolation: (type) => {
        // Once auto-submit has begun, ignore any further flags — this is what
        // stops the count overshooting 5 while the submit request is in flight.
        if (submittedRef.current) return;
        const next = Math.min(vRef.current + 1, VIOLATION_LIMIT);
        vRef.current = next;
        setViolations(next);
        setLog((l) => [{ type, at: new Date() }, ...l].slice(0, 8));
        setToast(SIGNAL_LABEL[type] || type);
        setTimeout(() => setToast(null), 2500);
        if (sessionId) api.proctorEvent(sessionId, type).catch(() => {});
        if (next >= VIOLATION_LIMIT) doSubmit(true, "proctor");
      },
    });
    return detach;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ----- server-authoritative-ish timer -----
  useEffect(() => {
    timer.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          clearInterval(timer.current);
          doSubmit(true, "timeout");
          return 0;
        }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function choose(qid, opt) {
    setAnswers((a) => ({ ...a, [qid]: opt }));
    // durable auto-save to the live Exam Engine (best-effort)
    if (sessionId) api.examSave(sessionId, { [qid]: { option: opt } }).catch(() => {});
  }

  function saveCode(qid, payload) {
    setAnswers((a) => ({ ...a, [qid]: payload }));
    if (sessionId) api.examSave(sessionId, { [qid]: payload }).catch(() => {});
  }

  async function doSubmit(auto, reason) {
    if (submittedRef.current) return; // guard: only submit once (proctor/timeout/manual)
    submittedRef.current = true;
    clearInterval(timer.current);
    if (sessionId) {
      try {
        await api.examSubmit(sessionId);
      } catch {
        /* ignore */
      }
    }
    setSubmitted({ answered: Object.keys(answers).length, total: flat.length, auto, reason });
  }

  if (submitted) {
    const reasonText =
      submitted.reason === "timeout" ? "Time up — auto-submitted."
        : submitted.reason === "proctor" ? "Auto-submitted due to integrity violations."
          : "Your responses were recorded.";
    return (
      <div className="page-composition page-composition-candidate exam-result-page max-w-md mx-auto">
        <Card className="p-8 text-center">
          <span className={`grid place-items-center h-14 w-14 rounded-2xl mx-auto mb-4 ${
            submitted.reason === "proctor" ? "bg-rose-500/10 text-rose-600" : "bg-teal-500/12 text-teal-600"
          }`}>
            {submitted.reason === "proctor" ? <ShieldAlert size={28} /> : <CheckCircle2 size={28} />}
          </span>
          <h2 className="font-display text-xl font-bold text-ink-900">Submitted</h2>
          <p className="text-slate-500 mt-1">{reasonText}</p>
          <p className="mt-4 text-sm text-slate-600">
            Answered <span className="font-semibold">{submitted.answered}</span> of {submitted.total} ·{" "}
            {violations} integrity {violations === 1 ? "flag" : "flags"}
          </p>
          <Button className="mt-6 w-full" onClick={onExit}>Back to my drives</Button>
        </Card>
      </div>
    );
  }

  const section = exam.sections[secIdx];
  const low = remaining <= 30;
  const questions = section.questions || [];

  return (
    <div className="page-composition page-composition-candidate exam-runner min-h-[70vh]">
      {/* Proctor toast */}
      {toast && (
        <div className="fixed top-20 right-6 z-50 flex items-center gap-2 rounded-md bg-rose-500 text-white text-sm px-4 py-2.5 shadow-lift">
          <ShieldAlert size={16} /> {toast} recorded
        </div>
      )}

      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="font-display font-bold text-ink-900">{exam.title}</h1>
          <p className="text-sm text-slate-400">
            Section {secIdx + 1} of {exam.sections.length}: {section.title}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCalc((v) => !v)}
            className={`flex items-center gap-1.5 px-3 h-9 rounded-md text-sm font-medium transition-colors ${
              showCalc ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
            title="Open calculator"
          >
            <CalcIcon size={15} /> Calculator
          </button>
          <span className={`flex items-center gap-1.5 px-3 h-9 rounded-md text-sm font-medium ${
            violations ? "bg-rose-500/10 text-rose-600" : "bg-teal-500/10 text-teal-600"
          }`}>
            <Eye size={15} /> {violations}/{VIOLATION_LIMIT} flags
          </span>
          <div className={`flex items-center gap-2 px-4 h-11 rounded-md font-display font-semibold tabular-nums ${
            low ? "bg-rose-500/10 text-rose-600" : "bg-invert-900 text-white"
          }`}>
            <Clock size={18} /> {fmt(remaining)}
          </div>
        </div>
      </div>

      {showCalc && <Calculator onClose={() => setShowCalc(false)} />}

      {low && (
        <div className="mb-4 flex items-center gap-2 rounded-md bg-rose-500/10 text-rose-600 text-sm px-3.5 py-2.5">
          <AlertTriangle size={16} /> Less than a minute remaining — the exam will auto-submit.
        </div>
      )}

      <div className="grid lg:grid-cols-[1fr_240px] gap-6">
        <div className="space-y-4">
          {questions.map((q, i) => (
            <Card key={q.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <p className="font-medium text-ink-900">
                  <span className="text-slate-400 mr-2">Q{i + 1}.</span>{q.stem}
                </p>
                {q.type && <Badge tone="slate">{TYPE_LABEL[q.type] || q.type}</Badge>}
              </div>

              {q.type === "coding" && !(q.options || []).length ? (
                <CodeAnswer q={q} answer={answers[q.id]} onSave={(payload) => saveCode(q.id, payload)} />
              ) : (
                <div className="mt-4 space-y-2">
                  {(q.options || []).map((opt) => {
                    const [oid, text] = Array.isArray(opt) ? opt : [opt.id, opt.text];
                    const chosen = answers[q.id] === oid || answers[q.id]?.option === oid;
                    return (
                      <button
                        key={oid}
                        onClick={() => choose(q.id, oid)}
                        className={`w-full text-left px-4 min-h-11 py-2 rounded-md border flex items-center gap-3 transition-colors ${
                          chosen ? "border-brand-500 bg-brand-500/5 text-ink-900"
                            : "border-slate-200 hover:border-slate-300 text-slate-700"
                        }`}
                      >
                        <span className={`grid place-items-center h-6 w-6 shrink-0 rounded-full text-xs font-semibold ${
                          chosen ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-500"
                        }`}>
                          {String(oid).toUpperCase()}
                        </span>
                        {text || ""}
                      </button>
                    );
                  })}
                </div>
              )}
            </Card>
          ))}

          <div className="flex justify-between">
            <Button variant="secondary" disabled={secIdx === 0} onClick={() => setSecIdx((i) => Math.max(0, i - 1))}>
              Previous
            </Button>
            {secIdx < exam.sections.length - 1 ? (
              <Button onClick={() => setSecIdx((i) => i + 1)}>Next section <ChevronRight size={18} /></Button>
            ) : (
              <Button variant="amber" onClick={() => doSubmit(false)}>Submit exam</Button>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <Card className="p-5 h-fit sticky top-24">
            <p className="text-sm font-medium text-ink-900 mb-3">Questions</p>
            <div className="grid grid-cols-5 gap-2">
              {flat.map((qid, i) => (
                <span key={qid} className={`grid place-items-center h-9 w-9 rounded-md text-sm font-semibold ${
                  answers[qid] ? "bg-teal-500 text-white" : "bg-slate-100 text-slate-500"
                }`}>
                  {i + 1}
                </span>
              ))}
            </div>
            <p className="text-xs text-slate-400 mt-3">{Object.keys(answers).length}/{flat.length} answered</p>
            <Button variant="amber" className="w-full mt-4" onClick={() => doSubmit(false)}>Submit exam</Button>
          </Card>

          {log.length > 0 && (
            <Card className="p-4">
              <p className="text-sm font-medium text-ink-900 mb-2 flex items-center gap-2">
                <ShieldAlert size={15} className="text-rose-500" /> Proctor log
              </p>
              <ul className="space-y-1.5">
                {log.map((e, i) => (
                  <li key={i} className="text-xs text-slate-500 flex justify-between">
                    <span>{SIGNAL_LABEL[e.type] || e.type}</span>
                    <span className="tabular-nums">{e.at.toLocaleTimeString()}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
