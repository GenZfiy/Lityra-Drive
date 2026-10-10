import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, BookOpen, Eye, Heart, Lightbulb, Sparkles, Target, Users, Zap } from "lucide-react";
import { Logo } from "../components/ui/Logo.jsx";

const companyValues = [
  { icon: Zap, title: "Innovation first", body: "We build with new technology to solve meaningful problems and create lasting value." },
  { icon: Heart, title: "Human centred", body: "Learning, assessment and hiring should help people grow. People stay at the centre of our product decisions." },
  { icon: Users, title: "Global by design", body: "We aim to build useful technology for different languages, cultures and communities." },
  { icon: Target, title: "Outcomes over outputs", body: "We focus on skills people can demonstrate and decisions teams can make with confidence." },
  { icon: Eye, title: "Radical transparency", body: "We value clear, honest communication with the people and organizations we work with." },
  { icon: Lightbulb, title: "Long-term thinking", body: "We build toward durable human progress, not only short-term activity." },
];

const productAnswers = [
  { label: "Why", title: "Learning and hiring need a stronger connection", body: "People build skills over time, while hiring teams need clear evidence of what candidates can do. Lityra brings learning, practice, assessment, credentials and hiring workflows into one connected journey." },
  { label: "What", title: "A connected Learn and Hire platform", body: "Lityra Learn supports structured learning, coding practice, adaptive drills, assessments and skill credentials. Lityra Hire supports drive access, assessment rounds, interviews and candidate decisions." },
  { label: "When", title: "From first lessons to the next opportunity", body: "Use Lityra throughout the journey: while building foundations, practicing skills, demonstrating capability, preparing for careers and coordinating recruitment." },
  { label: "For whom", title: "Learners, educators and hiring teams", body: "Learners use it to build and show skills. Educators and institutions organize curriculum and follow progress. Recruiters coordinate drives and review candidate evidence." },
];

const leadership = [
  { initials: "SS", photo: "/team/sameer.webp", name: "Sameer Shaik", role: "Founder & CEO, CFO", background: "Founding Team", expertise: ["Product Strategy", "AI Platforms", "Finance"] },
  { initials: "SG", photo: "https://avatars.githubusercontent.com/u/174678147?v=4", name: "Sashipreetham G", role: "Co-founder & CTO, CIO", background: "Founding Team", expertise: ["Engineering", "AI Systems", "Cloud Architecture"] },
  { initials: "BK", photo: "https://avatars.githubusercontent.com/u/168163179?v=4", name: "Babu Kothacharuvu Shaik", role: "CSO, COO & CRO", background: "Founding Team", expertise: ["Sales Strategy", "Operations", "Revenue Growth"] },
];

const advisors = [
  { initials: "BK", photo: "/team/bharathi.webp", name: "Bharathi K", role: "Advisory Committee", background: "SDE 1, Pragma Edge Software Services", location: "Jubilee Hills, Hyderabad", expertise: ["Software Engineering", "Full Stack Development"] },
  { initials: "LP", photo: "/team/priya.webp", name: "Lakshmi Priya K", role: "Advisory Committee", background: "Research Scholar", location: "Cyber Security", expertise: ["Cyber Security", "Research"] },
  { initials: "HT", photo: "/team/haseen.webp", name: "Haseen Taj S", role: "Advisory Committee", background: "Research Scholar", location: "Artificial Intelligence & Machine Learning", expertise: ["AI / ML", "Research"] },
];

function PeopleGrid({ people }) {
  return <div className="about-people-grid">{people.map((person, index) => <motion.article key={person.name} className="about-person-card" initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .15 }} transition={{ duration: .4, delay: index * .06 }}>
    <div className="about-person-photo"><span className="about-person-monogram" aria-hidden="true">{person.initials}</span><img src={person.photo} alt={`${person.name} portrait`} loading="lazy" onError={(event) => { event.currentTarget.hidden = true; }} /></div>
    <h3>{person.name}</h3><span className="about-person-role">{person.role}</span>
    <p>{person.background}</p><p>{person.location}</p>
    <div className="about-person-expertise">{person.expertise.map((item) => <span key={item}>{item}</span>)}</div>
  </motion.article>)}</div>;
}

