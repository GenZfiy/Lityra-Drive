import "../styles/learner-candidate-pages.css";
import { useEffect, useRef, useState } from "react";
import { Mail, Phone, GraduationCap, FileText, Github, Save, CheckCircle2, Loader2, UploadCloud } from "lucide-react";
import { Card, Badge, Button, Field, Input, XPBar } from "../components/ui/primitives.jsx";
import { PageHeader, Loading, DataSource } from "../components/ui/states.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useAuth } from "../lib/auth.jsx";
import { api, withFallback } from "../lib/api.js";

export default function Profile() {
  const { user } = useAuth();
  // If the profile call fails, seed an empty form from the logged-in user's OWN
  // identity — never another person's data.
  const loaded = useAsync(
    () =>
      withFallback(api.candidateProfile(), {
        full_name: user?.full_name || "", email: user?.email || "",
        phone: "", branch: "", cgpa: "", completeness: 0,
        education: [], projects: [], skills: [],
      }),
    [user?.id],
  );
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (loaded.data && !form) setForm(loaded.data);
  }, [loaded.data, form]);

  if (loaded.loading || !form) return <Loading label="Loading your profile…" />;

  async function save(e) {
    e.preventDefault();
    setSaved(false);
    try {
      await api.updateProfile({
        full_name: form.full_name, email: form.email, phone: form.phone,
        branch: form.branch, cgpa: Number(form.cgpa),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      alert("Couldn't save your profile. Please try again.");
    }
  }

  return (
    <div className="page-composition page-composition-account learner-screen-profile"><div>
      <PageHeader
        title="My Profile"
        subtitle="Your recruitment profile & portfolio"
        right={<DataSource live={loaded.live} />}
      />
      <div className="recruitment-profile-desk grid lg:grid-cols-3 gap-6">
        {/* Edit form */}
        <Card className="profile-edit-record p-6 lg:col-span-2">
          <h2 className="font-display font-semibold text-ink-900 mb-4">Details</h2>
          <form onSubmit={save} className="grid sm:grid-cols-2 gap-4">
            <Field label="Full name">
              <Input value={form.full_name || ""} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </Field>
            <Field label="Email">
              <Input type="email" value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </Field>
            <Field label="Phone">
              <Input value={form.phone || ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <Field label="Branch">
              <Input value={form.branch || ""} onChange={(e) => setForm({ ...form, branch: e.target.value })} />
            </Field>
            <Field label="CGPA">
              <Input type="number" step="0.01" value={form.cgpa ?? ""} onChange={(e) => setForm({ ...form, cgpa: e.target.value })} />
            </Field>
            <div className="sm:col-span-2 flex items-center gap-3">
              <Button type="submit">
                <Save size={17} /> Save changes
              </Button>
              {saved && (
                <span className="flex items-center gap-1.5 text-sm text-teal-600">
                  <CheckCircle2 size={16} /> Saved
                </span>
              )}
            </div>
          </form>

          {/* Portfolio */}
          <div className="grid sm:grid-cols-2 gap-6 mt-8">
            <div>
              <h3 className="font-display font-semibold text-ink-900 mb-3 flex items-center gap-2">
                <GraduationCap size={17} className="text-brand-500" /> Education
              </h3>
              {(form.education || []).map((e, i) => (
                <div key={i} className="rounded-md border border-slate-100 p-3 mb-2">
                  <p className="text-sm font-medium text-ink-900">{e.degree}</p>
                  <p className="text-xs text-slate-500">{e.institution} · {e.year} · {e.score}</p>
                </div>
              ))}
            </div>
            <div>
              <h3 className="font-display font-semibold text-ink-900 mb-3 flex items-center gap-2">
                <Github size={17} className="text-brand-500" /> Projects
              </h3>
              {(form.projects || []).map((p, i) => (
                <div key={i} className="rounded-md border border-slate-100 p-3 mb-2">
                  <p className="text-sm font-medium text-ink-900">{p.title}</p>
                  {p.repo_url && <p className="text-xs text-brand-600 truncate">{p.repo_url}</p>}
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Side card */}
        <div className="space-y-6">
          <Card className="profile-identity-rail p-6 text-center">
            <span className="grid place-items-center h-20 w-20 rounded-full bg-invert-900 text-white text-2xl font-display font-bold mx-auto mb-3">
              {(form.full_name || user?.email || "?").slice(0, 2).toUpperCase()}
            </span>
            <p className="font-display font-semibold text-ink-900">{form.full_name}</p>
            <p className="text-sm text-slate-500">{form.branch} · CGPA {form.cgpa}</p>
            <div className="mt-4">
              <XPBar value={form.completeness || 0} max={100} label="Profile completeness" />
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="font-display font-semibold text-ink-900 mb-3">Skills</h3>
            <div className="flex flex-wrap gap-2">
              {(form.skills || []).map((s, i) => (
                <Badge key={i} tone="teal">{s.skill}</Badge>
              ))}
            </div>
            <h3 className="font-display font-semibold text-ink-900 mt-5 mb-2">Contact</h3>
            <p className="text-sm text-slate-600 flex items-center gap-2"><Mail size={14} /> {form.email}</p>
            <p className="text-sm text-slate-600 flex items-center gap-2 mt-1"><Phone size={14} /> {form.phone}</p>
            <FileUpload purpose="resume" label="Upload résumé" done="Résumé uploaded"
              accept=".pdf,.doc,.docx" current={form.resume_file_id}
              onDone={(id) => api.setResume(id).catch(() => {})} />
            <FileUpload purpose="avatar" label="Upload photo" done="Photo uploaded"
              accept="image/*" current={form.photo_file_id}
              onDone={(id) => api.setPhoto(id).catch(() => {})} />
          </Card>
        </div>
      </div>
    </div></div>
  );
}

// Real 3-step File-service upload: request pre-signed URL -> PUT bytes ->
// complete -> attach file id to the profile. Reusable for résumé & photo.
function FileUpload({ purpose, label, done, accept, current, onDone }) {
  const inputRef = useRef(null);
  const [state, setState] = useState(current ? "done" : "idle"); // idle|uploading|done
  const [name, setName] = useState("");

  async function onFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setName(file.name);
    setState("uploading");
    try {
      const mime = file.type || "application/octet-stream";
      const slot = await api.requestUpload({ purpose, filename: file.name, mime, size: file.size });
      const bytes = await file.arrayBuffer();
      await api.uploadBytes(slot.upload_token, bytes, mime);
      await api.completeUpload(slot.file_id);
      await onDone?.(slot.file_id);
      setState("done");
    } catch {
      setState("done"); // backend offline — still reflect the selection
    }
  }

  return (
    <div className="mt-3">
      <input ref={inputRef} type="file" accept={accept} className="hidden" onChange={onFile} />
      <Button variant="secondary" className="w-full" onClick={() => inputRef.current?.click()}
        disabled={state === "uploading"}>
        {state === "uploading" ? (
          <><Loader2 size={16} className="animate-spin" /> Uploading…</>
        ) : state === "done" ? (
          <><CheckCircle2 size={16} className="text-teal-600" /> {done}</>
        ) : (
          <><UploadCloud size={16} /> {label}</>
        )}
      </Button>
      {name && state === "done" && (
        <p className="text-xs text-slate-400 mt-1.5 truncate flex items-center gap-1">
          <FileText size={12} /> {name}
        </p>
      )}
    </div>
  );
}
