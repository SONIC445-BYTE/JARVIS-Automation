"""
The detector's entire knowledge, in one readable file.

Why a lexicon and regex rules rather than a local NER/classifier model
-- the trade is stated here rather than buried, because PG-001's whole
point is that the detector's limits are published:

*   **§3.7b forbids the cloud option outright.** Session content in a
    session that may have drifted clinical is, by assumption, possibly
    clinical. Sending it to a cloud classifier to find out whether it
    is clinical would make the detector itself the leak. So the only
    real choice is "local model" vs. "local rules".

*   **§3.1's hardware is an i5/Ryzen-5 laptop, 8-16 GB, integrated
    graphics, no CUDA**, and this runs per-utterance in a live voice
    loop that already spends ~9.9s to first spoken word (S0-E9). A
    transformer NER pass costs tens to hundreds of ms of CPU that is
    directly contended with STT and the LLM. Rules cost microseconds.

*   **What rules buy:** deterministic and reproducible (the same input
    scores identically forever, so a published metric stays true);
    auditable line by line by a clinician or a hospital's compliance
    officer; zero new dependencies and no model file to ship, version,
    or keep in sync; every finding carries the literal reason it fired.

*   **What rules cost, plainly:** no generalisation to surface forms
    nobody wrote down. Paraphrase defeats them. Person-name detection
    without a gazetteer is structural (titles, syntactic context,
    capitalisation) and therefore weak on lowercase transcription --
    which is exactly what an STT stream often produces -- and weak on
    transliterated Indic names, which is the actual deployment
    population. A model would generalise better and would be the right
    call for **Mode B**, where the detector is on the critical path and
    a miss silently breaks pseudonymisation. For Mode C's secondary
    drift-catch, where a miss costs a late safety net and not the
    primary guarantee, the deterministic-and-measurable trade is
    defensible. That reasoning does not transfer to Mode B and must not
    be reused there without re-deciding it.

**No gazetteer of names, deliberately.** A name list would inflate
recall on any corpus whose names came from the same list -- and since
the evaluation corpus in this package was written by the same author as
this file, that inflation would be self-inflicted and invisible. Name
detection is structural only. `_NON_NAME_TOKENS` below is a stoplist of
generic English/product vocabulary, kept to categories that exist
independent of the corpus (weekdays, months, common function words,
widely-known software names). It was not extended to fix individual
corpus false positives; the resulting precision is reported as measured.
"""
from __future__ import annotations

import re

DETECTOR_VERSION = "pg001-modec-drift-1.0.0"

# ---------------------------------------------------------------------------
# Clinical vocabulary. Weight = how much this single term alone should move
# belief that a *patient's care* is being discussed.
#
# STRONG   -- essentially only used clinically.
# MEDIUM   -- clinical in a hospital, but has ordinary senses.
# WEAK     -- appears constantly in ordinary speech; near-useless alone,
#             contributes only in combination. These exist so that the
#             "ordinary speech that superficially looks clinical" cases in
#             the corpus have a genuine chance to produce a false positive
#             rather than being trivially excluded.
# ---------------------------------------------------------------------------
STRONG = 0.88
MEDIUM = 0.55
WEAK = 0.22

