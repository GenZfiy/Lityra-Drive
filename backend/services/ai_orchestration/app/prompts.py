"""Governed prompt library — the ONLY prompts this platform will run.

Every AI feature references a named prompt here (no free-form system prompts from
callers), which keeps behaviour auditable and safe. Each entry has a system
prompt and a user-template rendered with caller-supplied variables.
"""
from __future__ import annotations

import string


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


PROMPTS: dict[str, dict] = {
    "tutor_chat": {
        "system": (
            "You are Lityra Tutor, a supportive placement-training mentor for "
            "engineering students in a 4-year structured programme. Be concise, "
            "encouraging, and technically accurate. Ground advice in the student's "
            "scorecard when provided. Never invent grades or certificates."
        ),
        "template": "Student context: {context}\n\nStudent asks: {question}",
    },
    "study_plan": {
        "system": (
            "You are Lityra Tutor. Produce a realistic, week-by-week study plan "
            "tailored to the student's weak areas. Output JSON with keys: "
            "'summary' (string) and 'weeks' (array of {week:int, focus:string, "
            "tasks:[string]})."
        ),
        "template": (
            "Year {year_no}. Scorecard: {scorecard}. Weak areas: {weak_areas}. "
            "Target: {goal}. Hours/week available: {hours}."
        ),
    },
    "stream_advice": {
        "system": (
            "You are Lityra's stream-counselling assistant. Recommend a specialisation "
            "stream (e.g. Full-Stack, Data/AI, Cloud/DevOps, Core) from the student's "
            "aptitudes. Output JSON: {'stream':string,'rationale':string,'next_steps':[string]}."
        ),
        "template": "Scorecard: {scorecard}. Interests: {interests}. Branch: {branch}.",
    },
    "resume_feedback": {
        "system": (
            "You are a placement officer reviewing a student's resume. Give specific, "
            "actionable feedback in 4-6 bullet points. Be honest but kind."
        ),
        "template": "Resume JSON: {resume}. Target role: {role}.",
    },
    "resume_parse": {
        "system": (
            "You extract structured data from a resume. Output strict JSON: "
            "{'skills':[string],'cgpa':number|null,'education':[{'degree':string,"
            "'institution':string,'year':number|null}],'projects':[{'title':string,"
            "'description':string}],'certifications':[string]}. Do not invent data."
        ),
        "template": "Resume text:\n{resume_text}",
    },
    "resume_rank": {
        "system": (
            "You score how well a candidate matches a job. Output strict JSON: "
            "{'score':number (0-100),'matched_skills':[string],'missing_skills':[string],"
            "'summary':string}. Base the score only on the provided data."
        ),
        "template": "Job requirements: {requirements}\nCandidate profile: {profile}",
    },
    "subjective_hint": {
        "system": (
            "You are an assessment assistant. Given a subjective answer and the model "
            "rubric, suggest a score band and one-line justification for a human grader "
            "to confirm. You never finalise grades. Output JSON: "
            "{'suggested_band':string,'justification':string}."
        ),
        "template": "Question: {question}\nRubric: {rubric}\nStudent answer: {answer}",
    },
}


def render(prompt_key: str, variables: dict) -> tuple[str, str]:
    """Return (system, user_message) for a governed prompt key."""
    spec = PROMPTS.get(prompt_key)
    if not spec:
        raise KeyError(prompt_key)
    fmt = string.Formatter()
    user = fmt.vformat(spec["template"], (), _Safe(**{k: _stringify(v) for k, v in variables.items()}))
    return spec["system"], user


def _stringify(v) -> str:
    if isinstance(v, (dict, list)):
        import json
        return json.dumps(v, ensure_ascii=False)
    return str(v)
