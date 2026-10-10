import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Mail, KeyRound, ArrowLeft, CheckCircle2 } from "lucide-react";
import { Card, Button, Field, Input } from "../components/ui/primitives.jsx";
import { AuthLayout } from "./AuthLayout.jsx";
import { api } from "../lib/api.js";

// Two-step self-service reset: request a token by email, then set a new password.
// `?app=learn|hire` scopes the reset to that product's account (separate logins).
export default function ForgotPassword() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const product = params.get("app") === "hire" ? "hire" : "learn";
  const loginTo = product === "hire" ? "/hire/login" : "/learn/login";
  const [step, setStep] = useState("request"); // request | reset | done
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [devToken, setDevToken] = useState(null);

  async function requestReset(e) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      const r = await api.forgotPassword(email, product);
      if (r?.dev_reset_token) setDevToken(r.dev_reset_token); // dev convenience
      setStep("reset");
    } catch {
      setStep("reset"); // uniform response — never reveal if the email exists
    } finally { setBusy(false); }
  }

  async function doReset(e) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      await api.resetPassword(token, pw);
      setStep("done");
      setTimeout(() => nav(loginTo), 1800);
    } catch (ex) {
      setErr(ex.message || "Reset failed — check your token.");
    } finally { setBusy(false); }
  }

  return (
    <AuthLayout
      product={product}
      title={step === "request" ? "Reset your password" : step === "reset" ? "Choose a new password" : "Password updated"}
      subtitle={step === "request" ? "We'll email a secure reset link if the account can be recovered." : step === "reset" ? "Enter the token from your email to choose a new password." : "Your account is ready. Returning you to sign in."}
      footer={<Link to={loginTo} className="font-semibold text-brand-600 hover:underline inline-flex items-center gap-1.5"><ArrowLeft size={14} /> Back to sign in</Link>}
    >
        <Card className="auth-reset-card p-6">
          {step === "request" && (
            <>
              <form onSubmit={requestReset} className="space-y-4">
                <Field label="Email">
                  <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@college.edu" />
                </Field>
                <Button type="submit" className="w-full" disabled={busy}>
                  <Mail size={16} /> Send reset link
                </Button>
              </form>
            </>
          )}

          {step === "reset" && (
            <>
              {devToken && (
                <div className="mb-4 rounded-md bg-amber-500/10 text-amber-700 p-3 text-xs break-all">
                  Dev token: {devToken}
                </div>
              )}
              <form onSubmit={doReset} className="space-y-4">
                <Field label="Reset token">
                  <Input required value={token} onChange={(e) => setToken(e.target.value)} />
                </Field>
                <Field label="New password" error={err}>
                  <Input type="password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} />
                </Field>
                <Button type="submit" className="w-full" disabled={busy}>
                  <KeyRound size={16} /> Set new password
                </Button>
              </form>
            </>
          )}

          {step === "done" && (
            <div className="text-center py-6">
              <div className="mx-auto grid place-items-center h-14 w-14 rounded-full bg-teal-500/10 text-teal-600 mb-3">
                <CheckCircle2 size={30} />
              </div>
              <p className="font-display font-semibold text-ink-900">Password updated</p>
              <p className="text-sm text-slate-500 mt-1">Redirecting to sign in…</p>
            </div>
          )}

        </Card>
    </AuthLayout>
  );
}
