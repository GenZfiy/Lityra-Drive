// Premium, self-contained SVG charts for the Lityra Drive analytics. No external
// chart library. Theme-aware (tracks/axes use CSS token vars; data colors are
// explicit hues). Each chart is data-driven from real drive metrics.
import { useId } from "react";
import { motion, useReducedMotion } from "framer-motion";

/* ---------- Mastery bar (magnitude, with depth) ----------
   A recessed glossy track with a gradient fill, quarter-scale ticks, a glowing
   leading knob and an animated grow-in. Width maps exactly to `pct` — depth is
   cosmetic only, never distorts the value. Shared by Skill Map + Career Readiness. */
const MASTERY_BANDS = {
  strong:     { c1: "#5eead4", c2: "#0d9488", text: "#0f766e", glow: "rgba(13,148,136,.55)" },
  developing: { c1: "#fcd34d", c2: "#d97706", text: "#b45309", glow: "rgba(217,119,6,.52)" },
  weak:       { c1: "#fda4af", c2: "#e11d48", text: "#be123c", glow: "rgba(225,29,72,.52)" },
};
const bandFor = (p) => (p >= 80 ? "strong" : p >= 50 ? "developing" : "weak");
const rgba = (hex, a) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};

/* ---------- Heat tile (compact heat-map cell) ----------
   A color-graded tile whose fill intensity scales with mastery (green→amber→red).
   Big % headline, name + fraction, optional rank chip. Grid these for a heat-map. */
export function HeatTile({ label, pct = 0, sub, band, rank }) {
  const reduceMotion = useReducedMotion();
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  const b = MASTERY_BANDS[band] || MASTERY_BANDS[bandFor(p)];
  const a = 0.12 + (p / 100) * 0.34; // heat intensity 0.12 → 0.46
  return (
    <motion.div
      className="relative rounded-xl p-3.5 overflow-hidden shadow-card"
      style={{ background: `linear-gradient(140deg, ${rgba(b.c1, a * 0.85)}, ${rgba(b.c2, a)})`, border: `1px solid ${rgba(b.c2, 0.22)}` }}
      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-30px" }}
      transition={{ duration: reduceMotion ? 0 : 0.4 }}
      whileHover={reduceMotion ? undefined : { y: -3 }}
    >
      {/* top gloss */}
      <span aria-hidden className="absolute inset-x-0 top-0 h-8 pointer-events-none"
            style={{ background: "linear-gradient(180deg, rgba(255,255,255,.35), transparent)" }} />
      {rank != null && (
        <span className="absolute top-2.5 right-2.5 grid place-items-center h-5 min-w-5 px-1 rounded-md text-[10px] font-bold tabular-nums"
              style={{ background: rgba(b.c2, 0.18), color: b.text }}>{rank}</span>
      )}
      <div className="font-display text-2xl font-bold tabular-nums leading-none" style={{ color: b.text }}>{p}%</div>
      <p className="mt-2 text-sm font-medium text-ink-900 capitalize truncate">{label}</p>
      {sub != null && <p className="text-[11px] text-slate-500 tabular-nums">{sub}</p>}
    </motion.div>
  );
}

/* ---------- Radar / spider chart (a profile across topics) ----------
   Plots each topic on its own spoke; the connected polygon is the skill "shape".
   Concentric grid rings, gradient fill, glowing stroke, band-coloured vertices
   and per-axis value labels. Radius maps exactly to mastery. Needs ≥ 3 axes. */
