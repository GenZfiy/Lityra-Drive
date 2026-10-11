// Thin fetch client for the Lityra API. Talks to /api (dev-proxied to the Gateway
// at :8000, which routes onward to every service). Handles the
// { data, meta, errors } envelope and JWT tokens.

const PRODUCT_NAMESPACE = import.meta.env.VITE_PRODUCT_ID || "combined";
const TOKEN_SUFFIX = PRODUCT_NAMESPACE === "combined" ? "" : `_${PRODUCT_NAMESPACE}`;
const ACCESS_KEY = `lare_access${TOKEN_SUFFIX}`;
const REFRESH_KEY = `lare_refresh${TOKEN_SUFFIX}`;

// In production set VITE_API_BASE_URL to the Render gateway origin (for
// example https://lityra-api.onrender.com). Keeping /api as the default
// preserves the Vite development proxy and same-origin deployments.
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
const usesDevTunnel = API_BASE.includes(".devtunnels.ms");
export const apiUrl = (path) => `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

// Dev Tunnels can show an anti-phishing interstitial to browser API requests.
// Send its bypass header only when this frontend is explicitly configured to
// use a Dev Tunnel; normal local and production API requests stay unchanged.
function apiHeaders(headers = {}) {
  return usesDevTunnel
    ? { "X-Tunnel-Skip-AntiPhishing-Page": "true", ...headers }
    : headers;
}

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set({ access_token, refresh_token }) {
    if (access_token) localStorage.setItem(ACCESS_KEY, access_token);
    if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

// LMS Access Gate grant. Kept in sessionStorage so it clears when the browser
// session ends — a fresh sign-in must re-enter the class Access ID.
const GRANT_KEY = `lare_access_grant${TOKEN_SUFFIX}`;
export const accessGrant = {
  get value() { return sessionStorage.getItem(GRANT_KEY); },
  set(v) { if (v) sessionStorage.setItem(GRANT_KEY, v); },
  clear() { sessionStorage.removeItem(GRANT_KEY); },
};

export class ApiError extends Error {
  constructor(message, code, status, details) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

// Silently exchange the refresh token for a new access token. De-duplicated so a
// burst of concurrent 401s triggers only one refresh, and everyone awaits it.
// Returns "ok" | "expired" (refresh token invalid → log out) | "error"
// (network/server blip → keep the session, do NOT log out).
let _refreshing = null;
async function refreshAccess() {
  if (_refreshing) return _refreshing;
  const rt = tokens.refresh;
  if (!rt) return "expired";
  _refreshing = (async () => {
    try {
      const res = await fetch(apiUrl("/auth/v1/refresh"), {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (res.ok) {
        const payload = await res.json();
        if (payload?.data?.access_token) { tokens.set(payload.data); return "ok"; }
        return "error";
      }
      // Only a 401/403 means the refresh token itself is invalid/expired.
      // 5xx / anything else is transient — never nuke the session for it.
      return res.status === 401 || res.status === 403 ? "expired" : "error";
    } catch {
      return "error"; // network failure (e.g. tunnel hiccup) — keep session
    } finally {
      _refreshing = null;
    }
  })();
  return _refreshing;
}

// Server-Sent-Events stream over fetch (so we can send the Bearer header, which
// EventSource cannot). Calls onData(parsedJson) per `data:` frame; returns a
// stop() function. Silently no-ops on abort/network error — callers keep their
// last-known state (e.g. the polling fallback).
export function sseStream(path, onData) {
  const ctrl = new AbortController();
  (async () => {
    try {
      const headers = { Accept: "text/event-stream" };
      if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
      const res = await fetch(apiUrl(path), { headers: apiHeaders(headers), signal: ctrl.signal });
      if (!res.ok || !res.body) return;
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n\n")) >= 0) {
          const frame = buf.slice(0, i); buf = buf.slice(i + 2);
          const line = frame.split("\n").find((l) => l.startsWith("data:"));
          if (line) { try { onData(JSON.parse(line.slice(5).trim())); } catch { /* ignore */ } }
        }
      }
    } catch { /* aborted or network — fallback poll covers it */ }
  })();
  return () => ctrl.abort();
}

async function request(path, opts = {}) {
  const { method = "GET", body, auth = true, raw = false, _retried = false } = opts;
  const headers = { "Content-Type": "application/json" };
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  if (accessGrant.value) headers["X-Access-Grant"] = accessGrant.value;

  const res = await fetch(apiUrl(path), {
    method,
    headers: apiHeaders(headers),
    body: body ? JSON.stringify(body) : undefined,
    // Never let the browser reuse a cached response: these are per-user (the
    // cache key is the URL, not the token), so on a shared machine a cached
    // /me would leak the previous user's profile to the next student.
    cache: "no-store",
  });

  // Access token expired mid-session: refresh once and replay the request, so a
  // long session never dumps the user back to login. This runs BEFORE the raw
  // return so binary downloads (xlsx exports, PDFs) also recover — previously
  // they 401'd mid-drive and showed "Session expired" despite a valid session.
  // Only clear the session when the refresh token is genuinely invalid
  // ("expired") — a transient network/server error keeps the session to retry.
  if (res.status === 401 && auth && !_retried && tokens.refresh) {
    const outcome = await refreshAccess();
    if (outcome === "ok") {
      return request(path, { ...opts, _retried: true });
    }
    if (outcome === "expired") {
      tokens.clear();
    }
    // outcome === "error": leave tokens in place; surface the 401 to the caller.
  }

  if (raw) return res;

  let payload = null;
  try {
    payload = await res.json();
  } catch {
    /* empty / non-JSON */
  }

  if (!res.ok) {
    const err = payload?.errors?.[0];
    // LMS Access Gate: grant missing/expired → drop it and send the student to
    // the gate (unless they're already there).
    if (err?.code === "access_gate_required") {
      accessGrant.clear();
      const gate = path.startsWith("/drive") ? "/drive/access-gate" : "/lms/access-gate";
      if (!location.pathname.endsWith("/access-gate")) location.assign(gate);
    }
    throw new ApiError(
      err?.message || `Request failed (${res.status})`,
      err?.code,
      res.status,
      err?.details,
    );
  }
  return payload?.data;
}

export const api = {
  // ---- auth ----
  // `product` scopes the account to one app — "learn" or "hire". Accounts are
  // separate per product (same email may exist in both with different passwords).
  register: (email, password, full_name, product = "learn") =>
    request("/auth/v1/register", { method: "POST", auth: false, body: { email, password, full_name, product } }),
  login: (email, password, product = "learn") =>
    request("/auth/v1/login", { method: "POST", auth: false, body: { email, password, device: "web", product } }),
  refresh: (refresh_token) =>
    request("/auth/v1/refresh", { method: "POST", auth: false, body: { refresh_token } }),
  forgotPassword: (email, product = "learn") =>
    request("/auth/v1/password/forgot", { method: "POST", auth: false, body: { email, product } }),
  resetPassword: (token, new_password) =>
    request("/auth/v1/password/reset", { method: "POST", auth: false, body: { token, new_password } }),
  requestOtp: (email, product = "learn") =>
    request("/auth/v1/otp/request", { method: "POST", auth: false, body: { email, product } }),
  verifyOtp: (email, code, product = "learn") =>
    request("/auth/v1/otp/verify", { method: "POST", auth: false, body: { email, code, device: "web", product } }),
  requestEmailVerify: () => request("/auth/v1/email/verify/request", { method: "POST" }),
  confirmEmail: (token) =>
    request("/auth/v1/email/confirm", { method: "POST", auth: false, body: { token } }),
  setNotifyPref: (channel, enabled) =>
    request("/notify/v1/preferences", { method: "PUT", body: { channel, enabled } }),
  setPhoto: (photo_file_id) =>
    request("/drive/v1/candidate/photo", { method: "POST", body: { photo_file_id } }),
  logout: (refresh_token) =>
    request("/auth/v1/logout", { method: "POST", auth: false, body: { refresh_token } }),
  me: () => request("/auth/v1/me"),

  // ---- RBAC administration (roles & permissions) ----
  listRoles: () => request("/auth/v1/roles"),
  listPermissions: () => request("/auth/v1/permissions"),
  createRole: (body) => request("/auth/v1/roles", { method: "POST", body }),
  cloneRole: (id, body) => request(`/auth/v1/roles/${id}/clone`, { method: "POST", body }),
  updateRole: (id, body) => request(`/auth/v1/roles/${id}`, { method: "PATCH", body }),
  deleteRole: (id) => request(`/auth/v1/roles/${id}`, { method: "DELETE" }),
  assignRole: (body) => request("/auth/v1/roles/assign", { method: "POST", body }),
  unassignRole: (body) => request("/auth/v1/roles/unassign", { method: "POST", body }),

  // ---- LMS Access Gate ----
  validateAccess: (code) => request("/lms/v1/access/validate", { method: "POST", body: { code } }),
  myAccess: () => request("/lms/v1/access/me"),
  exitAccess: () => request("/lms/v1/access/exit", { method: "POST" }),
  // admin — manage access codes
  createAccessCode: (body) => request("/lms/v1/access/codes", { method: "POST", body }),
  listAccessCodes: (cohortId) => request(`/lms/v1/access/codes${cohortId ? `?cohort_id=${cohortId}` : ""}`),
  setAccessCodeStatus: (id, status) => request(`/lms/v1/access/codes/${id}/status`, { method: "POST", body: { status } }),
  regenerateAccessCode: (id) => request(`/lms/v1/access/codes/${id}/regenerate`, { method: "POST" }),

  // ---- LMS ----
  curriculumTree: (id) => request(`/lms/v1/curricula/${id}/tree`),
  curricula: () => request("/lms/v1/curricula"),
  playlist: (learnerId, lessonId) =>
    request(`/lms/v1/content/playlist?learner_id=${learnerId}${lessonId ? `&lesson_id=${lessonId}` : ""}`),
  recommendations: (learnerId) =>
    request(`/lms/v1/content/recommendations?learner_id=${learnerId}`),
  contentProgress: (contentId, learnerId, position, completed) =>
    request(`/lms/v1/content/${contentId}/progress`, {
      method: "POST",
      body: { learner_id: learnerId, position_sec: position, completed },
    }),
  progressSummary: (learnerId) => request(`/lms/v1/progress/${learnerId}`),
  scorecard: (learnerId) => request(`/lms/v1/progress/${learnerId}/scorecard`),
  game: (learnerId) => request(`/lms/v1/gamification/${learnerId}`),
  leaderboard: () => request("/lms/v1/gamification/leaderboard/global"),
  certificates: (learnerId) => request(`/lms/v1/certificates/for/${learnerId}`),
  downloadCertificatePdf: async (certId, certNo) => {
    const res = await request(`/lms/v1/certificates/${certId}/pdf`, { raw: true });
    if (!res.ok) throw new Error("Download failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `certificate-${certNo || certId}.pdf`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  },
  assessmentSummary: (learnerId) => request(`/lms/v1/assessments/summary?learner_id=${learnerId}`),

  // ---- Drive Access Gate ----
  validateDriveAccess: (code) => request("/drive/v1/access/validate", { method: "POST", body: { code } }),
  exitDriveAccess: () => request("/drive/v1/access/exit", { method: "POST" }),
  createDriveAccessCode: (body) => request("/drive/v1/access/codes", { method: "POST", body }),
  listDriveAccessCodes: (driveId) => request(`/drive/v1/access/codes${driveId ? `?drive_id=${driveId}` : ""}`),
  setDriveAccessCodeStatus: (id, status) => request(`/drive/v1/access/codes/${id}/status`, { method: "POST", body: { status } }),
  regenerateDriveAccessCode: (id) => request(`/drive/v1/access/codes/${id}/regenerate`, { method: "POST" }),

  // ---- Drive (candidate) ----
  drives: (status) => request(`/drive/v1/drives${status ? `?status=${status}` : ""}`),
  drive: (id) => request(`/drive/v1/drives/${id}`),
  myRound: (driveId) => request(`/drive/v1/drives/${driveId}/my-round`),

  // ---- Drive (recruiter/admin management) ----
  createDrive: (body) => request("/drive/v1/drives", { method: "POST", body }),
  driveInvitations: () => request("/drive/v1/invitations"),
  respondDriveInvitation: (driveId, kind, participantId, decision) =>
    request(`/drive/v1/drives/${driveId}/participation/${kind}/${encodeURIComponent(participantId)}`, { method: "POST", body: { decision } }),
  inviteDriveColleges: (driveId, college_ids) => request(`/drive/v1/drives/${driveId}/institutions/invite`, { method: "POST", body: { college_ids } }),
  inviteDriveCompanies: (driveId, company_ids, adopting = false) => request(`/drive/v1/drives/${driveId}/companies/invite`, { method: "POST", body: { company_ids, adopting } }),
  transitionDrive: (driveId, status) => request(`/drive/v1/drives/${driveId}/transition`, { method: "POST", body: { status } }),
  deleteDrive: (id) => request(`/drive/v1/drives/${id}`, { method: "DELETE" }),
  addRole: (id, body) => request(`/drive/v1/drives/${id}/roles`, { method: "POST", body }),
  setEligibility: (id, body) => request(`/drive/v1/drives/${id}/eligibility`, { method: "POST", body }),
  addRound: (id, body) => request(`/drive/v1/drives/${id}/rounds`, { method: "POST", body }),
  getWorkflow: (id) => request(`/drive/v1/drives/${id}/workflow`),
  setWorkflow: (id, stages) => request(`/drive/v1/drives/${id}/workflow`, { method: "PUT", body: { stages } }),
  deleteRound: (id, order) => request(`/drive/v1/drives/${id}/rounds/${order}`, { method: "DELETE" }),
  roundScores: (id, order) => request(`/drive/v1/drives/${id}/rounds/${order}/scores`),
  setRoundScore: (id, order, body) => request(`/drive/v1/drives/${id}/rounds/${order}/scores`, { method: "POST", body }),
  addRoundCandidate: (id, order, candidate_id) => request(`/drive/v1/drives/${id}/rounds/${order}/candidates`, { method: "POST", body: { candidate_id } }),
  removeRoundCandidate: (id, order, candidate_id) => request(`/drive/v1/drives/${id}/rounds/${order}/candidates/${candidate_id}`, { method: "DELETE" }),
  publishRound: (id, order) => request(`/drive/v1/drives/${id}/rounds/${order}/publish`, { method: "POST" }),
  openDrive: (id) => request(`/drive/v1/drives/${id}/open`, { method: "POST" }),
  registerCandidate: (id, body) => request(`/drive/v1/drives/${id}/register`, { method: "POST", body }),
  shortlist: (id, candidate_ids) => request(`/drive/v1/drives/${id}/shortlist`, { method: "POST", body: { candidate_ids } }),
  advance: (id, candidate_id) => request(`/drive/v1/drives/${id}/advance`, { method: "POST", body: { candidate_id } }),
  funnel: (id) => request(`/drive/v1/drives/${id}/funnel`),
  // Lityra Hire — a candidate's verified skill tags from real drive-exam performance.
  candidateSkills: (candidateId) => request(`/drive/v1/evaluations/twin/${candidateId}`),
  // Cognitive Twin v0.1 (Lityra Learn) — a learner's skill profile from their LMS
  // assessment history. Separate from Lityra Hire's evaluation data.
  skillTwin: (learnerId) => request(`/lms/v1/assessments/twin/${learnerId}`),
  // AI Coach — the learner's persistent study plan. force=true regenerates it.
  skillCoach: (learnerId, force = false) =>
    request(`/lms/v1/assessments/coach/${learnerId}${force ? "?force=1" : ""}`),
  // Mark a plan day done/undone (persisted progress against the plan).
  coachProgress: (learnerId, day, done) =>
    request(`/lms/v1/assessments/coach/${learnerId}/progress`, { method: "POST", body: { day, done } }),
  // Nudge: send the learner their weakest area + plan via in-app + email.
  nudgePlan: (learnerId) => request(`/lms/v1/assessments/nudge/${learnerId}`, { method: "POST" }),
  // Lityra Learn — coding practice bank (feeds the Skill Map). Same sandbox as
  // Drive coding rounds, but a student-facing practice surface.
  practiceProblems: (params = "") => request(`/lms/v1/practice/problems${params}`),
  practiceOpen: (problem_id, language) =>
    request("/lms/v1/practice/session", { method: "POST", body: { problem_id, language } }),
  practiceRun: (sid, code) =>
    request(`/lms/v1/practice/${sid}/run`, { method: "POST", body: { code } }),
  practiceSubmit: (sid, code) =>
    request(`/lms/v1/practice/${sid}/submit`, { method: "POST", body: { code } }),
  practiceSkills: (learnerId) => request(`/lms/v1/practice/skills/${learnerId}`),
  // Adversarial viva — prove you understand your own solution (cheat-resistant).
  vivaStart: (sid) => request(`/lms/v1/practice/${sid}/viva`, { method: "POST" }),
  vivaGrade: (vivaId, answer) =>
    request(`/lms/v1/practice/viva/${vivaId}`, { method: "POST", body: { answer } }),
  // Lityra Learn — Skills-to-Opportunity: career-role readiness from the LMS twin.
  careerReadiness: (learnerId) => request(`/lms/v1/careers/readiness/${learnerId}`),
  listCareers: () => request("/lms/v1/careers"),
  createCareer: (body) => request("/lms/v1/careers", { method: "POST", body }),
  deleteCareer: (cid) => request(`/lms/v1/careers/${cid}`, { method: "DELETE" }),
  // Lityra Hire — Skills-to-Opportunity: open drives matched to a candidate's skills.
  matchedOpportunities: (candidateId) =>
    request(`/drive/v1/opportunities${candidateId ? `?candidate_id=${candidateId}` : ""}`),
  // Lityra Learn — Lifelong Reinforcement: forgetting-aware spaced review queue.
  reviewQueue: (learnerId) => request(`/lms/v1/reviews/${learnerId}`),
  submitReview: (learnerId, skill, outcome) =>
    request(`/lms/v1/reviews/${learnerId}/review`, { method: "POST", body: { skill, outcome } }),
  // Lityra Learn — Embodied Practice Worlds: browser workplace simulations.
  listWorlds: () => request("/lms/v1/worlds"),
  startWorld: (worldId) => request(`/lms/v1/worlds/${worldId}/start`, { method: "POST" }),
  answerWorld: (runId, step_id, choice) =>
    request(`/lms/v1/worlds/runs/${runId}/answer`, { method: "POST", body: { step_id, choice } }),
  // Lityra Learn — Generative Learning Fabric: on-demand AI micro-lessons.
  generateLesson: (learnerId, topic, force = false) =>
    request(`/lms/v1/micro-lessons/${learnerId}/generate`, { method: "POST", body: { topic, force } }),
  listLessons: (learnerId) => request(`/lms/v1/micro-lessons/${learnerId}`),
  // Author-facing: AI-generate lesson blocks to review + save into a curriculum lesson.
  authorBlocks: (topic) => request("/lms/v1/micro-lessons/author-blocks", { method: "POST", body: { topic } }),
  // Lityra Learn — Human Knowledge Mesh: AI-matched peer teach-back.
  meshOverview: (learnerId) => request(`/lms/v1/mesh/${learnerId}`),
  meshSessions: (learnerId) => request(`/lms/v1/mesh/${learnerId}/sessions`),
  meshRequest: (topic, mentor_id, note) =>
    request("/lms/v1/mesh/request", { method: "POST", body: { topic, mentor_id, note } }),
  meshRespond: (sessionId, accept) =>
    request(`/lms/v1/mesh/${sessionId}/respond`, { method: "POST", body: { accept } }),
  meshComplete: (sessionId) => request(`/lms/v1/mesh/${sessionId}/complete`, { method: "POST" }),
  // Lityra Learn — Flow layer: adaptive drill that tunes difficulty in real time.
  drillStart: (topic, target) =>
    request("/lms/v1/drill/start", { method: "POST", body: { topic: topic || null, target: target || 8 } }),
  drillAnswer: (drillId, item_id, option, elapsed_ms) =>
    request(`/lms/v1/drill/${drillId}/answer`, { method: "POST", body: { item_id, option, elapsed_ms } }),
  // Lityra Learn — Sovereign Learning Wallet: signed, verifiable competence record.
  getWallet: (learnerId) => request(`/lms/v1/wallet/${learnerId}`),
  issueWallet: (learnerId) => request(`/lms/v1/wallet/${learnerId}/issue`, { method: "POST" }),
  revokeWallet: (learnerId) => request(`/lms/v1/wallet/${learnerId}/revoke`, { method: "POST" }),
  verifyWallet: (verifyId) => request(`/verify/wallet/${verifyId}`, { auth: false }),
  downloadWalletPdf: async (learnerId) => {
    const res = await request(`/lms/v1/wallet/${learnerId}/export.pdf`, { raw: true });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "lityra-wallet.pdf";
    document.body.appendChild(a); a.click();
    a.remove(); URL.revokeObjectURL(url);
  },
  driveAnalytics: (id) => request(`/drive/v1/drives/${id}/analytics`),
  // Download a round's marks as .xlsx (cleared=true → only cleared students).
  downloadRoundXlsx: async (id, order, cleared = false) => {
    const res = await request(
      `/drive/v1/drives/${id}/rounds/${order}/export${cleared ? "?cleared=true" : ""}`,
      { raw: true },
    );
    if (!res.ok) throw new Error(res.status === 401 ? "Session expired — sign in again." : "Export failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `drive-${cleared ? "cleared" : "attendees"}-round${order}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
  driveRegistrations: (id) => request(`/drive/v1/drives/${id}/registrations`),
  setPpo: (id, body) => request(`/drive/v1/drives/${id}/ppo-config`, { method: "POST", body }),

  // ---- Interview (recruiter) ----
  resolveCandidates: (ids) => request(`/drive/v1/candidates/resolve?ids=${(ids || []).join(",")}`),
  scheduleInterview: (body) => request("/drive/v1/interviews/schedule", { method: "POST", body }),
  allocateInterview: (id, interviewer_id) => request(`/drive/v1/interviews/${id}/allocate`, { method: "POST", body: { interviewer_id } }),
  rateInterview: (id, body) => request(`/drive/v1/interviews/${id}/rate`, { method: "POST", body }),
  decideInterview: (id, body) => request(`/drive/v1/interviews/${id}/decision`, { method: "POST", body }),
  driveInterviews: (driveId) => request(`/drive/v1/interviews/drive/${driveId}`),

  // ---- Evidence ledger (Drive-OS, append-only) ----
  addEvidence: (body) => request("/drive/v1/evidence", { method: "POST", body }),
  driveEvidence: (driveId) => request(`/drive/v1/evidence/drive/${driveId}`),
  driveEvidenceConflicts: (driveId) => request(`/drive/v1/evidence/drive/${driveId}/conflicts`),
  candidateEvidence: (candidateId, driveId) => request(`/drive/v1/evidence/candidate/${candidateId}${driveId ? `?drive_id=${driveId}` : ""}`),
  resolveEvidenceConflict: (conflictId) => request(`/drive/v1/evidence/conflicts/${conflictId}/resolve`, { method: "POST" }),
  backfillEvidence: (driveId) => request(`/drive/v1/evidence/backfill/${driveId}`, { method: "POST" }),

  // ---- Competency models ----
  competencyCatalogue: () => request("/drive/v1/competency/catalogue"),
  setEvaluationModel: (body) => request("/drive/v1/competency/models", { method: "POST", body }),
  evaluationModel: (driveId) => request(`/drive/v1/competency/models/${driveId}`),

  // ---- Decision intelligence ----
  recordDecision: (body) => request("/drive/v1/decisions", { method: "POST", body }),
  driveDecisions: (driveId) => request(`/drive/v1/decisions/drive/${driveId}`),
  decisionQueue: (driveId) => request(`/drive/v1/decisions/drive/${driveId}/queue`),
  candidateDecisions: (candidateId, driveId) => request(`/drive/v1/decisions/candidate/${candidateId}${driveId ? `?drive_id=${driveId}` : ""}`),

  // ---- Action (attention) engine ----
  driveActions: (driveId) => request(`/drive/v1/actions/drive/${driveId}`),
  resolveAction: (actionId, status) => request(`/drive/v1/actions/${actionId}/resolve`, { method: "POST", body: { status: status || "resolved" } }),

  // ---- Recruit-AI insights + calibration ----
  driveInsights: (driveId) => request(`/drive/v1/insights/drive/${driveId}`),
  driveCalibration: (driveId) => request(`/drive/v1/calibration/drive/${driveId}`),
  crossCalibration: () => request("/drive/v1/calibration/interviewers"),

  // ---- Evaluation / Result (recruiter) ----
  computeRanks: (exam_id) => request("/drive/v1/evaluations/rank", { method: "POST", body: { exam_id } }),
  examRanks: (examId) => request(`/drive/v1/evaluations/exam/${examId}/ranks`),
  examDifficulty: (examId) => request(`/drive/v1/evaluations/exam/${examId}/difficulty`),
  compileResults: (body) => request("/drive/v1/results/compile", { method: "POST", body }),
  driveResults: (driveId) => request(`/drive/v1/results/${driveId}`),
  publishResults: (driveId) => request(`/drive/v1/results/${driveId}/publish`, { method: "POST" }),
  generateOffer: (body) => request("/drive/v1/offers/generate", { method: "POST", body }),
  offerStatus: (offerId, status) => request(`/drive/v1/offers/${offerId}/status`, { method: "POST", body: { status } }),

  // ---- Question Bank & Exam authoring (recruiter) ----
  createQuestion: (body) => request("/drive/v1/questions", { method: "POST", body }),
  listQuestions: (status) => request(`/drive/v1/questions${status ? `?status=${status}` : ""}`),
  activateQuestion: (id) => request(`/drive/v1/questions/${id}/activate`, { method: "POST" }),
  createBlueprint: (body) => request("/drive/v1/blueprints", { method: "POST", body }),
  generatePaper: (id) => request(`/drive/v1/blueprints/${id}/generate-paper`, { method: "POST" }),
  createExam: (body) => request("/drive/v1/exams", { method: "POST", body }),
  deleteExam: (id) => request(`/drive/v1/exams/${id}`, { method: "DELETE" }),
  upsertEvalKey: (body) => request("/drive/v1/evaluations/keys", { method: "POST", body }),
  generateQuestions: (body) => request("/drive/v1/questions/generate", { method: "POST", body }),

  // ---- Proctoring (browser hooks) ----
  proctorStart: (body) => request("/drive/v1/proctor/start", { method: "POST", body }),
  proctorEvent: (examSessionId, type, meta) => request(`/drive/v1/proctor/${examSessionId}/events`, { method: "POST", body: { type, meta } }),
  // Public registration creates a pending candidate and sends an email OTP.
  attendDrive: (body) => request("/drive/v1/attend", { method: "POST", auth: false, body }),
  attendResume: (student_id, email) =>
    request("/drive/v1/attend/resume", { method: "POST", auth: false, body: { student_id, email } }),
  attendComplete: () => request("/drive/v1/attend/complete", { method: "POST" }),
  apply: (drive_id, drive_role_id) =>
    request("/drive/v1/candidate/apply", { method: "POST", body: { drive_id, drive_role_id } }),
  myApplications: () => request("/drive/v1/candidate/applications"),
  candidateProfile: () => request("/drive/v1/candidate/profile"),
  listExams: (driveId) => request(`/drive/v1/exams${driveId ? `?drive_id=${driveId}` : ""}`),
  examMeta: (examId) => request(`/drive/v1/exams/${examId}`),
  examPaper: (examId) => request(`/drive/v1/exams/${examId}/paper`),
  examStart: (examId, candidateId) =>
    request(`/drive/v1/exams/${examId}/start`, { method: "POST", body: candidateId ? { candidate_id: candidateId } : {} }),
  examState: (sessionId) => request(`/drive/v1/exam-sessions/${sessionId}/state`),
  examSave: (sessionId, answers) =>
    request(`/drive/v1/exam-sessions/${sessionId}/save`, { method: "POST", body: { answers } }),
  examSubmit: (sessionId) =>
    request(`/drive/v1/exam-sessions/${sessionId}/submit`, { method: "POST" }),
  updateProfile: (body) => request("/drive/v1/candidate/profile", { method: "PUT", body }),
  runCode: (language, code, cases) =>
    request("/drive/v1/coding/run-adhoc", { method: "POST", body: { language, code, cases } }),
  codingLanguages: () => request("/drive/v1/coding/languages"),
  codingOpen: (problem_id) =>
    request("/drive/v1/coding/session", { method: "POST", body: { problem_id } }),
  codingRun: (sid, code) =>
    request(`/drive/v1/coding/${sid}/run`, { method: "POST", body: { code } }),
  codingSubmit: (sid, code) =>
    request(`/drive/v1/coding/${sid}/submit`, { method: "POST", body: { code } }),

  // ---- Analytics ----
  dashboard: (role) => request(`/analytics/v1/dashboard/${role}`),
  ranking: () => request("/analytics/v1/colleges/ranking"),
  collegeReadiness: (collegeId) => request(`/analytics/v1/college/${encodeURIComponent(collegeId)}/readiness`),

  // Hire organization administration. These are organization tenants, not LMS colleges.
  organizations: () => request("/org/v1/organizations"),
  organization: (id) => request(`/org/v1/organizations/${encodeURIComponent(id)}`),
  myOrganization: () => request("/org/v1/me"),
  createOrganization: (body) => request("/org/v1/organizations", { method: "POST", body }),
  updateOrganization: (id, body) => request(`/org/v1/organizations/${encodeURIComponent(id)}`, { method: "PUT", body }),
  deleteOrganization: (id) => request(`/org/v1/organizations/${encodeURIComponent(id)}`, { method: "DELETE" }),

  // ---- Notifications ----
  inbox: () => request("/notify/v1/inbox"),
  markRead: (id) => request(`/notify/v1/inbox/${id}/read`, { method: "POST" }),

  // ---- Institution (Super Admin / College Admin) ----
  colleges: () => request("/lms/v1/colleges"),
  createCollege: (body) => request("/lms/v1/colleges", { method: "POST", body }),
  collegeCohorts: (cid) => request(`/lms/v1/colleges/${cid}/cohorts`),
  collegeBranches: (cid) => request(`/lms/v1/colleges/${cid}/branches`),
  trainingCenters: () => request("/lms/v1/training-centers"),
  createTrainingCenter: (body) => request("/lms/v1/training-centers", { method: "POST", body }),
  trainingPrograms: (centerId) => request(`/lms/v1/training-centers/${centerId}/programs`),
  createTrainingProgram: (centerId, body) => request(`/lms/v1/training-centers/${centerId}/programs`, { method: "POST", body }),
  trainingBatches: (centerId) => request(`/lms/v1/training-centers/${centerId}/batches`),
  createTrainingBatch: (centerId, body) => request(`/lms/v1/training-centers/${centerId}/batches`, { method: "POST", body }),
  trainingParticipants: (batchId) => request(`/lms/v1/training-batches/${batchId}/participants`),
  addTrainingParticipant: (batchId, body) => request(`/lms/v1/training-batches/${batchId}/participants`, { method: "POST", body }),
  createCohort: (cid, body) => request(`/lms/v1/colleges/${cid}/cohorts`, { method: "POST", body }),

  // ---- Audit trail (Super Admin) ----
  auditLogs: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
    return request(`/audit/v1/logs${qs ? `?${qs}` : ""}`);
  },
  auditVerify: (partitionKey = "platform") =>
    request(`/audit/v1/logs/verify?partition_key=${encodeURIComponent(partitionKey)}`),

  // ---- User administration (Super Admin portal) ----
  adminUsers: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
    return request(`/auth/v1/admin/users${qs ? `?${qs}` : ""}`);
  },
  adminUser: (id) => request(`/auth/v1/admin/users/${id}`),
  createUser: (body) => request("/auth/v1/admin/users", { method: "POST", body }),
  setUserStatus: (id, status) => request(`/auth/v1/admin/users/${id}/status`, { method: "POST", body: { status } }),
  myInterviews: () => request("/drive/v1/interviews/mine"),
  interviewDossier: (id) => request(`/drive/v1/interviews/${id}/dossier`),
  rateInterview: (id, body) => request(`/drive/v1/interviews/${id}/rate`, { method: "POST", body }),
  decideInterview: (id, body) => request(`/drive/v1/interviews/${id}/decision`, { method: "POST", body }),

  // ---- Student home (dashboard + year-wise roadmap) ----
  studentHome: () => request("/lms/v1/students/me/home"),
  moduleResources: (mid) => request(`/lms/v1/students/modules/${mid}/resources`),

  // ---- Hierarchical analytics (Platform → College → Branch → Section → Student) ----
  rosterRollup: (level = "platform", parentId) =>
    request(`/lms/v1/roster/rollup?level=${level}${parentId ? `&parent_id=${parentId}` : ""}`),
  placementRollup: (level = "platform", parentId) =>
    request(`/lms/v1/placement/rollup?level=${level}${parentId ? `&parent_id=${parentId}` : ""}`),

  // ---- Learner roster (TPO / College Admin) ----
  learners: (params = "") => request(`/lms/v1/learners${params}`),
  createLearner: (body) => request("/lms/v1/learners", { method: "POST", body }),
  bulkImportLearners: (body) => request("/lms/v1/learners/import", { method: "POST", body }),
  verifyLearner: (lid) => request(`/lms/v1/learners/${lid}/verify`, { method: "POST" }),
  promoteLearner: (lid) => request(`/lms/v1/learners/${lid}/promote`, { method: "POST" }),

  // ---- Curriculum authoring (Trainer / Admin) ----
  createCurriculum: (body) => request("/lms/v1/curricula", { method: "POST", body }),
  addYear: (cid, body) => request(`/lms/v1/curricula/${cid}/years`, { method: "POST", body }),
  addModule: (yid, body) => request(`/lms/v1/years/${yid}/modules`, { method: "POST", body }),
  addLesson: (mid, body) => request(`/lms/v1/modules/${mid}/lessons`, { method: "POST", body }),
  addModuleToYear: (yid, body) => request(`/lms/v1/years/${yid}/modules`, { method: "POST", body }),
  authoringScopes: () => request("/lms/v1/authoring/scopes"),
  // content resources on a lesson/topic
  createContent: (body) => request("/lms/v1/content", { method: "POST", body }),
  listContent: (lessonId) => request(`/lms/v1/content?lesson_id=${lessonId}`),
  getLesson: (lid) => request(`/lms/v1/lessons/${lid}`),
  setLessonContent: (lid, content) => request(`/lms/v1/lessons/${lid}/content`, { method: "PUT", body: { content } }),
  gradeLessonCheck: (lid, block_id, choice) =>
    request(`/lms/v1/lessons/${lid}/check`, { method: "POST", body: { block_id, choice } }),
  // A lesson check counts as real practice → feeds the review schedule (twin).
  recordActivity: (learnerId, skill, good, mastery = 0) =>
    request(`/lms/v1/reviews/${learnerId}/activity`, { method: "POST", body: { skill, good, mastery, source: "written" } }),
  publishCurriculum: (cid) => request(`/lms/v1/curricula/${cid}/publish`, { method: "POST" }),

  // ---- Progress writes (Trainer) ----
  markAttendance: (body) => request("/lms/v1/attendance", { method: "POST", body }),
  computeYear: (body) => request("/lms/v1/progress/compute-year", { method: "POST", body }),
  gradeAnswer: (answerId, score) => request(`/lms/v1/answers/${answerId}/grade`, { method: "POST", body: { score } }),

  // ---- LMS assessments (student take-flow) ----
  listAssessments: () => request("/lms/v1/assessments"),
  createAssessment: (body) => request("/lms/v1/assessments", { method: "POST", body }),
  getAssessment: (aid) => request(`/lms/v1/assessments/${aid}`),
  startAttempt: (aid, learnerId) => request(`/lms/v1/assessments/${aid}/attempts`, { method: "POST", body: { learner_id: learnerId } }),
  submitAttempt: (attemptId, answers) => request(`/lms/v1/attempts/${attemptId}/submit`, { method: "POST", body: { answers } }),

  // ---- Certification ----
  issueCertificate: (body) => request("/lms/v1/certificates/issue", { method: "POST", body }),
  verifyCertificate: (verifyId) => request(`/verify/${verifyId}`, { auth: false }),

  // ---- AI Tutor ----
  tutorChat: (message, session_id, context) => request("/ai/v1/tutor/chat", { method: "POST", body: { message, session_id, context } }),
  tutorSessions: () => request("/ai/v1/tutor/sessions"),
  tutorMessages: (sid) => request(`/ai/v1/tutor/sessions/${sid}/messages`),
  studyPlan: (variables) => request("/ai/v1/tutor/study-plan", { method: "POST", body: { variables } }),
  streamAdvice: (variables) => request("/ai/v1/tutor/stream-advice", { method: "POST", body: { variables } }),

  // ---- File upload (pre-signed 3-step) ----
  requestUpload: (body) => request("/files/v1/upload-url", { method: "POST", body }),
  completeUpload: (fileId) => request(`/files/v1/${fileId}/complete`, { method: "POST" }),
  // raw PUT of bytes to the pre-signed token URL
  uploadBytes: (token, bytes, mime) =>
    fetch(apiUrl(`/files/v1/upload/${token}`), { method: "PUT", headers: apiHeaders({ "Content-Type": mime }), body: bytes }),
  setResume: (resume_file_id) => request("/drive/v1/candidate/resume", { method: "POST", body: { resume_file_id } }),
};

// Keep the SHAPE of a fallback but blank every value, so a failed call yields an
// honest empty state instead of fabricated data.
function blankShape(v) {
  if (Array.isArray(v)) return [];
  if (v && typeof v === "object") {
    const out = {};
    for (const k of Object.keys(v)) out[k] = blankShape(v[k]);
    return out;
  }
  if (typeof v === "number") return 0;
  if (typeof v === "boolean") return false;
  if (typeof v === "string") return "";
  return v; // null / undefined
}

// Wrap a live call so a page still renders when a call fails. In DEVELOPMENT we
// return the demo data so screens render with the backend down. In PRODUCTION we
// must NEVER surface fabricated/demo data — it can show one user the shape of
// another's record (e.g. a demo profile for everyone). There we blank the
// fallback to an empty state of the same shape.
const IS_PROD = !!(import.meta && import.meta.env && import.meta.env.PROD);
export async function withFallback(promise, fallback) {
  try {
    const data = await promise;
    return { data, live: true };
  } catch {
    return { data: IS_PROD ? blankShape(fallback) : fallback, live: false };
  }
}
