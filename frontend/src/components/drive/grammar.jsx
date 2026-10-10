// Lityra Drive — visual grammar for the recruitment operating system.
// Presentational primitives shared across Drive surfaces. Everything here is
// data-driven; callers pass values derived from REAL API responses. Nothing
// fabricates recruitment data.
import { ArrowUp, ArrowDown, Minus, ChevronRight, Sparkles, AlertTriangle } from "lucide-react";

/* ---------- signal helpers ---------- */
export const band = (v) => (v >= 75 ? "good" : v >= 50 ? "warn" : "risk");
export const BANDHEX = { good: "#0d9488", warn: "#d97706", risk: "#e11d48", neutral: "#64748b", brand: "#4f46e5" };
export const bandHex = (b) => BANDHEX[b] || BANDHEX.neutral;
export const initials = (n = "") => n.split(/\s+/).map((w) => w[0]).filter(Boolean).slice(0, 2).join("").toUpperCase() || "–";
const AV = ["#4f46e5", "#0d9488", "#d97706", "#8b5cf6", "#e11d48", "#0891b2", "#db2777", "#65a30d"];
export const hueFor = (n = "") => { let h = 0; for (const c of n) h = (h * 31 + c.charCodeAt(0)) >>> 0; return AV[h % AV.length]; };

/* ---------- Delta ---------- */
export function Delta({ v = 0, suffix = "%", invertGood = false }) {
  const good = invertGood ? v < 0 : v > 0;
  const Icon = v > 0 ? ArrowUp : v < 0 ? ArrowDown : Minus;
  const cls = v === 0 ? "text-slate-400" : good ? "text-teal-600" : "text-rose-600";
  return (
    <span className={`inline-flex items-center gap-0.5 font-semibold tabular-nums ${cls}`}>
      <Icon size={12} strokeWidth={2.4} /> {Math.abs(v)}{suffix}
    </span>
  );
}

/* ---------- Spark ---------- */
export function Spark({ points = [], color = "#4f46e5", w = 62, h = 20 }) {
  if (!points.length) return null;
  const mn = Math.min(...points), mx = Math.max(...points), rng = mx - mn || 1;
  const P = points.map((p, i) => [(i / (points.length - 1)) * w, h - ((p - mn) / rng) * (h - 3) - 1]);
  const d = P.map((p) => p.join(",")).join(" ");
  const last = P[P.length - 1];
  return (
    <svg width={w} height={h} className="opacity-90" aria-hidden="true">
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r="2" fill={color} />
    </svg>
  );
}

/* ---------- ReadOut (instrument metric) ---------- */
export function ReadOut({ label, value, unit, delta, hint, spark }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-surface p-4 relative overflow-hidden">
      <div className="text-[10.5px] font-bold uppercase tracking-[0.13em] text-slate-400">{label}</div>
      <div className="mt-2 font-display text-[26px] font-bold tracking-tight text-ink-900 leading-none">
        {value}{unit && <span className="text-[15px] text-slate-400 font-semibold"> {unit}</span>}
      </div>
      <div className="mt-2 flex items-center gap-2 text-[11.5px] text-slate-500 min-h-[16px]">
        {delta}{hint && <span>{hint}</span>}
      </div>
      {spark && <div className="absolute right-3 bottom-3">{spark}</div>}
    </div>
  );
}

/* ---------- PipelineRibbon (intelligent) ---------- */
export function Ribbon({ stages = [], selected, onSelect }) {
  const max = Math.max(1, ...stages.map((s) => s.count || 0));
  return (
    <div className="flex items-stretch gap-0 overflow-x-auto pb-1">
      {stages.map((s, i) => {
        const hex = bandHex(s.health || "neutral");
        const sel = selected === s.key;
        return (
          <div key={s.key} className="relative flex-1 min-w-[122px] px-1">
            {i < stages.length - 1 && (
              <div className="absolute top-9 -right-2 z-10 grid place-items-center h-4 w-4 rounded-full bg-surface border border-slate-200 text-slate-300">
                <ChevronRight size={11} />
              </div>
            )}
            <button
              onClick={() => onSelect && onSelect(sel ? null : s.key)}
              className={`w-full text-left rounded-xl border p-3 transition ${sel ? "border-brand-500 ring-1 ring-brand-500" : "border-slate-200 hover:border-slate-300 bg-surface"}`}
            >
              <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-600 whitespace-nowrap">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: hex }} /> {s.label}
                {s.bottleneck && <span className="ml-auto text-[8.5px] font-extrabold tracking-wide text-amber-700 bg-amber-500/15 px-1.5 py-0.5 rounded">BOTTLENECK</span>}
              </div>
              <div className="mt-1.5 font-display text-[23px] font-bold tracking-tight text-ink-900 leading-none tabular-nums">{s.count}</div>
              <div className="mt-1 text-[10.5px] text-slate-400">{s.meta}</div>
              <div className="mt-2 h-1 rounded bg-slate-100 overflow-hidden">
                <span className="block h-full rounded" style={{ width: `${Math.round(((s.count || 0) / max) * 100)}%`, background: hex }} />
              </div>
            </button>
          </div>
        );
      })}
    </div>
  );
}