CLINICAL_TERMS: dict[str, float] = {
    # --- drugs / dosing -----------------------------------------------------
    "paracetamol": STRONG, "acetaminophen": STRONG, "amoxicillin": STRONG,
    "azithromycin": STRONG, "ceftriaxone": STRONG, "metformin": STRONG,
    "insulin": STRONG, "heparin": STRONG, "warfarin": STRONG,
    "ondansetron": STRONG, "pantoprazole": STRONG, "furosemide": STRONG,
    "salbutamol": STRONG, "prednisolone": STRONG, "morphine": STRONG,
    "antibiotic": STRONG, "antibiotics": STRONG, "analgesic": STRONG,
    "iv fluids": STRONG, "saline drip": STRONG, "nebuliser": STRONG,
    "nebulizer": STRONG, "mg/kg": STRONG, "bd dosing": STRONG,
    "broad-spectrum": MEDIUM, "dosage": MEDIUM, "dose": WEAK,
    "prescription": MEDIUM, "prescribe": MEDIUM, "prescribed": MEDIUM,
    "tapering": MEDIUM, "medication": MEDIUM, "tablet": WEAK,
    # --- symptoms / findings ------------------------------------------------
    "dyspnoea": STRONG, "dyspnea": STRONG, "haemoptysis": STRONG,
    "hemoptysis": STRONG, "tachycardia": STRONG, "bradycardia": STRONG,
    "hypotension": STRONG, "hypertension": STRONG, "hypoxia": STRONG,
    "febrile": STRONG, "afebrile": STRONG, "oedema": STRONG, "edema": STRONG,
    "jaundice": STRONG, "cyanosis": STRONG, "sepsis": STRONG,
    "septic": STRONG, "seizure": STRONG, "syncope": STRONG,
    "chest pain": STRONG, "shortness of breath": STRONG,
    "abdominal pain": STRONG, "vomiting": MEDIUM, "nausea": MEDIUM,
    "fever": MEDIUM, "spiking a temperature": STRONG, "breathless": MEDIUM,
    "swelling": WEAK, "rash": MEDIUM, "bleeding": WEAK,
    # --- diagnoses ----------------------------------------------------------
    "diabetes": STRONG, "diabetic": STRONG, "asthma": STRONG,
    "pneumonia": STRONG, "tuberculosis": STRONG, "anaemia": STRONG,
    "anemia": STRONG, "myocardial infarction": STRONG, "stroke": MEDIUM,
    "fracture": MEDIUM, "carcinoma": STRONG, "malignancy": STRONG,
    "diagnosis": MEDIUM, "differential": WEAK, "comorbidity": STRONG,
    "prognosis": MEDIUM,
    # --- investigations -----------------------------------------------------
    "haemoglobin": STRONG, "hemoglobin": STRONG, "creatinine": STRONG,
    "troponin": STRONG, "hba1c": STRONG, "electrolytes": STRONG,
    "platelet count": STRONG, "leucocyte": STRONG, "leukocyte": STRONG,
    "blood culture": STRONG, "urine culture": STRONG, "biopsy": STRONG,
    "histopath": STRONG, "ultrasound": MEDIUM, "echocardiogram": STRONG,
    "angiogram": STRONG, "endoscopy": STRONG, "colonoscopy": STRONG,
    "x-ray": MEDIUM, "chest x-ray": STRONG, "ct scan": MEDIUM,
    "mri": MEDIUM, "ecg": STRONG, "ekg": STRONG, "cbc": MEDIUM,
    "lft": MEDIUM, "rft": MEDIUM, "blood sugar": STRONG,
    "blood pressure": STRONG, "bp reading": STRONG, "saturation": MEDIUM,
    "spo2": STRONG, "vitals": STRONG, "labs": WEAK, "lab report": MEDIUM,
    # --- care process -------------------------------------------------------
    "patient": STRONG, "patients": STRONG, "admitted": MEDIUM,
    "admission": MEDIUM, "discharge summary": STRONG, "discharged": MEDIUM,
    "ward round": STRONG, "ward": MEDIUM, "icu": STRONG, "hdu": STRONG,
    "casualty": MEDIUM, "opd": STRONG, "outpatient": STRONG,
    "inpatient": STRONG, "triage": MEDIUM, "referral": WEAK,
    "consultant": WEAK, "attending": WEAK, "resident doctor": STRONG,
    "nursing": MEDIUM, "nurse": MEDIUM, "physician": MEDIUM,
    "surgeon": MEDIUM, "clinical": MEDIUM, "clinically": MEDIUM,
    "intubate": STRONG, "intubated": STRONG, "catheter": STRONG,
    "cannula": STRONG, "sutures": STRONG, "dressing change": STRONG,
    "operation theatre": STRONG, "operating theatre": STRONG,
    "post-op": STRONG, "pre-op": STRONG, "surgery": MEDIUM,
    "consent form": WEAK, "case sheet": STRONG, "case notes": MEDIUM,
    "chart": WEAK, "history and examination": STRONG, "examined": WEAK,
    "follow-up visit": MEDIUM, "review in": WEAK, "npo": STRONG,
    "nil by mouth": STRONG, "cc": WEAK,
    # --- ambiguous-on-purpose ----------------------------------------------
    "critical": WEAK, "stable": WEAK, "acute": WEAK, "chronic": WEAK,
    "recovery": WEAK, "treatment": WEAK, "monitor": WEAK, "scan": WEAK,
    "symptoms": MEDIUM, "condition": WEAK, "bleeding out": WEAK,
}

