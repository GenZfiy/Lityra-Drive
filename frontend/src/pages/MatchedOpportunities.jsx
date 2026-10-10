import "../styles/learner-candidate-pages.css";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles, Target, CheckCircle2, Building2, MapPin, Clock, Briefcase,
} from "lucide-react";
import { Card, Badge, Button } from "../components/ui/primitives.jsx";
import { PageHeader, Loading, EmptyState } from "../components/ui/states.jsx";
import { api } from "../lib/api.js";

// Lityra Hire — Skills-to-Opportunity (Hire domain only). Ranks OPEN drives by how
// well the candidate's drive-exam skills match the roles. Uses only Hire data;
// no LMS content appears here.
export default function MatchedOpportunities() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try { setData(await api.matchedOpportunities()); }
      catch { setData({ matches: [], unspecified: [], has_skill_data: false }); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <Loading label="Finding matching opportunities…" />;

  const matches = data?.matches || [];
  const unspecified = data?.unspecified || [];

  return (
    <div className="page-composition page-composition-candidate learner-screen-opportunities"><div>
      <PageHeader
        title="Matched Opportunities"
        subtitle="Open drives ranked by how well your skills fit each role — with exactly which skills matched and where the gaps are."
        right={<Button as={Link} to="/drive" variant="secondary"><Briefcase size={16} /> My Drives</Button>}
      />

      {!data?.has_skill_data && (
        <Card className="p-4 mb-5 text-sm text-slate-500 flex items-center gap-2">
          <Sparkles size={16} className="text-brand-500" />
          Take part in a drive's tests to build your skill profile — matches sharpen as you do.
        </Card>
      )}

      {matches.length === 0 && unspecified.length === 0 ? (
        <EmptyState title="No open drives right now"
          hint="When companies open drives, the best-matched ones show up here first." />
      ) : (
        <section className="opportunity-matchboard space-y-5" aria-label="Matched open drives">
          {matches.map((d) => <MatchCard key={d.drive_id} d={d} />)}

          {unspecified.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3 mt-8">Other open drives</h3>
              <div className="grid sm:grid-cols-2 gap-4">
                {unspecified.map((d) => (
                  <Card key={d.drive_id} className="p-5">
                    <p className="font-medium text-ink-900">{d.title}</p>
                    <p className="text-sm text-slate-500 flex items-center gap-1.5 mt-1"><Building2 size={13} /> {d.company_name}</p>
                    <p className="mt-2 text-xs text-slate-400">No skills specified for matching.</p>
                  </Card>
                ))}
              </div>
            </div>
          )}</section>
      )}
    </div></div>
  );
}

function matchColor(pct) {
  return pct >= 75 ? "text-teal-600" : pct >= 45 ? "text-amber-600" : "text-rose-600";
}
function matchBar(pct) {
  return pct >= 75 ? "bg-teal-500" : pct >= 45 ? "bg-amber-500" : "bg-rose-500";
}

function MatchCard({ d }) {
  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="font-display text-lg font-semibold text-ink-900">{d.title}</h3>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1 text-sm text-slate-500">
            <span className="flex items-center gap-1.5"><Building2 size={13} /> {d.company_name}</span>
            {d.reporting_time && <span className="flex items-center gap-1.5"><Clock size={13} /> {d.reporting_time}</span>}
            {d.venue && <span className="flex items-center gap-1.5"><MapPin size={13} /> {d.venue}</span>}
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className={`font-display text-3xl font-bold tabular-nums ${matchColor(d.match_pct)}`}>{d.match_pct}%</p>
          <p className="text-xs text-slate-400">match</p>
        </div>
      </div>

      <div className="mt-3 h-2.5 rounded-full bg-slate-200 overflow-hidden">
        <div className={`h-full rounded-full ${matchBar(d.match_pct)} transition-all`} style={{ width: `${d.match_pct}%` }} />
      </div>

      {d.roles?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {d.roles.map((r) => (
            <span key={r.id} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              {r.title}{r.ctc ? ` · ${r.ctc}` : ""}
            </span>
          ))}
        </div>
      )}

      <div className="mt-4 grid sm:grid-cols-2 gap-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal-600 mb-2 flex items-center gap-1.5">
            <CheckCircle2 size={13} /> Your matching skills
          </p>
          {d.matched.length ? (
            <div className="flex flex-wrap gap-1.5">
              {d.matched.map((sk) => (
                <span key={sk.name} className="inline-flex items-center gap-1 rounded-full bg-teal-500/10 text-teal-700 px-2.5 py-1 text-xs font-medium">
                  {sk.name} <span className="text-teal-600/70">{sk.mastery}%</span>
                </span>
              ))}
            </div>
          ) : <p className="text-sm text-slate-400">None yet — close the gaps to qualify.</p>}
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-600 mb-2 flex items-center gap-1.5">
            <Target size={13} /> Skills to build
          </p>
          {d.missing.length ? (
            <div className="flex flex-wrap gap-1.5">
              {d.missing.map((sk) => (
                <span key={sk.name} className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 text-amber-700 px-2.5 py-1 text-xs font-medium">
                  {sk.name} <span className="text-amber-600/70">{sk.mastery}%</span>
                </span>
              ))}
            </div>
          ) : <p className="text-sm text-teal-600">You meet every required skill! 🎉</p>}
        </div>
      </div>
    </Card>
  );
}
