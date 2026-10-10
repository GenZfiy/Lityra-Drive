import "../styles/learner-candidate-pages.css";
import { useState } from "react";
import { Bell, Mail, ShieldCheck, MailCheck, CheckCircle2 } from "lucide-react";
import { Card, Badge, Button } from "../components/ui/primitives.jsx";
import { PageHeader } from "../components/ui/states.jsx";
import { useAuth } from "../lib/auth.jsx";
import { api } from "../lib/api.js";

// Account settings: notification preferences + email verification.
export default function Settings() {
  const { user } = useAuth();
  const [prefs, setPrefs] = useState({ inapp: true, email: true, sms: false });
  const [flash, setFlash] = useState(null);
  const [verifySent, setVerifySent] = useState(false);

  async function toggle(channel) {
    const next = !prefs[channel];
    setPrefs({ ...prefs, [channel]: next });
    try { await api.setNotifyPref(channel, next); } catch { /* demo */ }
    setFlash(`${channel} notifications ${next ? "enabled" : "disabled"}`);
  }

  async function resendVerify() {
    try { await api.requestEmailVerify(); } catch { /* demo */ }
    setVerifySent(true);
    setFlash("Verification email sent.");
  }

  return (
    <div className="page-composition page-composition-account learner-screen-settings"><div>
      <PageHeader title="Settings" subtitle="Manage your account and notifications" />
      {flash && (
        <div className="mb-5 rounded-md bg-brand-500/10 text-brand-700 p-3 text-sm flex items-center gap-2">
          <CheckCircle2 size={15} /> {flash}
        </div>
      )}

      <div className="settings-workbench grid lg:grid-cols-2 gap-6">
        <Card className="settings-panel settings-notifications p-6">
          <h2 className="font-display font-semibold text-ink-900 mb-4 flex items-center gap-2">
            <Bell size={18} className="text-brand-500" /> Notification preferences
          </h2>
          <div className="space-y-3">
            {[
              { key: "inapp", label: "In-app inbox", icon: Bell },
              { key: "email", label: "Email", icon: Mail },
              { key: "sms", label: "SMS", icon: MailCheck },
            ].map(({ key, label, icon: Icon }) => (
              <div key={key} className="flex items-center justify-between p-3 rounded-md border border-slate-100">
                <span className="flex items-center gap-2.5 text-sm text-ink-900">
                  <Icon size={16} className="text-slate-400" /> {label}
                </span>
                <button
                  onClick={() => toggle(key)}
                  className={`relative h-6 w-11 rounded-full transition-colors ${prefs[key] ? "bg-brand-500" : "bg-slate-300"}`}
                  aria-label={`Toggle ${label}`}
                >
                  <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-surface transition-transform ${prefs[key] ? "translate-x-5" : "translate-x-0.5"}`} />
                </button>
              </div>
            ))}
          </div>
        </Card>

        <Card className="settings-panel settings-account p-6">
          <h2 className="font-display font-semibold text-ink-900 mb-4 flex items-center gap-2">
            <ShieldCheck size={18} className="text-teal-500" /> Account
          </h2>
          <div className="space-y-3 text-sm">
            <Row label="Name" value={user?.full_name || "—"} />
            <Row label="Email" value={user?.email || "—"} />
            <div className="flex items-center justify-between p-3 rounded-md border border-slate-100">
              <span className="text-slate-500">Email verified</span>
              {user?.email_verified ? (
                <Badge tone="teal"><CheckCircle2 size={12} /> verified</Badge>
              ) : (
                <Button size="sm" variant="secondary" onClick={resendVerify} disabled={verifySent}>
                  {verifySent ? "Sent" : "Verify now"}
                </Button>
              )}
            </div>
            <div className="flex items-center justify-between p-3 rounded-md border border-slate-100">
              <span className="text-slate-500">Roles</span>
              <div className="flex gap-1.5 flex-wrap justify-end">
                {(user?.roles || ["student"]).map((r) => <Badge key={r} tone="slate">{r}</Badge>)}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div></div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between p-3 rounded-md border border-slate-100">
      <span className="text-slate-500">{label}</span>
      <span className="text-ink-900 font-medium">{value}</span>
    </div>
  );
}
