import { createContext, lazy, Suspense, useContext } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  BookOpen,
  Layers3,
  Sparkles,
  Trophy,
  Code2,
  ShieldCheck,
  Briefcase,
  GraduationCap,
  Building2,
  Award,
  TrendingUp,
  Users,
} from "lucide-react";
import { Logo } from "../components/ui/Logo.jsx";
import { Button } from "../components/ui/primitives.jsx";
const CareerConstellation = lazy(() =>
  import("../components/ui/CareerConstellation.jsx").then((module) => ({ default: module.CareerConstellation })),
);
const ProductContext = createContext(false);

function SmartLink({ to, children, ...props }) {
  const isHireApp = useContext(ProductContext);
  if (to === "/about") return <Link to="/about" {...props}>{children}</Link>;
  const isHireRoute = to.startsWith("/hire/") || to.startsWith("/drive/");
  const isLearnRoute = to.startsWith("/learn/") || to.startsWith("/trainer/");
  const crossProduct = (isHireApp && isLearnRoute) || (!isHireApp && isHireRoute);
  if (crossProduct) {
    const base = isHireApp ? import.meta.env.VITE_LITYRA_LEARN_URL : import.meta.env.VITE_LITYRA_HIRE_URL;
    if (base) return <a href={`${base.replace(/\/$/, "")}${to}`} {...props}>{children}</a>;
    return <a href="https://genzifytech.netlify.app/" {...props}>{children}</a>;
  }
  return <Link to={to} {...props}>{children}</Link>;
}