/* ---------- Attention (action intelligence) ---------- */
export function Attention({ items = [] }) {
  if (!items.length) return <div className="p-6 text-sm text-slate-400 text-center">Nothing needs attention — the drive is flowing cleanly.</div>;
  const PRIO = { critical: "#e11d48", high: "#d97706", medium: "#4f46e5" };
  const TONEBG = { risk: "bg-rose-500/10 text-rose-600", warn: "bg-amber-500/10 text-amber-600", brand: "bg-brand-500/10 text-brand-600", teal: "bg-teal-500/10 text-teal-600" };
  return (
    <div>
      {items.map((a, i) => {
        const Icon = a.icon;
        return (
          <div key={i} className="flex gap-3 items-start px-4 py-3.5 border-b border-slate-100 last:border-b-0">
            <span className="w-1 self-stretch rounded" style={{ background: PRIO[a.priority] || PRIO.medium }} />
            <span className={`grid place-items-center h-9 w-9 rounded-[10px] shrink-0 ${TONEBG[a.tone] || TONEBG.brand}`}>
              {Icon ? <Icon size={17} /> : <AlertTriangle size={17} />}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-semibold text-ink-900 tracking-[-0.01em]">{a.title}</div>
              <div className="text-[12px] text-slate-500 mt-0.5">{a.detail}</div>
              {a.actions?.length > 0 && (
                <div className="flex gap-2 mt-2.5">
                  {a.actions.map((x, j) => (
                    <button key={j} onClick={x.onClick}
                      className={`h-7 px-3 rounded-lg text-[11.5px] font-semibold transition ${x.primary ? "bg-invert-900 text-white hover:bg-invert-800" : "text-slate-500 hover:text-ink-900 hover:bg-slate-100"}`}>
                      {x.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ---------- AIObservation (Observation -> Reason -> Impact -> Action) ---------- */
export function AIObservation({ severity = "brand", title, observation, reason, impact, action }) {
  const tone = { risk: "text-rose-600 bg-rose-500/10", warn: "text-amber-600 bg-amber-500/10", brand: "text-brand-600 bg-brand-500/10", teal: "text-teal-600 bg-teal-500/10" }[severity] || "text-brand-600 bg-brand-500/10";
  const Row = ({ k, v }) => (
    <div className="grid grid-cols-[70px_1fr] gap-2.5 mt-2.5 text-[12.5px]">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400 pt-0.5">{k}</div>
      <div className="text-slate-600 leading-relaxed">{v}</div>
    </div>
  );
  return (
    <div className="rounded-xl border border-slate-200 bg-gradient-to-b from-brand-500/[0.04] to-transparent p-4">
      <div className="flex items-center gap-2 text-[13px] font-semibold text-ink-900 tracking-[-0.01em]">
        <span className={`grid place-items-center h-6 w-6 rounded-lg ${tone}`}><Sparkles size={14} /></span>
        {title}
        <span className="ml-auto text-[9.5px] font-bold uppercase tracking-wide text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">Derived intelligence</span>
      </div>
      {observation && <Row k="Observation" v={observation} />}
      {reason && <Row k="Reason" v={reason} />}
      {impact && <Row k="Impact" v={impact} />}
      {action && (
        <div className="flex items-center justify-between gap-2 mt-3 pt-3 border-t border-slate-100">
          <span className="text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">Recommended</span>
          <button onClick={action.onClick} className="inline-flex items-center gap-1.5 h-7 px-3 rounded-lg bg-invert-900 text-white text-[11.5px] font-semibold hover:bg-invert-800">
            {action.label} <ChevronRight size={13} />
          </button>
        </div>
      )}
    </div>
  );
}

/* ---------- SignalCard (candidate intelligence) ---------- */
export function SignalCard({ name, sub, confidence, comps = [], riskTag, next, picked, onClick }) {
  const cHex = bandHex(band(confidence));
  return (
    <button onClick={onClick}
      className={`text-left rounded-2xl border bg-surface p-4 transition w-full ${picked ? "border-brand-500 ring-1 ring-brand-500" : "border-slate-200 hover:border-slate-300 hover:-translate-y-px"}`}>
      <div className="flex items-center gap-3">
        <span className="grid place-items-center h-10 w-10 rounded-xl text-white font-bold text-sm shrink-0" style={{ background: hueFor(name) }}>{initials(name)}</span>
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-ink-900 tracking-[-0.01em] truncate">{name}</div>
          <div className="text-[11.5px] text-slate-500 truncate">{sub}</div>
        </div>
        <div className="text-right shrink-0">
          <div className="font-display text-[19px] font-bold leading-none tabular-nums" style={{ color: cHex }}>{confidence}</div>
          <div className="text-[9px] uppercase tracking-wider text-slate-400">readiness</div>
        </div>
      </div>
      {comps.length > 0 && (
        <div className="flex gap-1.5 mt-3">
          {comps.map((c) => (
            <div key={c.name} className="flex-1 min-w-0">
              <div className="text-[9.5px] text-slate-400 truncate">{c.name}</div>
              <div className="h-1.5 rounded bg-slate-100 mt-1 overflow-hidden">
                <span className="block h-full rounded" style={{ width: `${c.value}%`, background: bandHex(band(c.value)) }} />
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100 text-[11.5px]">
        {riskTag}
        {next && <span className="ml-auto text-brand-600 font-medium inline-flex items-center gap-1">{next} <ChevronRight size={13} /></span>}
      </div>
    </button>
  );
}
