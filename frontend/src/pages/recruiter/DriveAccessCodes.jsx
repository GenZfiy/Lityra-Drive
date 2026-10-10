import { useEffect, useState } from "react";
import { KeyRound, RefreshCw, Copy, Check, Power } from "lucide-react";
import { Card, Button, Badge, Field, Input } from "../../components/ui/primitives.jsx";
import { PageHeader, Loading, EmptyState } from "../../components/ui/states.jsx";
import { api } from "../../lib/api.js";
import "../../styles/recruiter-operations-pages.css";

// Recruiter: create & manage Drive Access IDs. Each code maps to ONE drive;
// candidates present it (after Hire login) to access only that drive.
export default function DriveAccessCodes() {
  const [drives, setDrives] = useState([]);
  const [driveId, setDriveId] = useState("");
  const [label, setLabel] = useState("");
  const [codes, setCodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState("");

  async function loadCodes() {
    try { setCodes(await api.listDriveAccessCodes()); }
    catch (error) { setCodes([]); setErr(error?.message || "Drive access IDs could not be loaded."); }
  }

  useEffect(() => {
    (async () => {
      try { setDrives(await api.drives()); }
      catch (error) { setDrives([]); setErr(error?.message || "Drive list could not be loaded."); }
      await loadCodes();
      setLoading(false);
    })();
  }, []);

  const driveName = (id) => {
    const d = drives.find((x) => x.id === id);
    return d ? `${d.title}${d.company_name ? ` · ${d.company_name}` : ""}` : id;
  };
  const activeCodes = codes.filter((code) => code.status === "active").length;
  const totalUses = codes.reduce((sum, code) => sum + (Number(code.used_count) || 0), 0);

  async function create(event) {
    event?.preventDefault();
    if (!driveId) return;
    setErr(""); setBusy(true);
    try {
      await api.createDriveAccessCode({ drive_id: driveId, label: label || null });
      setLabel(""); setDriveId("");
      await loadCodes();
    } catch (e) { setErr(e.message || "Could not create the Access ID."); }
    finally { setBusy(false); }
  }
  async function toggle(c) {
    setErr("");
    try { await api.setDriveAccessCodeStatus(c.id, c.status === "active" ? "inactive" : "active"); await loadCodes(); }
    catch (error) { setErr(error?.message || "Access ID status could not be changed."); }
  }
  async function regen(c) {
    setErr("");
    try { await api.regenerateDriveAccessCode(c.id); await loadCodes(); }
    catch (error) { setErr(error?.message || "Access ID could not be regenerated."); }
  }
  async function copy(code) {
    setErr("");
    try { if (!navigator.clipboard?.writeText) throw new Error("Clipboard access is unavailable in this browser."); await navigator.clipboard.writeText(code); setCopied(code); setTimeout(() => setCopied(""), 1500); }
    catch (error) { setErr(error?.message || "Access ID could not be copied."); }
  }

  if (loading) return <Loading />;

  return (
    <main className="page-composition page-composition-recruiter hire-ops hire-ops--codes"><div>
      <header className="hire-ops-intro hire-codes-intro"><div><span className="hire-ops-kicker">Candidate entry · scoped access</span><PageHeader
        title="Drive Access IDs"
        subtitle="One secure code per recruitment drive. Candidates sign in and enter it to access only that drive."
      /></div><dl className="hire-codes-readouts"><div><dt>Active IDs</dt><dd>{activeCodes}</dd></div><div><dt>Total IDs</dt><dd>{codes.length}</dd></div><div><dt>Entries used</dt><dd>{totalUses}</dd></div></dl></header>
      {err && <p role="alert" className="hire-drive-error">{err}</p>}

      <div className="hire-codes-layout"><Card className="hire-codes-create p-6 mb-6">
        <div className="hire-codes-form-head"><span>01</span><div><p className="hire-ops-kicker">Issue credentials</p><h3 className="font-display font-semibold text-ink-900">Create a drive ID</h3><p>Assign the access credential to one drive and label the intended audience.</p></div></div>
        <form className="hire-codes-fields" onSubmit={create}>
          <Field label="Drive">
            <select required value={driveId} onChange={(e) => setDriveId(e.target.value)}
              className="w-full h-11 rounded-lg border border-slate-200 bg-surface px-3 text-sm">
              <option value="">Select drive…</option>
              {drives.map((d) => <option key={d.id} value={d.id}>{d.title}{d.company_name ? ` · ${d.company_name}` : ""}</option>)}
            </select>
          </Field>
          <Field label="Label (optional)">
            <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Campus A batch" />
          </Field>
          <Button type="submit" variant="amber" disabled={busy || !driveId}>
            <KeyRound size={16} /> {busy ? "Generating…" : "Generate"}
          </Button>
        </form>
      </Card>

      <section className="hire-code-ledger" aria-label="Drive access code ledger"><header className="hire-code-ledger-heading"><div><p className="hire-ops-kicker">02 · Credential ledger</p><h2>Access by drive</h2><p>Copy, rotate, or suspend a credential. Each code stays scoped to its assigned drive.</p></div></header>{codes.length === 0 ? (
        <EmptyState title="No Drive Access IDs yet" hint="Generate one above for a drive to let its candidates in." />
      ) : (
        <ol className="hire-code-list">
          {codes.map((c, index) => <li key={c.id} className="hire-code-record">
            <div className="hire-code-record-index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</div>
            <div className="hire-code-record-main">
              <div className="hire-code-identity">
                <button onClick={() => copy(c.code)} aria-label={`${copied === c.code ? "Copied" : "Copy"} access ID ${c.code}`} className="hire-code-value font-mono font-semibold hover:text-amber-600">
                  <span>{c.code}</span>{copied === c.code ? <Check size={15} className="text-teal-600" /> : <Copy size={14} className="text-slate-400" />}
                </button>
                <Badge tone={c.status === "active" ? "teal" : "slate"}>{c.status}</Badge>
              </div>
              <h3>{driveName(c.drive_id)}</h3>
              {c.label && <p>{c.label}</p>}
            </div>
            <div className="hire-code-usage"><strong>{c.used_count}</strong><span>uses</span></div>
            <div className="hire-code-actions">
              <Button variant="secondary" size="sm" onClick={() => toggle(c)}><Power size={14} /> {c.status === "active" ? "Deactivate" : "Activate"}</Button>
              <Button variant="secondary" size="sm" onClick={() => regen(c)}><RefreshCw size={14} /> Regenerate</Button>
            </div>
          </li>)}
        </ol>
      )}</section></div>
    </div></main>
  );
}
