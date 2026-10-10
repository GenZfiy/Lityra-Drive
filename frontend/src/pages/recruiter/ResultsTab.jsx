import { useState } from "react";
import { Trophy, Send, Upload, Award, CheckCircle2, ExternalLink } from "lucide-react";
import { Card, Badge, Button, Input } from "../../components/ui/primitives.jsx";
import { Loading } from "../../components/ui/states.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { api, apiUrl, withFallback } from "../../lib/api.js";
import "../../styles/recruiter-operations-pages.css";

const OUTCOME_TONE = { selected: "teal", shortlist: "brand", fail: "rose", pass: "brand" };

// Render a candidate as name / email / roll, falling back to the id.
function Person({ info }) {
  const i = info || {};
  if (!i.candidate_name && !i.candidate_email) {
    return <span className="font-mono text-xs">{i.candidate_id}</span>;
  }
  return (
    <div className="leading-tight">
      <span>{i.candidate_name || i.candidate_email}</span>
      {i.candidate_email && <span className="block text-xs text-slate-400">{i.candidate_email}</span>}
      {i.candidate_roll && <span className="block text-xs text-slate-400">Roll: {i.candidate_roll}</span>}
    </div>
  );
}

export default function ResultsTab({ id }) {
  const regs = useAsync(() => withFallback(api.driveRegistrations(id), []), [id]);
  const driveA = useAsync(() => withFallback(api.drive(id), {}), [id]);
  const [scores, setScores] = useState({});
  const [cutoff, setCutoff] = useState(60);
  const [results, setResults] = useState(null);
  const [published, setPublished] = useState(false);
  const [offers, setOffers] = useState({});
  const [offerRoles, setOfferRoles] = useState({});
  const [compileError, setCompileError] = useState("");

  if (regs.loading) return <Loading />;
  const candidates = (regs.data || []).filter((r) => r.eligible !== "no");
  // Lookup so result/offer rows show real people, not UUIDs.
  const info = Object.fromEntries((regs.data || []).map((r) => [r.candidate_id, r]));
  const drive = driveA.data || {};
  const roles = drive.roles || [];
  const roleForOffer = (cid) => roles.find((role) => role.id === (offerRoles[cid] || info[cid]?.role_id)) || (roles.length === 1 ? roles[0] : null);

  async function compile() {
    setCompileError("");
    const missing = candidates.find((candidate) => scores[candidate.candidate_id] === "" || scores[candidate.candidate_id] === undefined || !Number.isFinite(Number(scores[candidate.candidate_id])) || Number(scores[candidate.candidate_id]) < 0);
    if (missing) { setCompileError(`Enter a valid non-negative final score for ${missing.candidate_name || missing.candidate_email || missing.candidate_id}.`); return; }
    if (!Number.isFinite(Number(cutoff)) || Number(cutoff) < 0 || Number(cutoff) > 100) { setCompileError("Cutoff must be between 0 and 100 percent."); return; }
    const rows = candidates.map((c) => ({
      candidate_id: c.candidate_id,
      final_score: Number(scores[c.candidate_id]),
      interview_decision: c.status === "selected" ? "select" : null,
    }));
    try {
      await api.compileResults({ drive_id: id, cutoff: Number(cutoff), rows });
      const live = await api.driveResults(id);
      setResults(live);
    } catch {
      setCompileError("Couldn't compile results. Please check the scores and try again.");
    }
  }

  async function publish() {
    try {
      await api.publishResults(id);
      setResults((rs) => (rs || []).map((r) => ({ ...r, status: "published" })));
      setPublished(true);
    } catch {
      alert("Couldn't publish results. Please try again.");
    }
  }

  async function makeOffer(cid, type) {
    try {
      const role = roleForOffer(cid);
      const out = await api.generateOffer({
        drive_id: id, candidate_id: cid, type,
        role_id: role?.id || null,
        company_name: drive.company_name || null,
        role_title: role?.title || null,
        ctc: role?.ctc || null,
      });
      setOffers((o) => ({ ...o, [cid]: out }));
    } catch {
      alert("Couldn't generate the offer. Please try again.");
    }
  }

  return (
    <section className="page-composition page-composition-recruiter-detail hire-ops hire-ops--results"><div className="space-y-6">
      {/* Compile controls */}
      <Card className="hire-results-compile p-0 overflow-hidden">
        <header className="hire-results-compile-heading"><div><span className="hire-ops-kicker">Decision room · final scoring</span><h2 className="font-display font-semibold text-ink-900">Compile drive results</h2><p>Enter each eligible candidate’s final score, set the pass threshold, then compile the ranked outcome.</p></div><Trophy size={24} aria-hidden="true" /></header>
        {compileError && <p role="alert" className="hire-drive-error mx-5 mt-4">{compileError}</p>}
        <div className="hire-results-workbench">
          <aside className="hire-results-control-rail" aria-label="Compilation settings">
            <div className="hire-results-pool"><strong>{candidates.length}</strong><span>eligible candidates in this drive</span></div>
            <label className="hire-results-cutoff"><span>Pass cutoff</span><div><Input type="number" min="0" max="100" value={cutoff} onChange={(e) => setCutoff(e.target.value)} /><b>%</b></div></label>
            <p>Scores and threshold determine the compiled shortlist and selection outcomes.</p>
            <Button onClick={compile} disabled={!candidates.length}><Trophy size={17} /> Compile results</Button>
          </aside>
          <section className="hire-results-roster" aria-label="Candidate final scores">
            <header><div><span className="hire-ops-kicker">Score entry</span><h3>Final assessment</h3></div><span>{candidates.length} rows</span></header>
            {candidates.length ? <ol>
          {candidates.map((c) => (
            <li key={c.candidate_id} className="hire-results-candidate">
              <span className="hire-results-candidate-mark" aria-hidden="true">{c.candidate_roll || "•"}</span>
              <div className="hire-results-person"><div className="text-sm font-medium text-ink-900"><Person info={c} /></div><span>Eligible for this result run</span></div>
              <Input
                type="number"
                required
                min="0"
                placeholder="Final score"
                aria-label={`Final score for ${c.candidate_name || c.candidate_email || c.candidate_id}`}
                value={scores[c.candidate_id] ?? ""}
                onChange={(e) => setScores((s) => ({ ...s, [c.candidate_id]: e.target.value }))}
              />
            </li>
          ))}
            </ol> : <p className="hire-results-roster-empty">No eligible candidates are available for final scoring.</p>}
          </section>
        </div>
      </Card>

      {/* Results table */}
      {results && (
        <Card className="p-0 overflow-hidden">
          <div className="flex items-center justify-between p-5 border-b border-slate-100">
            <h2 className="font-display font-semibold text-ink-900">Results</h2>
            <div className="flex items-center gap-3">
              {!regs.live && <span role="status" className="hire-source-state">Live candidate data is unavailable.</span>}
              {!published && (
                <Button onClick={publish}><Upload size={16} /> Publish results</Button>
              )}
              {published && <Badge tone="teal"><CheckCircle2 size={13} /> Published</Badge>}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Compiled candidate results and offer actions</caption>
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th scope="col" className="text-left font-medium px-5 py-3">Rank</th>
                  <th scope="col" className="text-left font-medium px-5 py-3">Candidate</th>
                  <th scope="col" className="text-left font-medium px-5 py-3">Score</th>
                  <th scope="col" className="text-left font-medium px-5 py-3">Outcome</th>
                  <th scope="col" className="text-right font-medium px-5 py-3">Offer</th>
                </tr>
              </thead>
              <tbody>
                {(results || []).map((r) => (
                  <tr key={r.candidate_id} className="border-t border-slate-100">
                    <td className="px-5 py-3">
                      <span className={`grid place-items-center h-7 w-7 rounded-full text-sm font-semibold ${
                        r.rank === 1 ? "bg-amber-500 text-ink-950" : "bg-slate-100 text-slate-500"
                      }`}>{r.rank}</span>
                    </td>
                    <td className="px-5 py-3 font-medium text-ink-900"><Person info={info[r.candidate_id] || { candidate_id: r.candidate_id }} /></td>
                    <td className="px-5 py-3 tabular-nums text-slate-600">{r.final_score}</td>
                    <td className="px-5 py-3"><Badge tone={OUTCOME_TONE[r.outcome] || "slate"}>{r.outcome}</Badge></td>
                    <td className="px-5 py-3 text-right">
                      {offers[r.candidate_id] ? (
                        <a
                          href={apiUrl(`/verify/offer/${offers[r.candidate_id].verify_id}`)}
                          target="_blank" rel="noreferrer"
                          className="inline-flex items-center gap-1.5 text-sm text-brand-600 hover:underline"
                        >
                          <ExternalLink size={14} /> {offers[r.candidate_id].type === "ppo" ? "PPO" : "Offer"} issued
                        </a>
                      ) : r.outcome === "selected" ? (
                        <div className="hire-offer-action">{roles.length > 1 && <label><span className="sr-only">Role for {info[r.candidate_id]?.candidate_name || r.candidate_id} offer</span><select aria-label={`Offer role for ${info[r.candidate_id]?.candidate_name || r.candidate_id}`} value={offerRoles[r.candidate_id] || info[r.candidate_id]?.role_id || ""} onChange={(e) => setOfferRoles((s) => ({ ...s, [r.candidate_id]: e.target.value }))}><option value="">Choose role</option>{roles.map((role) => <option key={role.id} value={role.id}>{role.title}{role.ctc ? ` · ${role.ctc}` : ""}</option>)}</select></label>}<Button size="sm" variant="amber" disabled={driveA.loading || (roles.length > 1 && !roleForOffer(r.candidate_id))} onClick={() => makeOffer(r.candidate_id, "ppo")}>
                          <Award size={15} /> PPO offer
                        </Button></div>
                      ) : r.outcome === "shortlist" ? (
                        <div className="hire-offer-action">{roles.length > 1 && <label><span className="sr-only">Role for {info[r.candidate_id]?.candidate_name || r.candidate_id} offer</span><select aria-label={`Offer role for ${info[r.candidate_id]?.candidate_name || r.candidate_id}`} value={offerRoles[r.candidate_id] || info[r.candidate_id]?.role_id || ""} onChange={(e) => setOfferRoles((s) => ({ ...s, [r.candidate_id]: e.target.value }))}><option value="">Choose role</option>{roles.map((role) => <option key={role.id} value={role.id}>{role.title}{role.ctc ? ` · ${role.ctc}` : ""}</option>)}</select></label>}<Button size="sm" variant="secondary" disabled={driveA.loading || (roles.length > 1 && !roleForOffer(r.candidate_id))} onClick={() => makeOffer(r.candidate_id, "offer")}>
                          <Send size={14} /> Offer
                        </Button></div>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div></section>
  );
}