# Longest-first so "chest x-ray" wins over "x-ray".
_CLINICAL_PATTERN = re.compile(
    r"(?<![\w-])(" + "|".join(
        re.escape(t) for t in sorted(CLINICAL_TERMS, key=len, reverse=True)
    ) + r")(?![\w-])",
    re.IGNORECASE,
)


def clinical_matches(text: str) -> list[tuple[str, int, int, float]]:
    """(term, start, end, weight) for every clinical vocabulary hit."""
    out: list[tuple[str, int, int, float]] = []
    for m in _CLINICAL_PATTERN.finditer(text):
        term = m.group(1).lower()
        out.append((term, m.start(1), m.end(1), CLINICAL_TERMS[term]))
    return out


# ---------------------------------------------------------------------------
# Non-clinical context markers. Damp the clinical score when the surrounding
# talk is unambiguously about software, home, vehicles, sport or admin -- the
# domains where "critical", "patient", "chronic", "recovery", "monitor",
# "operation" and "stable" get used constantly by people who are not treating
# anyone. Damping, never veto: a physician can absolutely say "the server is
# down, also bed 4 is septic" in one breath.
# ---------------------------------------------------------------------------
NON_CLINICAL_MARKERS: tuple[str, ...] = (
    "server", "database", "laptop", "deploy", "deployment", "repository",
    "commit", "merge", "pull request", "compile", "firewall", "router",
    "wifi", "printer", "spreadsheet", "invoice", "reboot", "restart the",
    "software", "hard drive", "backup", "password reset", "api",
    "car", "engine oil", "tyre", "gearbox", "mileage", "petrol",
    "washing machine", "geyser", "plumber", "electrician", "rent",
    "landlord", "grocery", "cricket", "football", "match", "innings",
    "flight", "boarding", "hotel", "taxi", "movie", "restaurant",
    "salary", "appraisal", "meeting room", "slide deck",
)
_NON_CLINICAL_PATTERN = re.compile(
    r"(?<![\w-])(" + "|".join(
        re.escape(t) for t in sorted(NON_CLINICAL_MARKERS, key=len, reverse=True)
    ) + r")(?![\w-])",
    re.IGNORECASE,
)


def non_clinical_matches(text: str) -> list[str]:
    return [m.group(1).lower() for m in _NON_CLINICAL_PATTERN.finditer(text)]


# ---------------------------------------------------------------------------
# Identifier rules. Each returns spans with a fixed prior; `detector.py`
# applies context adjustment where documented.
# ---------------------------------------------------------------------------

# MRN / UHID / registration number, cue-led.
RE_PATIENT_ID_CUED = re.compile(
    r"\b(?:MRN|UHID|IP\s?(?:no\.?|number)|OP\s?(?:no\.?|number)|"
    r"patient\s*(?:id|no\.?|number)|hospital\s*(?:no\.?|number)|"
    r"reg(?:istration)?\s*(?:no\.?|number)|case\s*(?:no\.?|number))"
    r"\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]{3,})",
    re.IGNORECASE,
)
# Bare record-number shape, e.g. "MH-2291043" or "UH4471029". Fires without a
# cue, so it is low confidence on purpose.
RE_PATIENT_ID_BARE = re.compile(r"\b([A-Z]{2,4}[-/]?\d{5,9})\b")

