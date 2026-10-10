import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Command, Building2, ListChecks, Home } from "lucide-react";
import { api } from "../../lib/api.js";

// ⌘K command palette for the Lityra Drive recruiter area. Self-contained: mounts a
// window keydown listener only where rendered (recruiter Drive pages), so it
// never affects Lityra Learn. Real data — jumps to actual drives from api.drives().
export default function CommandPalette() {
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [cur, setCur] = useState(0);
  const [drives, setDrives] = useState([]);

  useEffect(() => { api.drives().then((d) => setDrives(Array.isArray(d) ? d : [])).catch(() => {}); }, []);
  useEffect(() => {
    const h = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); setQ(""); setCur(0); }
      else if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const items = useMemo(() => {
    const base = [
      { label: "Command Center — all drives", icon: Home, run: () => nav("/drive/recruiter/drives") },
      { label: "Question Bank", icon: ListChecks, run: () => nav("/drive/recruiter/questions") },
    ];
    const dr = drives.map((d) => ({ label: `Open drive · ${d.title}`, sub: d.company_name, icon: Building2, run: () => nav(`/drive/recruiter/drives/${d.id}`) }));
    const all = [...base, ...dr];
    const query = q.trim().toLowerCase();
    return query ? all.filter((i) => i.label.toLowerCase().includes(query) || (i.sub || "").toLowerCase().includes(query)) : all;
  }, [drives, q, nav]);

  if (!open) return null;
  const go = (i) => { const it = items[i]; setOpen(false); if (it) it.run(); };

  return (
    <div
      className="fixed inset-0 z-[60] bg-invert-900/50 backdrop-blur-sm flex items-start justify-center pt-[14vh] p-4"
      onClick={() => setOpen(false)}
      onKeyDown={(e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); setCur((c) => Math.min(c + 1, items.length - 1)); }
        else if (e.key === "ArrowUp") { e.preventDefault(); setCur((c) => Math.max(c - 1, 0)); }
        else if (e.key === "Enter") { e.preventDefault(); go(cur); }
      }}
    >
      <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-surface shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-slate-100">
          <Search size={18} className="text-slate-400" />
          <input autoFocus value={q} onChange={(e) => { setQ(e.target.value); setCur(0); }} aria-label="Command palette — jump to a drive or run a command" placeholder="Jump to a drive, or run a command…" className="flex-1 outline-none text-[15px] text-ink-900 bg-transparent" />
          <kbd className="text-[10px] text-slate-400 border border-slate-200 rounded px-1.5 py-0.5">ESC</kbd>
        </div>
        <div className="max-h-[50vh] overflow-y-auto p-2">
          {items.length === 0 ? <div className="p-6 text-center text-sm text-slate-400">No matches</div> :
            items.map((i, idx) => {
              const Ic = i.icon;
              return (
                <button key={idx} onMouseEnter={() => setCur(idx)} onClick={() => go(idx)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left ${idx === cur ? "bg-brand-500/10" : "hover:bg-slate-50"}`}>
                  <Ic size={16} className="text-slate-400" />
                  <span className="flex-1 text-[13px] text-ink-900">{i.label}{i.sub && <span className="text-slate-400"> · {i.sub}</span>}</span>
                  <span className="text-[10px] text-slate-300">↵</span>
                </button>
              );
            })}
        </div>
        <div className="px-4 py-2 border-t border-slate-100 text-[11px] text-slate-400 flex items-center gap-2"><Command size={12} /> Press ⌘K anywhere in Drive</div>
      </div>
    </div>
  );
}
