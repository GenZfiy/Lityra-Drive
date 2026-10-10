// Fallback demo data so every screen renders even when the backend isn't
// running. Live calls are wired in each page; this is the graceful fallback.

export const demoScorecard = [
  { year_no: 2, communication: 72, coding: 87, aptitude: 78, project: 66 },
];

export const demoGame = {
  learner_id: "demo",
  total_xp: 4720,
  level: 4,
  next_level_at: 5000,
  xp_to_next: 280,
  badges: ["streak_7", "dsa_i", "aptitude_ace"],
  streak: { current: 12, longest: 21 },
};

// Real zero-state for a learner with no activity yet. Used as the fallback for
// per-user gamification/scorecard so a NEW user (or a failed call) shows honest
// zeros — never another user's or the demo's numbers.
export const emptyGame = {
  learner_id: "", total_xp: 0, level: 1, next_level_at: 1000, xp_to_next: 1000,
  badges: [], streak: { current: 0, longest: 0 },
};
export const emptyScorecard = [];

export const demoLeaderboard = [
  { rank: 1, display_name: "Ravi K.", total_xp: 6120, level: 5 },
  { rank: 2, display_name: "Sita M.", total_xp: 5340, level: 5 },
  { rank: 3, display_name: "Arjun P.", total_xp: 4980, level: 4 },
  { rank: 4, display_name: "Asha Rao", total_xp: 4720, level: 4 },
  { rank: 5, display_name: "Neha S.", total_xp: 4310, level: 4 },
];

export const demoCurriculum = {
  name: "Lityra 4-Year Programme",
  status: "published",
  years: [
    {
      year_no: 2,
      theme: "Technical Foundation & Stream Discovery",
      modules: [
        {
          id: "m1",
          title: "Data Structures & Algorithms",
          branch_scope: "cse_allied",
          lessons: [
            { id: "l1", title: "Recursion", objectives: [{ statement: "Trace & write recursion", skill_tag: "coding" }] },
            { id: "l2", title: "Arrays & Strings", objectives: [] },
          ],
        },
        {
          id: "m2",
          title: "Databases & SQL",
          branch_scope: "all",
          lessons: [{ id: "l3", title: "Joins & Normalisation", objectives: [] }],
        },
      ],
      outcome_checks: [{ statement: "Solid DSA + one language + counselled stream choice" }],
    },
  ],
};

export const demoPlaylist = [
  { id: "c1", title: "Recursion — Intro", type: "video", duration_sec: 600, difficulty: "easy", unlocked: true, status: "completed" },
  { id: "c2", title: "Recursion — Challenge", type: "interactive", duration_sec: 1200, difficulty: "hard", unlocked: true, status: "in_progress" },
  { id: "c3", title: "SQL — Joins", type: "reading", duration_sec: 900, difficulty: "medium", unlocked: false, status: "not_started" },
];

export const demoCertificates = [
  { year_no: 1, certificate: "Foundation & Personality Development", status: "issued", cert_no: "LITYRA-Y1-000042", ppo_tag: false, verify_id: "demo1" },
];

export const demoDrives = [
  { id: "d1", company_name: "GenZify", title: "SWE Intern Drive 2027", status: "open", venue: "Aditya College", reporting_time: "9:00 AM" },
  { id: "d2", company_name: "TCS", title: "NQT Recruitment", status: "open", venue: "Online", reporting_time: "10:00 AM" },
];

export const demoRanking = [
  { rank: 1, college_id: "Aditya College", readiness_index: 81.6 },
  { rank: 2, college_id: "Sample College B", readiness_index: 58.0 },
];

export const demoProblem = {
  id: "p1",
  title: "Sum Two Integers",
  statement:
    "Read two space-separated integers from standard input and print their sum.\n\nExample:\nInput: 2 3\nOutput: 5",
  languages: ["python", "java", "cpp", "javascript"],
  time_limit_sec: 3,
  sample_cases: [
    { input: "2 3", expected: "5" },
    { input: "10 20", expected: "30" },
  ],
};

export const demoStarter = {
  python: "a, b = map(int, input().split())\nprint(a + b)\n",
  javascript:
    "const [a, b] = require('fs').readFileSync(0,'utf8').trim().split(' ').map(Number);\nconsole.log(a + b);\n",
  java: "// write your solution\n",
  cpp: "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}\n",
};

export const demoInbox = [
  { id: "n1", template_key: "badge_earned", subject: "New badge earned!", body: "You earned the 7-Day Streak badge. Keep it up, Asha!", read: false, created_at: new Date().toISOString() },
  { id: "n2", template_key: "exam_reminder", subject: "Exam tomorrow", body: "Your TCS NQT mock starts at 9:00 AM. Be ready 10 minutes early.", read: false, created_at: new Date(Date.now() - 3600e3).toISOString() },
  { id: "n3", template_key: "certificate_issued", subject: "Certificate issued", body: "Your Foundation & Personality Development certificate is ready to view.", read: true, created_at: new Date(Date.now() - 86400e3).toISOString() },
];

export const demoProfile = {
  full_name: "Asha Rao",
  email: "asha@aditya.edu",
  phone: "9652879470",
  branch: "CSE",
  cgpa: 8.4,
  completeness: 100,
  education: [{ degree: "B.Tech CSE", institution: "Aditya College", year: 2027, score: "8.4" }],
  skills: [{ skill: "Python" }, { skill: "DSA" }, { skill: "SQL" }],
  projects: [{ title: "Inventory Management System", repo_url: "https://github.com/asha/inventory" }],
};

