// Reusable premium 3D decoration kit — drop into any surface for depth.
// Pure CSS/framer 3D (no WebGL): gradient spheres with real highlight/shadow,
// a cursor-tilt hook for cards, and gradient brand-logo tiles.
import { motion, useMotionValue, useSpring, useTransform, useReducedMotion } from "framer-motion";

const GRAD = {
  amber: "radial-gradient(circle at 32% 28%, #fde68a, #f59e0b 52%, #b45309 100%)",
  brand: "radial-gradient(circle at 32% 28%, #93c5fd, #2563EB 52%, #1e3a8a 100%)",
  teal: "radial-gradient(circle at 32% 28%, #5eead4, #0D9488 52%, #134e4a 100%)",
  rose: "radial-gradient(circle at 32% 28%, #fda4af, #E11D48 52%, #881337 100%)",
};
const RGB = { amber: "217,119,6", brand: "37,99,235", teal: "13,148,136", rose: "225,29,72" };
const shadow = (c) => `0 24px 48px -14px rgba(${RGB[c]},.5), inset -5px -7px 14px rgba(0,0,0,.28), inset 4px 5px 10px rgba(255,255,255,.4)`;

// A single floating 3D sphere.
export function Sphere({ color = "amber", size = 80, className = "", float = 12, delay = 0, z = 0 }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      aria-hidden
      animate={reduceMotion ? { y: 0 } : { y: [0, -float, 0] }}
      transition={reduceMotion ? { duration: 0 } : { repeat: Infinity, duration: 5 + delay, ease: "easeInOut", delay }}
      style={{ width: size, height: size, background: GRAD[color], boxShadow: shadow(color), z }}
      className={`rounded-full pointer-events-none ${className}`}
    />
  );
}

// A scattered set of orbs for a section background (absolute-positioned).
export function Orbs({ className = "", tone = "mixed" }) {
  const sets = {
    mixed: [["amber", 92, "-top-6 -right-4", 0], ["brand", 52, "top-1/3 -left-7", 0.8], ["teal", 40, "bottom-12 right-12", 1.6]],
    warm: [["amber", 96, "-top-8 right-6", 0], ["rose", 46, "bottom-10 -left-6", 1.0], ["amber", 34, "top-1/2 right-1/4", 1.8]],
    cool: [["brand", 96, "-top-8 right-8", 0], ["teal", 48, "bottom-10 -left-6", 1.0], ["brand", 34, "top-1/2 right-1/3", 1.8]],
  };
  return (
    <div aria-hidden className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`}>
      {(sets[tone] || sets.mixed).map(([c, s, pos, d], i) => (
        <Sphere key={i} color={c} size={s} delay={d} className={`absolute ${pos} opacity-90`} />
      ))}
    </div>
  );
}

// Cursor-following 3D tilt for a card. Spread the returned handlers on a wrapper
// and apply {rotX,rotY} to a motion element with transformPerspective + preserve-3d.
export function useTilt(strength = 14) {
  const reduceMotion = useReducedMotion();
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const rotX = useSpring(useTransform(my, [-0.5, 0.5], [strength * 0.7, -strength * 0.7]), { stiffness: 150, damping: 18 });
  const rotY = useSpring(useTransform(mx, [-0.5, 0.5], [-strength, strength]), { stiffness: 150, damping: 18 });
  const onTilt = (e) => {
    if (reduceMotion) return;
    const r = e.currentTarget.getBoundingClientRect();
    mx.set((e.clientX - r.left) / r.width - 0.5);
    my.set((e.clientY - r.top) / r.height - 0.5);
  };
  const resetTilt = () => { mx.set(0); my.set(0); };
  return { rotX, rotY, onTilt, resetTilt };
}

// Drop-in card that tilts toward the cursor. Keeps children fully interactive.
export function TiltCard({ children, className = "", strength = 8, ...rest }) {
  const { rotX, rotY, onTilt, resetTilt } = useTilt(strength);
  return (
    <motion.div
      onMouseMove={onTilt}
      onMouseLeave={resetTilt}
      style={{ rotateX: rotX, rotateY: rotY, transformPerspective: 1000 }}
      className={`will-change-transform ${className}`}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

// Premium gradient brand-logo tile (monogram mark + wordmark).
export function LogoTile({ name, from, to }) {
  return (
    <span className="inline-flex items-center gap-2.5 group">
      <span className="grid place-items-center h-8 w-8 rounded-lg text-white text-[13px] font-display font-bold shadow-sm transition-transform group-hover:-translate-y-0.5"
        style={{ background: `linear-gradient(135deg, ${from}, ${to})` }}>{name[0]}</span>
      <span className="font-display font-semibold text-[15px] text-slate-600 tracking-tight">{name}</span>
    </span>
  );
}