RE_BED = re.compile(
    r"\b((?:bed|cot|bay|cubicle|ward|room|cabin)\s*(?:no\.?|number|#)?\s*"
    r"(?:\d{1,4}[A-Za-z]?|[A-Z]-?\d{1,3}))\b",
    re.IGNORECASE,
)
# "the one in 12", "shifted to 4B" -- bed reference with the noun elided.
RE_BED_ELIDED = re.compile(
    r"\b(?:in|to|from|at)\s+(\d{1,2}[A-Za-z]?)\b(?=[^\w]|$)",
)

RE_PHONE = re.compile(
    r"(?<![\d-])((?:\+91[\s-]?)?[6-9]\d{9}|\d{3}[\s-]\d{3}[\s-]\d{4}|"
    r"\(\d{3}\)\s?\d{3}-\d{4})(?![\d-])"
)
RE_EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")

_DATE = (
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\.?\s+\d{4}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})"
)
RE_DOB = re.compile(
    r"\b(?:d\.?o\.?b\.?|date\s+of\s+birth|born\s+on|birth\s*date)"
    r"\s*(?:is|was)?\s*[:\-]?\s*(" + _DATE + r")",
    re.IGNORECASE,
)

RE_AGE_SEX = re.compile(
    r"\b(\d{1,3}\s*[-/]?\s*(?:year|yr|y)[\s-]*(?:old|o)?[\s,]*"
    r"(?:male|female|man|woman|boy|girl|gentleman|lady|m\b|f\b)"
    r"|\d{1,3}\s*/\s*[MF]\b)",
    re.IGNORECASE,
)

# 12-digit national-ID shape (Aadhaar-like). Deliberately mid confidence: a
# 12-digit run is not exclusively an ID.
RE_NATIONAL_ID = re.compile(r"(?<!\d)(\d{4}\s?\d{4}\s?\d{4})(?!\d)")

RE_ADDRESS = re.compile(
    r"\b(\d+[A-Za-z]?[,/]?\s+(?:[A-Z][A-Za-z]+\s+){0,3}"
    r"(?i:street|road|rd\.?|lane|marg|nagar|colony|apartments?|apts?\.?|"
    r"block|sector|cross|society|enclave|layout))\b",
)

# Person-name rules -- structural only, no name list.
RE_NAME_TITLED = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Shri|Smt|Sri)\.?\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"
)
RE_NAME_CUED = re.compile(
    r"\b(?:patient|admitted|discharged|attendant|relative|referred|"
    r"called|named|for|with|to|by)\s+"
    r"(?:is\s+|was\s+|a\s+)?([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b"
)
RE_NAME_BARE = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b")

# Generic stoplist. See module docstring: kept to categories that exist
# independently of the evaluation corpus.
_NON_NAME_TOKENS: frozenset[str] = frozenset(
    """
    monday tuesday wednesday thursday friday saturday sunday
    january february march april may june july august september october
    november december
    the this that these those there their they them then than when where
    what which while with without who whom whose why how here have has had
    and but for nor yet because since although though after before during
    until unless about above across against among around behind below
    beneath beside between beyond despite except inside into like near
    onto outside over through toward under upon within
    can could shall should will would may might must
    yes okay ok sure fine good great please thanks thank hello hey
    also just only still even both each every some many much more most
    less least other another such same own very too now today tomorrow
    yesterday morning afternoon evening night week month year
    hospital clinic ward doctor nurse patient sister matron
    windows linux macos android chrome firefox excel word outlook teams
    zoom slack github google gmail whatsapp youtube python java
    internet email phone laptop printer server database wifi
    monday's covid dengue malaria typhoid
    i we you he she it me my your his her our its
    """.split()
)


def is_probable_non_name(token: str) -> bool:
    return token.lower() in _NON_NAME_TOKENS