export default function Landing({ isHire = false }) {
  const reduceMotion = useReducedMotion();
  const staticScene = reduceMotion || window.matchMedia("(max-width: 700px)").matches || (navigator.deviceMemory && navigator.deviceMemory <= 2) || navigator.connection?.saveData;

  return (
    <ProductContext.Provider value={isHire}><div className="landing-page min-h-screen bg-surface">
      <header className="landing-nav">
        <div className="landing-nav-inner">
          <SmartLink to="/" className="landing-brand" aria-label="Lityra home">
            <Logo size={48} />
            <span><strong>Lityra</strong><small>Write Your Future</small></span>
          </SmartLink>
          <nav aria-label="Primary navigation">
            <SmartLink to="/about">About</SmartLink>
            <SmartLink to="/learn/login">Learn login</SmartLink>
            <SmartLink to="/trainer/login">Trainer login</SmartLink>
            <SmartLink to="/hire/login">Hire login</SmartLink>
            <Button as={SmartLink} to="/learn/register" size="sm">Get started <ArrowRight size={15} /></Button>
          </nav>
        </div>
      </header>

      <section className={`landing-hero ${staticScene ? "is-static" : ""}`} aria-labelledby="landing-title">
        <div className="landing-hero-grain" aria-hidden="true" />
        <div className="landing-scene-route" aria-hidden="true" />
        <Suspense fallback={null}>
          <CareerConstellation mode="journey" className="landing-journey-scene" />
        </Suspense>
        <div className="landing-hero-layout">
          <div className="landing-hero-copy">
            <p className="landing-overline"><span /> LEARN · PRACTICE · CONNECT</p>
            <h1 id="landing-title">A future<br />written <em>by you.</em></h1>
            <p className="landing-hero-description">Build skills through lessons and practice. Show what you can do through assessments and credentials. Find opportunities through hiring drives.</p>
            <div className="landing-hero-actions">
              <Button as={SmartLink} to="/learn/register" size="lg">Start learning <ArrowRight size={17} /></Button>
              <SmartLink className="landing-secondary-link" to="/hire/login">Open Lityra Hire <ArrowRight size={16} /></SmartLink>
            </div>
            <p className="landing-hero-note">Learning and hiring in one connected platform.</p>
          </div>

          <ol className="landing-scene-stations" aria-label="Lityra learning and hiring journey">
            <li className="station-learning"><span className="station-number">01</span><BookOpen aria-hidden="true" /><span><strong>Learn</strong><small>Courses & lessons</small></span></li>
            <li className="station-practice"><span className="station-number">02</span><Code2 aria-hidden="true" /><span><strong>Practice</strong><small>Challenges & drills</small></span></li>
            <li className="station-evidence"><span className="station-number">03</span><ShieldCheck aria-hidden="true" /><span><strong>Demonstrate</strong><small>Assessments & credentials</small></span></li>
            <li className="station-opportunity"><span className="station-number">04</span><Briefcase aria-hidden="true" /><span><strong>Connect</strong><small>Drives & opportunities</small></span></li>
          </ol>
          <div className="landing-hero-index" aria-hidden="true"><span>01</span><i></i><span>04</span></div>
        </div>
        <a href="#journey" className="landing-scroll-cue"><span>Scroll to explore</span><i aria-hidden="true" /></a>
      </section>
      {/* The product loop: capabilities, not unverified customer claims. */}
      <section id="journey" className="landing-loop-section relative overflow-hidden bg-invert-950">
        <div className="absolute inset-0 opacity-[0.12] bg-grid" />
        <div className="relative mx-auto max-w-6xl px-5 py-16 lg:py-20">
          <div className="grid lg:grid-cols-[.8fr_1.2fr] gap-10 lg:gap-16 items-center">
            <div>
              <p className="text-sm font-semibold text-amber-300">A connected career studio</p>
              <h2 className="mt-3 text-3xl sm:text-4xl font-display font-bold text-white leading-tight">Make learning visible. Let opportunity follow.</h2>
              <p className="mt-4 max-w-lg text-slate-300 leading-7">Lityra brings practice, assessment, learner evidence and hiring workflows into one journey, with separate workspaces for learning and recruitment.</p>
            </div>
            <div className="landing-loop" aria-label="From learning to hiring">
              {[[BookOpen, "Build", "Follow a curriculum and learn in lessons."], [Code2, "Practice", "Work through coding challenges and drills."], [ShieldCheck, "Show evidence", "Use assessments and credentials to demonstrate progress."], [Briefcase, "Find opportunity", "Connect with drives and matching opportunities."]].map(([Icon, title, detail], index) => <motion.article key={title} className="landing-loop-step" initial={reduceMotion ? false : { opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .25 }} transition={{ duration: reduceMotion ? 0 : .36, delay: reduceMotion ? 0 : index * .07 }}><span className="landing-loop-index">0{index + 1}</span><span className="landing-loop-icon"><Icon size={19} /></span><div><h3>{title}</h3><p>{detail}</p></div></motion.article>)}
            </div>
          </div>
        </div>
      </section>

      {/* Two products, one journey */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <div className="text-center mb-10">
          <p className="text-sm font-semibold text-brand-500">One platform · two products</p>
          <h2 className="mt-1 text-2xl sm:text-3xl lg:text-4xl font-display font-bold text-ink-900">From learning to opportunity</h2>
          <p className="mt-3 text-slate-500 max-w-2xl mx-auto">Explore learning tools and hiring workflows designed to connect skills with opportunities.</p>
        </div>
        <div className="grid md:grid-cols-2 gap-5 relative">
          <div className="hidden md:grid absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 h-11 w-11 rounded-full bg-surface border border-slate-200 shadow-card place-items-center text-slate-400"><ArrowRight size={20} /></div>

          <motion.div initial={false} whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }} viewport={{ once: true }} transition={reduceMotion ? { duration: 0 } : { duration: 0.5 }}
            className="rounded-2xl border border-slate-200 bg-gradient-to-br from-brand-500/[0.06] via-surface to-surface p-7">
            <div className="flex items-center gap-3">
              <span className="grid place-items-center h-12 w-12 rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 text-white shadow-sm"><GraduationCap size={24} /></span>
              <div><p className="font-display text-xl font-bold text-ink-900">Lityra Learn</p><p className="text-[12.5px] text-slate-500">Write Your Future</p></div>
            </div>
            <ul className="mt-5 space-y-2.5">
              {[[Code2, "Curriculum, coding challenges & adaptive drills"], [Sparkles, "AI tutor, skill map & micro-lessons"], [Trophy, "XP, badges & learning achievements"], [ShieldCheck, "Assessments, certificates & skill wallet"]].map(([Ic, t]) => (
                <li key={t} className="flex items-start gap-2.5 text-[13.5px] text-slate-600"><Ic size={16} className="text-brand-500 mt-0.5 shrink-0" />{t}</li>
              ))}
            </ul>
            <div className="mt-6 flex gap-2">
            <Button as={SmartLink} to="/learn/register" className="flex-1 justify-center">Start learning <ArrowRight size={16} /></Button>
              <Button as={SmartLink} to="/learn/login" variant="secondary" className="justify-center">Sign in</Button>
            </div>
            <SmartLink to="/trainer/login" className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700 hover:underline">
              Trainer sign in <ArrowRight size={14} />
            </SmartLink>
          </motion.div>

          <motion.div initial={false} whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }} viewport={{ once: true }} transition={reduceMotion ? { duration: 0 } : { duration: 0.5, delay: 0.08 }}
            className="rounded-2xl border border-slate-200 bg-gradient-to-br from-amber-500/[0.07] via-surface to-surface p-7">
            <div className="flex items-center gap-3">
              <span className="grid place-items-center h-12 w-12 rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 text-white shadow-sm"><Briefcase size={24} /></span>
              <div><p className="font-display text-xl font-bold text-ink-900">Lityra Hire</p><p className="text-[12.5px] text-slate-500">Write Your Future</p></div>
            </div>
            <ul className="mt-5 space-y-2.5">
              {[[Building2, "Manage campus drives and candidate access"], [Award, "Organize multi-round hiring pipelines"], [TrendingUp, "Review candidate and assessment results"], [Users, "Coordinate interviews and decisions"]].map(([Ic, t]) => (
                <li key={t} className="flex items-start gap-2.5 text-[13.5px] text-slate-600"><Ic size={16} className="text-amber-600 mt-0.5 shrink-0" />{t}</li>
              ))}
            </ul>
            <div className="mt-6 flex gap-2">
              <Button as={SmartLink} to="/hire/login" variant="amber" className="flex-1 justify-center">Hire login <ArrowRight size={16} /></Button>
              <Button as={SmartLink} to="/drive/attend" variant="secondary" className="justify-center">Attend a drive</Button>
            </div>
          </motion.div>
        </div>
      </section>

      <section className="landing-audience-section mx-auto max-w-6xl px-5 py-16">
        <div className="landing-audience-heading"><span className="landing-audience-stamp"><Layers3 size={17} /> Two purpose-built workspaces</span><h2>One path. The right tools for each step.</h2><p>Learning and hiring share a career journey while keeping their day-to-day work focused.</p></div>
        <div className="landing-audience-grid">
          <article className="landing-audience-card landing-audience-learn"><span className="landing-audience-index">01 / LEARN</span><h3>Build capability through practice.</h3><p>Follow learning, practice coding, explore skills, complete assessments and keep credentials in one place.</p><SmartLink to="/learn/login">Explore Learn <ArrowRight size={16} /></SmartLink></article>
          <article className="landing-audience-card landing-audience-hire"><span className="landing-audience-index">02 / HIRE</span><h3>Move from applicants to decisions.</h3><p>Organize hiring drives, assessments, rounds, access codes and candidate review through a recruiter workspace.</p><SmartLink to="/hire/login">Explore Hire <ArrowRight size={16} /></SmartLink></article>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="relative overflow-hidden bg-invert-950">
        <div className="absolute -bottom-24 left-1/2 -translate-x-1/2 h-64 w-[42rem] rounded-full bg-amber-500/20 blur-3xl" />
        <div className="absolute inset-0 opacity-[0.10] bg-grid" />
        <div className="relative mx-auto max-w-4xl px-5 py-20 text-center">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-display font-bold text-white leading-[1.1]">
            Learn, practice and<br /><span className="text-amber-400">explore opportunity.</span>
          </h2>
          <p className="mt-4 text-slate-300 max-w-xl mx-auto">Learning, assessment and hiring workflows in one connected platform.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button as={SmartLink} to="/learn/register" size="lg" variant="amber">Start with Learn <ArrowRight size={18} /></Button>
            <SmartLink to="/hire/login" className="inline-flex items-center gap-2 h-12 px-6 rounded-lg border border-white/25 text-white font-semibold hover:bg-white/10 transition-colors">Enter Lityra Hire</SmartLink>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-100 bg-slate-50/50">
        <div className="mx-auto max-w-6xl px-5 py-8 flex flex-col sm:flex-row items-center justify-between gap-5 text-sm text-slate-400">
          <div className="flex items-center gap-3">
            <Logo size={72} />
            <div className="leading-tight">
              <p className="font-display font-semibold text-ink-900">Lityra</p>
              <p className="text-xs text-slate-500">Write Your Future</p>
              <p className="text-xs text-slate-400">© {new Date().getFullYear()} · All rights reserved.</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-center sm:text-right">
            <img
              src="/brand/genzify-tech-light.png"
              alt="GenZify"
              className="h-16 w-16 object-contain rounded-lg"
            />
            <p className="text-sm leading-tight text-slate-300">
              Parent company
              <span className="block font-semibold text-ink-900">GenZify</span>
              <span className="block max-w-xs text-xs">Engineering Human Potential Through Technology</span>
              <a href="https://genzifytech.netlify.app/" target="_blank" rel="noreferrer" className="landing-company-link">Visit company website <ArrowRight size={13} /></a>
            </p>
          </div>
        </div>
      </footer>
    </div></ProductContext.Provider>
  );
}