export default function About({ isHire = false }) {
  return (
    <main className="about-page min-h-screen">
      <header className="about-nav">
        <Link to="/" className="about-brand" aria-label="Lityra home"><Logo size={44} /><span><strong>Lityra</strong><small>Write Your Future</small></span></Link>
        <nav aria-label="About navigation">
          <Link to="/">Home</Link>
          <a href="https://genzifytech.netlify.app/" target="_blank" rel="noreferrer">GenZify website <ArrowRight size={15} /></a>
          <Link className="about-nav-cta" to={isHire ? "/hire/register" : "/learn/register"}>Get started</Link>
        </nav>
      </header>

      <section className="about-hero">
        <div className="about-hero-orbit" aria-hidden="true"><span /><i /><b /></div>
        <motion.div className="about-hero-copy" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .55 }}>
          <span className="about-eyebrow"><Sparkles size={15} /> ABOUT LITYRA &amp; GENZIFY</span>
          <h1>Technology should help people <em>move forward.</em></h1>
          <p>Lityra connects learning, demonstrable skills and hiring. It is a product by GenZify, built around a simple idea: engineering should expand human potential.</p>
          <div className="about-hero-actions"><Link to="/" className="about-back"><ArrowLeft size={16} /> Back to Lityra</Link><a className="about-company-link" href="https://genzifytech.netlify.app/" target="_blank" rel="noreferrer">Visit GenZify <ArrowRight size={16} /></a></div>
        </motion.div>
      </section>

      <section className="about-product-section">
        <div className="about-section-heading"><span className="about-eyebrow">THE PRODUCT</span><h2>A more connected path from learning to work.</h2><p>Four questions explain what Lityra is for and how it fits into that journey.</p></div>
        <div className="about-answer-grid">{productAnswers.map((item, i) => <motion.article key={item.label} className="about-answer-card" initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .2 }} transition={{ duration: .4, delay: i * .06 }}><span className="about-answer-label">{item.label}</span><h3>{item.title}</h3><p>{item.body}</p></motion.article>)}</div>
        <div className="about-workspaces"><article><BookOpen size={21} /><div><h3>Lityra Learn</h3><p>Courses, lessons, practice, assessments and a record of demonstrated skills.</p></div></article><article><Users size={21} /><div><h3>Lityra Hire</h3><p>Drive registration, candidate assessment, interview coordination and hiring decisions.</p></div></article></div>
      </section>

      <section className="about-company-section">
        <div className="about-company-intro"><span className="about-eyebrow">THE COMPANY BEHIND THE PRODUCT</span><h2>GenZify</h2><p className="about-company-tagline">Engineering Human Potential Through Technology</p><p>GenZify builds technology products to solve meaningful problems. Lityra is part of that mission: a focused platform for learning, skill evidence and career opportunity.</p><div className="about-origin-note"><span>OUR BEGINNING</span><p>GenZify began with a goal to build purposeful, AI-powered software for real problems. Lityra carries that mission into the journey from education to employment. The product is being developed as a connected platform for learners, educators and hiring teams.</p></div><a href="https://genzifytech.netlify.app/" target="_blank" rel="noreferrer">Explore the GenZify website <ArrowRight size={16} /></a></div>
        <div className="about-mission-vision"><article><Target size={20} /><span>OUR MISSION</span><h3>Build technology that solves real problems</h3><p>We combine thoughtful engineering with applied AI to create products that are useful to the people and organizations who use them.</p></article><article><Eye size={20} /><span>OUR VISION</span><h3>Make useful technology work for more people</h3><p>We want capable, well-built tools to be within reach of the people who can benefit from them, and we build toward that future one product at a time.</p></article></div>
      </section>

      <section className="about-people-section">
        <div className="about-section-heading"><span className="about-eyebrow">THE PEOPLE</span><h2>Builders and advisors behind GenZify.</h2><p>A team bringing together product strategy, engineering, operations and research.</p></div>
        <h3 className="about-people-heading">Leadership</h3><PeopleGrid people={leadership} />
        <h3 className="about-people-heading about-advisors-heading">Advisory committee</h3><PeopleGrid people={advisors} />
      </section>

      <section className="about-values-section"><div className="about-section-heading"><span className="about-eyebrow">HOW WE BUILD</span><h2>Principles behind the product.</h2></div><div className="about-values-grid">{companyValues.map(({ icon: Icon, title, body }) => <article key={title}><Icon size={19} /><h3>{title}</h3><p>{body}</p></article>)}</div></section>

      <section className="about-founder-note" aria-labelledby="founder-note-title">
        <div className="about-founder-note-inner">
          <span className="about-founder-kicker"><Heart size={14} fill="currentColor" /> A NOTE FROM THE FOUNDER</span>
          <h2 id="founder-note-title">She has been my home, my peace,<br className="hidden sm:block" /> my paradise, and my heaven.</h2>
          <p className="about-founder-lead">Behind every builder is someone who believed first — long before the world did.</p>
          <p>This platform, and everything that led to it, would not exist without the unwavering care, love, and constant support of my sister, <strong>Likhitha Rani P.</strong> Through every challenge, every sleepless night, and every moment of doubt, she stood beside me — not just as family, but as my anchor, my strength, and my greatest source of inspiration.</p>
          <p>Her presence alone has always been enough to keep going.</p>
          <svg className="about-founder-flourish" viewBox="0 0 220 28" role="img" aria-label="Decorative signature flourish"><path d="M4 19c28-1 32-12 47-12 15 0 14 17 29 17 12 0 12-18 27-18 9 0 10 9 19 9 10 0 14-10 22-10 8 0 9 10 19 10 9 0 16-7 28-7 7 0 13 3 21 3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><circle cx="110" cy="6" r="2" fill="currentColor" /></svg>
          <span className="about-founder-signoff">With deepest gratitude,</span>
          <p className="about-founder-signature">Shaik Sameer</p>
          <p className="about-founder-nickname">— your lil one 👻</p>
          <p className="about-founder-role">Founder &amp; CEO · CFO, GenZify</p>
        </div>
      </section>

      <footer className="about-footer"><Link to="/" className="about-brand"><Logo size={38} /><span><strong>Lityra</strong><small>Write Your Future</small></span></Link><span>A GenZify product</span><a href="https://genzifytech.netlify.app/" target="_blank" rel="noreferrer">GenZify · Engineering Human Potential Through Technology <ArrowRight size={14} /></a></footer>
    </main>
  );
}
