import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogIn, KeyRound, Mail } from "lucide-react";
import { AuthLayout } from "./AuthLayout.jsx";
import { Button, Field, Input } from "../components/ui/primitives.jsx";
import { useAuth } from "../lib/auth.jsx";
import { api } from "../lib/api.js";

const NAME = { learn: "Lityra Learn", hire: "Lityra Hire" };

export default function Login({ product = "learn", audience = "" }) {
  const { login, loginOtp } = useAuth();
  const nav = useNavigate();
  const isTrainerLogin = audience === "trainer";
  const home = isTrainerLogin ? "/lms/trainer" : product === "hire" ? "/drive" : "/lms";
  const registerTo = product === "hire" ? "/hire/register" : "/learn/register";

  const [mode, setMode] = useState("password"); // password | otp
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  // OTP flow
  const [otpSent, setOtpSent] = useState(false);
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState("");

  function switchMode(m) {
    setMode(m); setError(""); setInfo(""); setOtpSent(false); setCode(""); setDevCode("");
  }

  const submitPassword = async (e) => {
    e.preventDefault(); setError(""); setBusy(true);
    try { await login(form.email, form.password, product); nav(home); }
    catch (err) { setError(err.message || "Sign in failed"); }
    finally { setBusy(false); }
  };

  const sendCode = async (e) => {
    e.preventDefault(); setError(""); setInfo(""); setBusy(true);
    try {
      const r = await api.requestOtp(form.email, product);
      setOtpSent(true);
      setInfo(`We sent a 6-digit code to ${form.email}. It expires in 10 minutes.`);
      if (r?.dev_code) setDevCode(r.dev_code); // dev convenience only
    } catch (err) { setError(err.message || "Couldn't send a code"); }
    finally { setBusy(false); }
  };

  const verifyCode = async (e) => {
    e.preventDefault(); setError(""); setBusy(true);
    try { await loginOtp(form.email, code, product); nav(home); }
    catch (err) { setError(err.message || "Invalid or expired code"); }
    finally { setBusy(false); }
  };

  return (
    <AuthLayout
      product={product}
      title={isTrainerLogin ? "Trainer sign in" : `Sign in to ${NAME[product]}`}
      subtitle={isTrainerLogin
        ? "Sign in with your assigned trainer account to open the faculty workspace."
        : mode === "otp"
        ? "We'll email you a one-time code — no password needed."
        : "Separate account per app — this signs you into this product only."}
      footer={
        <>
          {isTrainerLogin ? (
            <>Trainer access is assigned by your institution administrator. <Link to="/learn/login" className="font-semibold text-brand-600 hover:underline">Learn sign in</Link></>
          ) : (
            <>New here?{" "}<Link to={registerTo} className="font-semibold text-brand-600 hover:underline">Create a {NAME[product]} account</Link></>
          )}
        </>
      }
    >
      {error && <div className="rounded-md bg-rose-500/10 text-rose-600 text-sm px-3.5 py-2.5 mb-4">{error}</div>}
      {info && <div className="rounded-md bg-teal-500/10 text-teal-700 text-sm px-3.5 py-2.5 mb-4">{info}</div>}
      {devCode && <div className="rounded-md bg-amber-500/10 text-amber-700 text-xs px-3.5 py-2 mb-4 break-all">Dev code: {devCode}</div>}

      {mode === "password" ? (
        <form onSubmit={submitPassword} className="space-y-4" noValidate>
          <Field label="Email" htmlFor="email">
            <Input id="email" type="email" autoComplete="email" required value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@college.edu" />
          </Field>
          <Field label="Password" htmlFor="password">
            <Input id="password" type="password" autoComplete="current-password" required value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="••••••••" />
          </Field>
          <div className="flex justify-end -mt-1">
            <Link to={`/forgot-password?app=${product}`} className="text-sm text-brand-600 hover:underline">
              Forgot password?
            </Link>
          </div>
          <Button type="submit" size="lg" className="w-full" disabled={busy}>
            <LogIn size={18} /> {busy ? "Signing in…" : "Sign in"}
          </Button>
          <button type="button" onClick={() => switchMode("otp")}
            className="w-full text-sm text-slate-500 hover:text-ink-900 flex items-center justify-center gap-1.5">
            <KeyRound size={14} /> Sign in with a code instead
          </button>
        </form>
      ) : (
        <div className="space-y-4">
          {!otpSent ? (
            <form onSubmit={sendCode} className="space-y-4" noValidate>
              <Field label="Email" htmlFor="otp-email">
                <Input id="otp-email" type="email" autoComplete="email" required value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@college.edu" />
              </Field>
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                <Mail size={18} /> {busy ? "Sending…" : "Email me a code"}
              </Button>
            </form>
          ) : (
            <form onSubmit={verifyCode} className="space-y-4" noValidate>
              <Field label="6-digit code" htmlFor="otp-code">
                <Input id="otp-code" inputMode="numeric" maxLength={6} required value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="123456" />
              </Field>
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                <LogIn size={18} /> {busy ? "Verifying…" : "Sign in"}
              </Button>
              <button type="button" onClick={() => { setOtpSent(false); setCode(""); setInfo(""); setDevCode(""); }}
                className="w-full text-sm text-slate-500 hover:text-ink-900">
                Use a different email
              </button>
            </form>
          )}
          <button type="button" onClick={() => switchMode("password")}
            className="w-full text-sm text-slate-500 hover:text-ink-900 flex items-center justify-center gap-1.5">
            <KeyRound size={14} /> Use password instead
          </button>
        </div>
      )}
    </AuthLayout>
  );
}
