import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserPlus } from "lucide-react";
import { AuthLayout } from "./AuthLayout.jsx";
import { Button, Field, Input } from "../components/ui/primitives.jsx";
import { useAuth } from "../lib/auth.jsx";

const NAME = { learn: "Lityra Learn", hire: "Lityra Hire" };
const BLURB = {
  learn: "Create an account to build your skills with Lityra Learn.",
  hire: "Create your Lityra Hire account to run recruitment drives.",
};

export default function Register({ product = "learn" }) {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const home = product === "hire" ? "/drive" : "/lms";
  const loginTo = product === "hire" ? "/hire/login" : "/learn/login";

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      await register(form.email, form.password, form.full_name, product);
      nav(home);
    } catch (err) {
      setError(err.message || "Registration failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      product={product}
      title={`Create your ${NAME[product]} account`}
      subtitle={BLURB[product]}
      footer={
        <>
          Already have an account?{" "}
          <Link to={loginTo} className="font-semibold text-brand-600 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && (
          <div className="rounded-md bg-rose-500/10 text-rose-600 text-sm px-3.5 py-2.5">
            {error}
          </div>
        )}
        <Field label="Full name" htmlFor="name">
          <Input
            id="name"
            required
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="Your name"
          />
        </Field>
        <Field label="Email" htmlFor="email">
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="you@college.edu"
          />
        </Field>
        <Field label="Password" htmlFor="password" hint="At least 8 characters.">
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Create a password"
          />
        </Field>
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          <UserPlus size={18} /> {busy ? "Creating…" : "Create account"}
        </Button>
      </form>
    </AuthLayout>
  );
}
