import { useEffect, useState } from "react";
import { BarChart3, CheckCircle2, Code2, Download, Filter, Trophy, GitBranch, Target } from "lucide-react";
import { Card, Button } from "../../components/ui/primitives.jsx";
import { Loading } from "../../components/ui/states.jsx";
import { api, withFallback } from "../../lib/api.js";
import { band, bandHex, initials, hueFor } from "../../components/drive/grammar.jsx";
import { RadialGauge, Funnel, AreaChart, Donut } from "../../components/charts.jsx";
import "../../styles/recruiter-operations-pages.css";

// World-class drive analytics — a real recruitment intelligence dashboard.
// Everything derives from live data (analytics + funnel + registrations); no mocks.
export default function AnalyticsTab({ id }) {
  const [a, setA] = useState(null);
  const [f, setF] = useState(null);
  const [regs, setRegs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [sources, setSources] = useState({ funnel: true, registrations: true });

  useEffect(() => {
    (async () => {
      setLoading(true);
      const [an, fnResult, rgResult] = await Promise.all([
        api.driveAnalytics(id).catch(() => null),
        withFallback(api.funnel(id), null),
        withFallback(api.driveRegistrations(id), []),
      ]);
      setA(an); setF(fnResult.live ? fnResult.data : null); setRegs(rgResult.live && Array.isArray(rgResult.data) ? rgResult.data : []);
      setSources({ funnel: fnResult.live, registrations: rgResult.live });
      if (!an) setErr("Written-test analytics aren't available yet.");
      setLoading(false);
    })();
  }, [id]);

  async function download(cleared) {
    setBusy(cleared ? "cleared" : "all"); setErr("");
    try { await api.downloadRoundXlsx(id, 1, cleared); }
    catch (e) { setErr(e?.message || "Export failed."); }
    finally { setBusy(""); }
  }

  if (loading) return <Loading />;

  const w = a?.written || {};
  const c = a?.coding || {};
  const bs = f?.by_status || {};
  const total = a?.total_registered ?? f?.total ?? (sources.registrations ? regs.length : null);
  const totalValue = total ?? 0;

  const inFlight = f ? (bs.shortlisted || 0) + (bs.in_round || 0) : null;
  const selected = f ? (bs.selected || 0) : null;
  const rejected = f ? (bs.rejected || 0) : null;
  const screening = f ? (bs.applied || 0) : null;
  const attRate = total ? Math.round((w.attended || 0) / total * 100) : null;
  const selRate = total && selected != null ? Math.round(selected / total * 100) : null;

  const funnel = [
    { label: "Registered", value: total ?? 0, color: "#3B82F6" },
    { label: "Attended test", value: w.attended ?? 0, color: "#2563EB" },
    { label: "Cleared written", value: w.cleared ?? 0, color: "#1D4ED8" },
    { label: "In rounds", value: (inFlight ?? 0) + (selected ?? 0), color: "#0D9488" },
    { label: "Selected", value: selected ?? 0, color: "#0F766E" },
  ];

  const dist = (w.score_distribution || []).map((b) => ({ label: (b.band || "").replace(/\s|%/g, ""), value: b.count }));

  const roundMap = {};
  regs.forEach((r) => { const k = r.current_round || 0; roundMap[k] = (roundMap[k] || 0) + 1; });
  const rounds = Object.keys(roundMap).map(Number).sort((x, y) => x - y).map((k) => ({ label: k === 0 ? "Pre" : `R${k}`, value: roundMap[k] }));

  const elig = { yes: 0, no: 0, unknown: 0 };
  regs.forEach((r) => { elig[r.eligible === "yes" ? "yes" : r.eligible === "no" ? "no" : "unknown"]++; });

  const top = regs.filter((r) => r.score != null).sort((x, y) => (y.score || 0) - (x.score || 0)).slice(0, 8);
  const scored = regs.filter((r) => r.score != null).length;

  const outcome = [
    { label: "Selected", n: selected ?? 0, color: "#0D9488" },
    { label: "In flight", n: inFlight ?? 0, color: "#F59E0B" },
    { label: "Screening", n: screening ?? 0, color: "#64748b" },
    { label: "Rejected", n: rejected ?? 0, color: "#E11D48" },
  ].filter((x) => x.n > 0);

  return (
    <section className="page-composition page-composition-recruiter-detail hire-ops hire-ops--analytics"><div className="space-y-6">
      <header className="hire-ops-intro hire-analytics-lead">
        <div>
          <span className="hire-ops-kicker">Evidence · outcomes · movement</span>
          <h2 className="font-display font-semibold text-lg text-ink-900">Drive analytics</h2>
          <p className="text-sm text-slate-500">Recruitment intelligence — funnel, performance &amp; pipeline, from live data.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => download(false)} disabled={!!busy}><Download size={16} /> {busy === "all" ? "Preparing…" : "Attendees (Excel)"}</Button>
          <Button onClick={() => download(true)} disabled={!!busy}><Download size={16} /> {busy === "cleared" ? "Preparing…" : "Cleared (Excel)"}</Button>
        </div>
      </header>

      {err && <div className="rounded-md bg-amber-500/10 text-amber-700 p-3 text-sm">{err}</div>}

      {/* Conversion story paired with the funnel it describes. */}
      <div className="hire-analytics-story">
      <section className="hire-analytics-outcome rounded-2xl border border-slate-200 bg-gradient-to-br from-brand-500/[0.05] via-surface to-teal-500/[0.04] p-6" aria-label="Selection outcome summary">
        <div className="grid lg:grid-cols-[1.1fr_2fr] gap-6 items-center">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400">Selection outcome</div>
            <div className="mt-1 flex items-end gap-2">
              <span className="font-display text-5xl font-bold tracking-tight text-ink-900 tabular-nums">{selected}</span>
              <span className="text-slate-400 text-lg mb-1">/ {total}</span>
            </div>
            <p className="text-[13px] text-slate-500 mt-1">selected from the pool · <span className="font-semibold" style={{ color: bandHex(band(selRate * 4)) }}>{selRate}% conversion</span></p>
            <div className="mt-4 grid grid-cols-3 gap-3">
              {[["Attended", w.attended ?? 0], ["Cleared", w.cleared ?? 0], ["In flight", inFlight]].map(([l, v]) => (
                <div key={l}><div className="font-display text-xl font-bold text-ink-900 tabular-nums">{v}</div><div className="text-[10.5px] uppercase tracking-wider text-slate-400">{l}</div></div>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 justify-items-center">
            <div className="text-center"><RadialGauge value={attRate} label="Attendance" color="#2563EB" /></div>
            <div className="text-center"><RadialGauge value={w.pass_rate ?? 0} label="Pass rate" color="#0D9488" /></div>
            <div className="text-center"><RadialGauge value={selRate} label="Selection" color="#F59E0B" /></div>
          </div>
        </div>
      </section>

      <Card className="hire-analytics-funnel p-6">
        <div className="hire-analytics-panel-heading"><span className="hire-ops-kicker">Movement</span><h3 className="font-display font-semibold text-ink-900"><Filter size={18} className="text-brand-500" /> Recruitment funnel</h3></div>
        <p className="text-xs text-slate-400 mb-5">How the pool narrows at each stage · stage-to-stage conversion on the right</p>
        <Funnel stages={funnel} />
      </Card>
      </div>

      {/* Distribution + occupancy */}
      <div className="hire-analytics-report-grid">
      <section className="hire-analytics-trends grid lg:grid-cols-2 gap-6" aria-label="Score and pipeline trends">
        <Card className="p-6">
          <h3 className="font-display font-semibold text-ink-900 mb-1 flex items-center gap-2"><BarChart3 size={18} className="text-brand-500" /> Score distribution</h3>
          <p className="text-xs text-slate-400 mb-3">Written test · average {w.avg_percentage ?? 0}%</p>
          {w.attended ? <AreaChart data={dist} color="#2563EB" /> : <p className="text-sm text-slate-400 py-8 text-center">No written-test results yet.</p>}
        </Card>
        <Card className="p-6">
          <h3 className="font-display font-semibold text-ink-900 mb-1 flex items-center gap-2"><GitBranch size={18} className="text-teal-500" /> Pipeline occupancy</h3>
          <p className="text-xs text-slate-400 mb-3">Where candidates sit right now</p>
          {rounds.length ? <AreaChart data={rounds} color="#0D9488" /> : <p className="text-sm text-slate-400 py-8 text-center">No candidates yet.</p>}
        </Card>
      </section>

      {/* Composition donuts */}
      <section className="hire-analytics-composition grid lg:grid-cols-2 gap-6" aria-label="Eligibility and outcome composition">
        <Card className="p-6">
          <h3 className="font-display font-semibold text-ink-900 mb-4 flex items-center gap-2"><Target size={18} className="text-brand-500" /> Outcome mix</h3>
          {outcome.length ? <Donut parts={outcome} centerValue={total} centerLabel="candidates" /> : <p className="text-sm text-slate-400">No data yet.</p>}
        </Card>
        <Card className="p-6">
          <h3 className="font-display font-semibold text-ink-900 mb-4 flex items-center gap-2"><CheckCircle2 size={18} className="text-teal-500" /> Eligibility</h3>
          <Donut centerValue={regs.length} centerLabel="screened" parts={[
            { label: "Eligible", n: elig.yes, color: "#0D9488" },
            { label: "Ineligible", n: elig.no, color: "#E11D48" },
            { label: "Unscreened", n: elig.unknown, color: "#64748b" },
          ].filter((x) => x.n > 0)} />
        </Card>
      </section>

      {/* Leaderboard + coding */}
      <section className="hire-analytics-performance grid lg:grid-cols-2 gap-6" aria-label="Candidate and coding performance">
        <Card className="p-6">
          <h3 className="font-display font-semibold text-ink-900 mb-1 flex items-center gap-2"><Trophy size={18} className="text-amber-500" /> Top performers</h3>
          <p className="text-xs text-slate-400 mb-4">By real marks · {scored} of {total} scored</p>
          {top.length ? (
            <div className="space-y-2.5">
              {top.map((r, i) => {
                const nm = r.candidate_name || r.candidate_id;
                const sc = Math.round(r.score || 0);
                return (
                  <div key={r.candidate_id} className="flex items-center gap-3">
                    <span className="w-5 text-[12px] tabular-nums text-slate-400 text-right font-semibold">{i + 1}</span>
                    <span className="grid place-items-center h-8 w-8 rounded-lg text-white text-[11px] font-bold shrink-0" style={{ background: hueFor(nm) }}>{initials(nm)}</span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[12.5px] font-medium text-ink-900 truncate">{nm}</div>
                      <div className="h-1.5 rounded-full bg-slate-100 mt-1 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${sc}%`, background: bandHex(band(sc)), transition: "width 700ms cubic-bezier(.2,.8,.2,1)" }} /></div>
                    </div>
                    <span className="font-display font-bold tabular-nums text-[15px]" style={{ color: bandHex(band(sc)) }}>{sc}</span>
                  </div>
                );
              })}
            </div>
          ) : <p className="text-sm text-slate-400">No marks recorded yet.</p>}
        </Card>

        <Card className="p-6">
          <h3 className="font-display font-semibold text-ink-900 mb-4 flex items-center gap-2"><Code2 size={18} className="text-teal-500" /> Coding performance</h3>
          {c.students_with_coding ? (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 flex items-center justify-center py-1"><RadialGauge value={c.accuracy ?? 0} label="Accuracy" color="#0D9488" size={124} /></div>
              {[["With coding", c.students_with_coding], ["Attempted", c.students_attempted], ["Correct", c.total_correct], ["Total tried", c.total_attempted]].map(([l, v]) => (
                <div key={l} className="rounded-lg bg-slate-50 border border-slate-100 p-3 text-center">
                  <div className="font-display text-lg font-bold text-ink-900 tabular-nums">{v}</div>
                  <div className="text-[10.5px] uppercase tracking-wider text-slate-400">{l}</div>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-slate-400">No coding questions in this drive's written test.</p>}
        </Card>
      </section>
      </div>
    </div></section>
  );
}
