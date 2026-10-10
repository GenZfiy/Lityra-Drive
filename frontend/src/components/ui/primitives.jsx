// Design-system primitives. All styling reads Tailwind tokens from
// tailwind.config.js (which mirrors DESIGN.md). No ad-hoc hex here.
import { motion, useReducedMotion } from "framer-motion";

function cx(...c) {
  return c.filter(Boolean).join(" ");
}

/* ---------- Button ---------- */
const BTN = {
  base:
    "inline-flex items-center justify-center gap-2 font-semibold rounded-md transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed select-none",
  size: {
    sm: "h-9 px-3 text-sm",
    md: "h-11 px-5 text-sm",
    lg: "h-12 px-6 text-base",
  },
  variant: {
    primary: "bg-brand-500 text-white hover:bg-brand-600 shadow-card",
    secondary: "bg-surface text-ink-900 border border-slate-200 hover:bg-slate-50",
    ghost: "bg-transparent text-ink-700 hover:bg-slate-100",
    amber: "bg-amber-500 text-ink-950 hover:bg-amber-400 shadow-card",
    danger: "bg-rose-500 text-white hover:bg-rose-600",
  },
};

export function Button({ variant = "primary", size = "md", className, as: As = "button", ...p }) {
  return <As className={cx(BTN.base, BTN.size[size], BTN.variant[variant], className)} {...p} />;
}

/* ---------- Card ---------- */
export function Card({ className, children, ...p }) {
  const reduceMotion = useReducedMotion();
  const onPointerMove = (event) => {
    if (reduceMotion || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const px = (event.clientX - rect.left) / rect.width;
    const py = (event.clientY - rect.top) / rect.height;
    event.currentTarget.style.setProperty("--depth-x", `${((0.5 - py) * 2.2).toFixed(2)}deg`);
    event.currentTarget.style.setProperty("--depth-y", `${((px - 0.5) * 2.6).toFixed(2)}deg`);
  };
  const onPointerLeave = (event) => {
    event.currentTarget.style.setProperty("--depth-x", "0deg");
    event.currentTarget.style.setProperty("--depth-y", "0deg");
  };
  return (
    <div className={cx("depth-card bg-surface rounded-lg border border-slate-100 shadow-card", className)} onPointerMove={onPointerMove} onPointerLeave={onPointerLeave} {...p}>
      {children}
    </div>
  );
}

/* ---------- Field / Input ---------- */
export function Field({ label, hint, error, children, htmlFor }) {
  return (
    <label htmlFor={htmlFor} className="block">
      {label && <span className="block text-sm font-medium text-ink-900 mb-1.5">{label}</span>}
      {children}
      {error ? (
        <span className="mt-1.5 block text-sm text-rose-600">{error}</span>
      ) : hint ? (
        <span className="mt-1.5 block text-sm text-slate-500">{hint}</span>
      ) : null}
    </label>
  );
}

export function Input({ className, invalid, ...p }) {
  return (
    <input
      className={cx(
        "w-full h-11 px-3.5 rounded-md border bg-surface text-ink-900 placeholder:text-slate-400",
        "transition-colors duration-200",
        invalid ? "border-rose-400" : "border-slate-200 hover:border-slate-300",
        className,
      )}
      {...p}
    />
  );
}

/* ---------- Badge ---------- */
export function Badge({ tone = "brand", className, children }) {
  const tones = {
    brand: "bg-brand-500/10 text-brand-600",
    amber: "bg-amber-500/15 text-amber-600",
    teal: "bg-teal-500/12 text-teal-600",
    slate: "bg-slate-100 text-slate-600",
    rose: "bg-rose-500/10 text-rose-600",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ---------- XP bar (gamification) ---------- */
export function XPBar({ value = 0, max = 100, label }) {
  const reduceMotion = useReducedMotion();
  const pct = Math.max(0, Math.min(100, Math.round((value / max) * 100)));
  return (
    <div>
      {label && (
        <div className="flex justify-between text-xs font-medium text-slate-500 mb-1.5">
          <span>{label}</span>
          <span className="tabular-nums">
            {value}/{max} XP
          </span>
        </div>
      )}
      <div className="h-2.5 w-full rounded-full bg-slate-200 overflow-hidden">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-amber-500 to-amber-400"
          initial={reduceMotion ? false : { width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: reduceMotion ? 0 : 0.7, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

/* ---------- Stat tile ---------- */
export function StatTile({ icon: Icon, label, value, tone = "brand", sub }) {
  const tones = {
    brand: "text-brand-600 bg-brand-500/10",
    amber: "text-amber-600 bg-amber-500/15",
    teal: "text-teal-600 bg-teal-500/12",
  };
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-1 text-2xl font-display font-semibold text-ink-900 tabular-nums">
            {value}
          </p>
          {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
        </div>
        {Icon && (
          <span className={cx("grid place-items-center h-10 w-10 rounded-md", tones[tone])}>
            <Icon size={20} strokeWidth={1.75} />
          </span>
        )}
      </div>
    </Card>
  );
}
