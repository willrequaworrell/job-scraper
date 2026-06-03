# Scoring Policy

Apply these rules generically when judging fit between a candidate profile and a job description. This file defines how to evaluate evidence conservatively. It does not define the candidate's preferences, target roles, geography, or anti-targets.

## Core Principles

- Separate must-have requirements from preferred requirements.
- Judge the center of gravity of the role, not just keyword overlap.
- Treat hard constraints as real evidence, especially location, work arrangement, employment type, and work authorization when clearly stated.
- Distinguish core function mismatch from experience gap.
- Judge seniority conservatively.
- Treat required years of experience as meaningful evidence, but not as an automatic disqualifier.
- Do not treat in-profile local geographies, acceptable hybrid requirements, or in-scope remote arrangements as negative evidence.
- Do not treat low minimum experience requirements as negative evidence for non-internship roles.
- Distinguish AI application work from AI infrastructure, ML, data science, and research work as a generic role-classification rule.
- Separate missing evidence from negative evidence.
- Ground justifications in specific evidence from the job description and candidate profile.
- Keep explanations anchored to the source materials without restating large parts of the job posting.
- Do not infer unstated candidate qualifications.
- Do not let partial technology overlap overcome a structural mismatch in role function, seniority, or constraints.
- Let hard-constraint mismatch outweigh technical overlap when they conflict.

## Score Calibration

- Keep `fit_score` tightly aligned to the numeric score bands provided in the prompt.
- Derive `verdict` from the score band rather than choosing it independently.
- A few attractive technologies should not outweigh a clear contradiction in role shape, seniority, or hard constraints.
- Roles with 0 to 3 years of required experience are generally in bounds when the profile targets junior-to-mid level work.
- A requirement framed as 2+ years should usually be treated as in bounds for a junior-to-mid profile unless the role is clearly more senior for other reasons.
- Required experience of 4+ years is a meaningful negative signal and should noticeably reduce the score unless the role is otherwise unusually accessible.
- Explicit senior/staff/principal/lead/architect framing should carry more weight than generic technology overlap.
- Greater Boston locations named in the candidate profile, including Cambridge and similar nearby cities, should be treated as local fit rather than relocation concern.
- Local, hybrid, and remote should be treated neutrally relative to one another unless the candidate profile explicitly states a preference or the job imposes an incompatible restriction.

## Output Field Guidance

- `matching_skills` should be short and evidence-based.
- `gaps` should be short and evidence-based.
- `gaps` may include role-family, seniority, employment-type, location, or other constraint mismatches, not just missing technologies.
- Do not list location as a gap when the job is in an explicitly in-scope local geography from the profile.
- Do not list `0-3 years` or `2+ years` as a gap by itself for a junior-to-mid candidate profile unless the job also contains stronger seniority evidence.