export const demoRecruiterDrives = [
  { id: "d1", company_name: "GenZify", title: "SWE Intern Drive 2027", status: "open", venue: "Aditya College", reporting_time: "9:00 AM" },
  { id: "d2", company_name: "TCS", title: "NQT Recruitment", status: "draft", venue: "Online", reporting_time: "10:00 AM" },
];

export const demoDriveDetail = {
  id: "d1",
  company_name: "GenZify",
  title: "SWE Intern Drive 2027",
  status: "open",
  venue: "Aditya College",
  reporting_time: "9:00 AM",
  roles: [{ id: "r1", title: "Software Engineer", ctc: "6 LPA", positions: 10 }],
  rounds: [
    { id: "rd1", order: 1, type: "aptitude" },
    { id: "rd2", order: 2, type: "coding" },
    { id: "rd3", order: 3, type: "interview" },
  ],
};

export const demoRegistrations = [
  { candidate_id: "20CSE001 · Asha Rao", status: "shortlisted", eligible: "yes", current_round: 2 },
  { candidate_id: "20CSE014 · Ravi Kumar", status: "in_round", eligible: "yes", current_round: 1 },
  { candidate_id: "20CSE022 · Sita M.", status: "applied", eligible: "yes", current_round: 0 },
  { candidate_id: "20MEC009 · Arjun P.", status: "applied", eligible: "no", current_round: 0 },
];

export const demoFunnel = {
  drive_id: "d1",
  total: 4,
  by_status: { applied: 2, shortlisted: 1, in_round: 1 },
};

export const demoResults = [
  { candidate_id: "20CSE001 · Asha Rao", final_score: 92, rank: 1, outcome: "selected", status: "published" },
  { candidate_id: "20CSE014 · Ravi Kumar", final_score: 74, rank: 2, outcome: "shortlist", status: "published" },
  { candidate_id: "20CSE022 · Sita M.", final_score: 55, rank: 3, outcome: "fail", status: "published" },
];

export const demoInterviews = [
  { id: "iv1", candidate_id: "20CSE001 · Asha Rao", stage: "technical", mode: "online", status: "completed", decision: "select", avg_rating: 4.3, interviewer_id: "panel-1" },
  { id: "iv2", candidate_id: "20CSE014 · Ravi Kumar", stage: "technical", mode: "online", status: "scheduled", decision: null, avg_rating: null, interviewer_id: null },
];

export const demoQuestions = [
  { id: "q1", type: "mcq", category: "aptitude", difficulty: "easy", stem: "What is 2 + 2?", status: "active", version: 1 },
  { id: "q2", type: "mcq", category: "aptitude", difficulty: "medium", stem: "12 × 8 = ?", status: "active", version: 1 },
  { id: "q3", type: "coding", category: "programming", difficulty: "hard", stem: "Reverse a linked list", status: "draft", version: 1 },
];

export const demoColleges = [
  { id: "c1", name: "Aditya College of Engineering", code: "ACE", city: "Surampalem", learners: 1240, verified: true },
  { id: "c2", name: "Sample College B", code: "SCB", city: "Kakinada", learners: 640, verified: false },
];

export const demoLearners = [
  { id: "l1", roll_no: "20CSE001", full_name: "Asha Rao", branch_id: "CSE", year_no: 2, cgpa: 8.4, verified: true, status: "active" },
  { id: "l2", roll_no: "20CSE014", full_name: "Ravi Kumar", branch_id: "CSE", year_no: 2, cgpa: 7.9, verified: true, status: "active" },
  { id: "l3", roll_no: "20MEC009", full_name: "Arjun P.", branch_id: "MECH", year_no: 2, cgpa: 7.1, verified: false, status: "pending" },
  { id: "l4", roll_no: "20ECE022", full_name: "Sita M.", branch_id: "ECE", year_no: 3, cgpa: 8.8, verified: true, status: "active" },
];

export const demoAdminDash = {
  role: "college_admin", colleges: 2, learners: 1880, drives: 6,
  top_colleges: [
    { rank: 1, college_id: "Aditya College", readiness_index: 81.6 },
    { rank: 2, college_id: "Sample College B", readiness_index: 58.0 },
  ],
};

export const demoAssessment = {
  id: "a1", title: "DSA — Weekly Quiz 3", pass_pct: 60, duration_min: 20,
  items: [
    { id: "i1", type: "mcq", stem: "Time complexity of binary search?", weight: 1,
      options: [{ id: "a", text: "O(n)" }, { id: "b", text: "O(log n)" }, { id: "c", text: "O(n log n)" }, { id: "d", text: "O(1)" }] },
    { id: "i2", type: "mcq", stem: "Which structure is LIFO?", weight: 1,
      options: [{ id: "a", text: "Queue" }, { id: "b", text: "Stack" }, { id: "c", text: "Heap" }, { id: "d", text: "Tree" }] },
    { id: "i3", type: "mcq", stem: "A balanced BST search is?", weight: 1,
      options: [{ id: "a", text: "O(n)" }, { id: "b", text: "O(log n)" }, { id: "c", text: "O(1)" }, { id: "d", text: "O(n^2)" }] },
  ],
};

export const demoTutorGreeting =
  "Hi! I'm your Lityra Tutor. Ask me anything about DSA, aptitude, interviews, or your study plan.";

export const DEMO_LEARNER_ID = "learner-1";
