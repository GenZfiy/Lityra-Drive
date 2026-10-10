import "../styles/learner-candidate-pages.css";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { KeyRound, ShieldCheck, LogOut, ArrowRight, Briefcase } from "lucide-react";
import { Card, Button, Field, Input } from "../components/ui/primitives.jsx";
import { Logo } from "../components/ui/Logo.jsx";
import { Orbs } from "../components/ui/Decor.jsx";
import { useAuth } from "../lib/auth.jsx";
import { api, accessGrant } from "../lib/api.js";

// Lityra Hire Access Gate. A signed-in candidate must present their Drive Access
// ID to enter a specific recruitment drive — they can only access that drive.
export default function DriveAccessGate() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      const res = await api.validateDriveAccess(code.trim());
      if (res?.grant) accessGrant.set(res.grant);
      setOk(res);
      setTimeout(() => nav("/drive"), 900);
    } catch (err) {
      setError(err.message || "Invalid Drive Access ID. Please check and try again.");
      setBusy(false);
    }
  };

  const firstName = (user?.full_name || user?.email || "there").split(/[\s@]/)[0];

  return (
    <div className="page-composition page-composition-gate learner-screen-hire-gate"><div className="min-h-screen grid place-items-center bg-invert-900 px-4 relative overflow-hidden">
      <div className="bg-grid absolute inset-0 opacity-[0.12]" />
      <Orbs tone="warm" className="opacity-70" />
      <div className="relative w-full max-w-md">
        <div className="flex justify-center mb-6"><Logo dark size={110} /></div>
        <Card className="gate-access-card p-8">
          <span className="grid place-items-center h-14 w-14 rounded-2xl bg-amber-500/10 text-amber-600 mb-4">
            <Briefcase size={26} />
          </span>
          <h1 className="font-display text-xl font-bold text-ink-900">Enter your Drive Access ID</h1>
          <p className="text-sm text-slate-500 mt-1">
            Welcome, {firstName}. Enter the Access ID shared for your recruitment drive to continue.
          </p>

          {ok ? (
            <div className="mt-6 rounded-xl border border-teal-200 bg-teal-500/10 p-4">
              <p className="flex items-center gap-2 text-teal-800 font-medium">
                <ShieldCheck size={18} /> Access granted
              </p>
              <p className="text-sm text-teal-700 mt-1">
                {[ok.drive_title, ok.company_name].filter(Boolean).join(" · ")}
              </p>
              <p className="text-xs text-slate-500 mt-2">Opening your drive…</p>
            </div>
          ) : (
            <form onSubmit={submit} className="gate-code-form mt-6 space-y-4" noValidate>
              {error && (
                <div className="rounded-md bg-rose-500/10 text-rose-600 text-sm px-3.5 py-2.5">{error}</div>
              )}
              <Field label="Drive Access ID" htmlFor="code">
                <Input
                  id="code"
                  autoFocus
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  placeholder="e.g. ACME-7KQ9"
                  className="tracking-wider font-mono"
                />
              </Field>
              <Button type="submit" variant="amber" size="lg" className="w-full" disabled={busy || !code.trim()}>
                <KeyRound size={18} /> {busy ? "Verifying…" : "Enter drive"} <ArrowRight size={18} />
              </Button>
            </form>
          )}

          <button
            onClick={async () => { await logout(); nav("/hire/login"); }}
            className="mt-5 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink-900"
          >
            <LogOut size={14} /> Sign out
          </button>
        </Card>
        <p className="mt-5 text-center text-xs text-slate-400">
          Don't have an Access ID? Contact the recruiter or your placement coordinator.
        </p>
      </div>
    </div></div>
  );
}