export function RadarChart({ data = [], color = "#2563EB", size = 300, max = 100 }) {
  const reduceMotion = useReducedMotion();
  const id = useId();
  const padX = 138, padY = 48;                 // room so long edge labels never clip
  const W = size + padX * 2, H = size + padY * 2;
  const cx = W / 2, cy = H / 2, R = size / 2;
  const n = Math.max(1, data.length);
  const ang = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  const onAxis = (frac, i, r = R) => [cx + frac * r * Math.cos(ang(i)), cy + frac * r * Math.sin(ang(i))];
  const ringPoly = (f) => data.map((_, i) => onAxis(f, i).join(",")).join(" ");
  const valuePoly = data.map((d, i) => onAxis(Math.max(0, Math.min(max, d.value)) / max, i).join(",")).join(" ");
  return (
    <div className="w-full grid place-items-center overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ maxWidth: "100%" }}>
        <defs>
          <radialGradient id={`rf${id}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={color} stopOpacity="0.42" />
            <stop offset="100%" stopColor={color} stopOpacity="0.14" />
          </radialGradient>
          <filter id={`rg${id}`} x="-40%" y="-40%" width="180%" height="180%">
            <feDropShadow dx="0" dy="1" stdDeviation="3" floodColor={color} floodOpacity="0.5" />
          </filter>
        </defs>

        {/* grid rings + spokes */}
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <polygon key={f} points={ringPoly(f)} fill="none" stroke="rgb(var(--c-slate-200))" strokeWidth="1" opacity={f === 1 ? 0.9 : 0.55} />
        ))}
        {data.map((d, i) => {
          const [x, y] = onAxis(1, i);
          return <line key={`sp${i}`} x1={cx} y1={cy} x2={x} y2={y} stroke="rgb(var(--c-slate-100))" strokeWidth="1" />;
        })}

        {/* value shape */}
        <motion.g style={{ transformBox: "fill-box", transformOrigin: "center" }}
          initial={reduceMotion ? false : { opacity: 0, scale: 0.5 }} whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true, margin: "-40px" }} transition={{ duration: reduceMotion ? 0 : 0.8, ease: [0.16, 1, 0.3, 1] }}>
          <polygon points={valuePoly} fill={`url(#rf${id})`} stroke={color} strokeWidth="2.5" strokeLinejoin="round" filter={`url(#rg${id})`} />
        </motion.g>

        {/* vertices (coloured by band) + labels */}
        {data.map((d, i) => {
          const p = Math.max(0, Math.min(100, Math.round(d.value)));
          const b = MASTERY_BANDS[bandFor(p)];
          const [vx, vy] = onAxis(p / max, i);
          const [lx, ly] = onAxis(1, i, R + 26);
          const c = Math.cos(ang(i));
          const anchor = c > 0.3 ? "start" : c < -0.3 ? "end" : "middle";
          return (
            <g key={`v${i}`}>
              <motion.circle cx={vx} cy={vy} r="4.5" fill="rgb(var(--c-surface))" stroke={b.c2} strokeWidth="2.5"
                initial={reduceMotion ? false : { opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true, margin: "-40px" }}
                transition={{ delay: reduceMotion ? 0 : 0.5 + i * 0.05 }}>
                <title>{d.label}: {p}%</title>
              </motion.circle>
              <text x={lx} y={ly - 5} textAnchor={anchor} fill="rgb(var(--c-ink-900))" fontSize="11" fontWeight="600" style={{ textTransform: "capitalize" }}>{d.label}</text>
              <text x={lx} y={ly + 9} textAnchor={anchor} fontSize="11" fontWeight="700" fill={b.c2} style={{ fontVariantNumeric: "tabular-nums" }}>{p}%</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function MasteryBar({ label, pct = 0, sub, band, small, rank }) {
  const reduceMotion = useReducedMotion();
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  const b = MASTERY_BANDS[band] || MASTERY_BANDS[bandFor(p)];
  const h = small ? "h-2.5" : "h-3.5";
  const knob = small ? 12 : 15;
  const showHeader = label != null || sub != null || rank != null;
  return (
    <div>
      {showHeader && (
        <div className="flex items-center justify-between mb-1.5 gap-3">
          <span className="flex items-center gap-2 min-w-0">
            {rank != null && (
              <span className="shrink-0 grid place-items-center h-5 w-5 rounded-md text-[11px] font-bold tabular-nums text-slate-500 bg-slate-100">
                {rank}
              </span>
            )}
            <span className={`${small ? "text-sm" : "font-medium"} text-ink-900 capitalize truncate`}>{label}</span>
          </span>
          <span className="flex items-center gap-2 text-sm shrink-0">
            {sub != null && <span className="tabular-nums text-slate-400">{sub}</span>}
            <span className="tabular-nums font-bold" style={{ color: b.text }}>{p}%</span>
          </span>
        </div>
      )}
      {/* recessed track (not clipped, so the leading knob & glow read) */}
      <div
        className={`relative ${h} rounded-full bg-slate-200/80`}
        style={{ boxShadow: "inset 0 1px 2.5px rgba(15,23,42,.18), inset 0 -1px 0 rgba(255,255,255,.55)" }}
      >
        {[25, 50, 75].map((t) => (
          <span key={t} aria-hidden className="absolute top-0 bottom-0 w-px bg-slate-300/60" style={{ left: `${t}%` }} />
        ))}
        <motion.div
          className="absolute left-0 top-0 h-full rounded-full"
          style={{ background: `linear-gradient(120deg, ${b.c1}, ${b.c2})`, boxShadow: `0 1px 6px -1px ${b.glow}, inset 0 1px 0 rgba(255,255,255,.45)` }}
          initial={reduceMotion ? false : { width: 0 }}
          whileInView={{ width: `${p}%` }}
          viewport={{ once: true, margin: "-40px" }}
          transition={reduceMotion ? { duration: 0 } : { duration: 1, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* glossy top highlight */}
          <span aria-hidden className="absolute inset-x-0 top-0 h-1/2 rounded-full"
                style={{ background: "linear-gradient(180deg, rgba(255,255,255,.55), transparent)" }} />
          {/* glowing leading knob */}
          {p > 0 && (
            <span aria-hidden className="absolute top-1/2 right-0 -translate-y-1/2 translate-x-1/2 rounded-full"
                  style={{ width: knob, height: knob, background: `radial-gradient(circle at 38% 32%, #fff, ${b.c1} 70%)`, boxShadow: `0 0 9px 1px ${b.glow}, inset 0 -1px 2px rgba(0,0,0,.15)` }} />
          )}
        </motion.div>
      </div>
    </div>
  );
}

/* ---------- smooth path (Catmull-Rom-ish) ---------- */
function smoothPath(pts) {
  if (pts.length < 2) return "";
  const ctrl = (cur, prev, next, reverse) => {
    prev = prev || cur; next = next || cur;
    const dx = next[0] - prev[0], dy = next[1] - prev[1];
    const ang = Math.atan2(dy, dx) + (reverse ? Math.PI : 0);
    const len = Math.hypot(dx, dy) * 0.16;
    return [cur[0] + Math.cos(ang) * len, cur[1] + Math.sin(ang) * len];
  };
  let d = `M ${pts[0][0]},${pts[0][1]}`;
  for (let i = 1; i < pts.length; i++) {
    const cps = ctrl(pts[i - 1], pts[i - 2], pts[i], false);
    const cpe = ctrl(pts[i], pts[i - 1], pts[i + 1], true);
    d += ` C ${cps[0]},${cps[1]} ${cpe[0]},${cpe[1]} ${pts[i][0]},${pts[i][1]}`;
  }
  return d;
}

/* ---------- Radial gauge (progress toward a max) ---------- */
export function RadialGauge({ value = 0, max = 100, label, color = "#2563EB", size = 132, suffix = "%" }) {
  const id = useId();
  const stroke = 11;
  const r = size / 2 - stroke;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, max ? value / max : 0));
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={`g${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.65" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(var(--c-slate-200))" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={`url(#g${id})`} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={`${circ * pct} ${circ}`} style={{ transition: "stroke-dasharray 900ms cubic-bezier(.2,.8,.2,1)", filter: "drop-shadow(0 3px 7px rgba(0,0,0,.18))" }} />
      </svg>
      <div className="absolute text-center">
        <div className="font-display text-[26px] font-bold text-ink-900 tabular-nums leading-none">{Math.round(value)}<span className="text-[15px] text-slate-400 font-semibold">{suffix}</span></div>
        {label && <div className="text-[10px] uppercase tracking-[0.12em] text-slate-400 mt-1">{label}</div>}
      </div>
    </div>
  );
}

/* ---------- Funnel (narrowing trapezoids) ---------- */
export function Funnel({ stages = [] }) {
  const id = useId();
  const max = Math.max(1, ...stages.map((s) => s.value));
  const W = 560, rowH = 52, gap = 8;
  const H = stages.length * (rowH + gap) - gap;
  const wAt = (v) => Math.max(46, (v / max) * W);
  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 380 }}>
        <defs>
          {stages.map((s, i) => (
            <linearGradient key={i} id={`f${id}-${i}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={s.color} stopOpacity="0.82" />
              <stop offset="100%" stopColor={s.color} />
            </linearGradient>
          ))}
        </defs>
        {stages.map((s, i) => {
          const topW = wAt(s.value);
          const botW = wAt(i < stages.length - 1 ? stages[i + 1].value : s.value);
          const y = i * (rowH + gap);
          const yb = y + rowH;
          const x1 = (W - topW) / 2, x2 = (W + topW) / 2, x3 = (W + botW) / 2, x4 = (W - botW) / 2;
          const prev = i === 0 ? null : stages[i - 1].value;
          const conv = prev ? Math.round((s.value / (prev || 1)) * 100) : null;
          return (
            <g key={s.label}>
              <path d={`M${x1},${y} L${x2},${y} L${x3},${yb} L${x4},${yb} Z`} fill={`url(#f${id}-${i})`}>
                <title>{s.label}: {s.value}</title>
              </path>
              <text x={W / 2} y={y + rowH / 2} textAnchor="middle" dominantBaseline="central" fill="#fff" fontSize="17" fontWeight="700" style={{ fontVariantNumeric: "tabular-nums" }}>{s.value}</text>
              <text x={12} y={y + rowH / 2} dominantBaseline="central" fill="rgb(var(--c-slate-600))" fontSize="12.5">{s.label}</text>
              {conv != null && <text x={W - 12} y={y + rowH / 2} textAnchor="end" dominantBaseline="central" fill="rgb(var(--c-slate-400))" fontSize="12">{conv}%</text>}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* ---------- Smooth area chart (distribution / density) ----------
   Premium line form: deep gradient fill, a glowing gradient stroke that draws
   in on view, soft-glowing data points, an emphasized peak with a value cap. */
export function AreaChart({ data = [], color = "#2563EB", height = 190 }) {
  const reduceMotion = useReducedMotion();
  const id = useId();
  const W = 520, H = height, padX = 16, padT = 22, padB = 30;
  const max = Math.max(1, ...data.map((d) => d.value));
  const n = data.length;
  const xAt = (i) => padX + (n <= 1 ? (W - padX * 2) / 2 : (i / (n - 1)) * (W - padX * 2));
  const yAt = (v) => padT + (1 - v / max) * (H - padT - padB);
  const pts = data.map((d, i) => [xAt(i), yAt(d.value)]);
  const line = smoothPath(pts);
  const area = pts.length ? `${line} L ${xAt(n - 1)},${H - padB} L ${xAt(0)},${H - padB} Z` : "";
  const peak = data.length ? data.reduce((m, d, i) => (d.value > data[m].value ? i : m), 0) : 0;
  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 320 }}>
        <defs>
          <linearGradient id={`a${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.42" />
            <stop offset="55%" stopColor={color} stopOpacity="0.14" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id={`s${id}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={color} stopOpacity="0.7" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
          <filter id={`glow${id}`} x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="2" stdDeviation="3.2" floodColor={color} floodOpacity="0.5" />
          </filter>
        </defs>

        {[0.25, 0.5, 0.75].map((g) => (
          <line key={g} x1={padX} x2={W - padX} y1={padT + g * (H - padT - padB)} y2={padT + g * (H - padT - padB)}
                stroke="rgb(var(--c-slate-100))" strokeWidth="1" />
        ))}
        <line x1={padX} x2={W - padX} y1={H - padB} y2={H - padB} stroke="rgb(var(--c-slate-200))" strokeWidth="1.25" />

        {area && (
          <motion.path d={area} fill={`url(#a${id})`}
            initial={reduceMotion ? false : { opacity: 0 }} whileInView={{ opacity: 1 }}
            viewport={{ once: true, margin: "-40px" }} transition={{ duration: reduceMotion ? 0 : 0.9, delay: reduceMotion ? 0 : 0.25 }} />
        )}
        {line && (
          <motion.path d={line} fill="none" stroke={`url(#s${id})`} strokeWidth="3"
            strokeLinecap="round" strokeLinejoin="round" filter={`url(#glow${id})`}
            initial={reduceMotion ? false : { pathLength: 0 }} whileInView={{ pathLength: 1 }}
            viewport={{ once: true, margin: "-40px" }} transition={{ duration: reduceMotion ? 0 : 1.1, ease: [0.16, 1, 0.3, 1] }} />
        )}
        {pts.map((p, i) => {
          const isPeak = i === peak && data[i].value > 0;
          return (
            <motion.g key={i}
              initial={reduceMotion ? false : { opacity: 0 }} whileInView={{ opacity: 1 }}
              viewport={{ once: true, margin: "-40px" }} transition={{ delay: reduceMotion ? 0 : 0.5 + i * 0.06 }}>
              {isPeak && <circle cx={p[0]} cy={p[1]} r="8" fill={color} opacity="0.18" />}
              <circle cx={p[0]} cy={p[1]} r={isPeak ? 5 : 3.6} fill="rgb(var(--c-surface))"
                      stroke={color} strokeWidth={isPeak ? 2.6 : 2}
                      style={isPeak ? { filter: `url(#glow${id})` } : undefined}>
                <title>{data[i].label}: {data[i].value}</title>
              </circle>
              {isPeak && (
                <text x={p[0]} y={p[1] - 12} textAnchor="middle" fill="rgb(var(--c-ink-900))"
                      fontSize="12.5" fontWeight="700" style={{ fontVariantNumeric: "tabular-nums" }}>
                  {data[i].value}
                </text>
              )}
              <text x={p[0]} y={H - padB + 17} textAnchor="middle" fill="rgb(var(--c-slate-400))" fontSize="11">{data[i].label}</text>
            </motion.g>
          );
        })}
      </svg>
    </div>
  );
}

/* ---------- Donut (composition, headline in center) ---------- */
function arc(cx, cy, r, a0, a1) {
  const p = (a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const [x0, y0] = p(a0), [x1, y1] = p(a1);
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M ${x0},${y0} A ${r},${r} 0 ${large} 1 ${x1},${y1}`;
}
export function Donut({ parts = [], size = 168, centerValue, centerLabel }) {
  const total = parts.reduce((n, p) => n + p.n, 0);
  const cx = size / 2, cy = size / 2, r = size / 2 - 12, stroke = 18;
  let ang = -Math.PI / 2;
  const gap = total > 1 ? 0.04 : 0;
  return (
    <div className="flex items-center gap-5">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size}>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgb(var(--c-slate-100))" strokeWidth={stroke} />
          {total > 0 && parts.map((p) => {
            const frac = p.n / total;
            const a0 = ang + gap / 2, a1 = ang + frac * 2 * Math.PI - gap / 2;
            ang += frac * 2 * Math.PI;
            if (a1 <= a0) return null;
            return <path key={p.label} d={arc(cx, cy, r, a0, a1)} fill="none" stroke={p.color} strokeWidth={stroke} strokeLinecap="round" style={{ filter: "drop-shadow(0 2px 5px rgba(0,0,0,.16))" }}><title>{p.label}: {p.n}</title></path>;
          })}
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center">
          <div>
            <div className="font-display text-2xl font-bold text-ink-900 tabular-nums leading-none">{centerValue ?? total}</div>
            <div className="text-[10px] uppercase tracking-[0.1em] text-slate-400 mt-1">{centerLabel ?? "total"}</div>
          </div>
        </div>
      </div>
      <div className="grid gap-2 min-w-0">
        {parts.map((p) => (
          <div key={p.label} className="flex items-center gap-2 text-[12.5px]">
            <span className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: p.color }} />
            <span className="text-slate-600 truncate">{p.label}</span>
            <span className="ml-auto pl-3 font-semibold text-ink-900 tabular-nums">{p.n}</span>
            <span className="text-slate-400 tabular-nums w-9 text-right">{total ? Math.round((p.n / total) * 100) : 0}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
