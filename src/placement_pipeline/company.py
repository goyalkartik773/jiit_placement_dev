"""Company extraction and canonicalization.

Strategy (layered, never force-fits):

1. Strip administrative lead-ins (``IMP:``, ``Reminder with extended
   timeline:``, ``Amendment of date in subject line:`` …).
2. Match a corpus-derived list of known companies anywhere in the subject
   (longest alias first) and map to a canonical spelling.
3. Fall back to taking the subject's first segment before a separator
   (`` - ``, ``:`` …) or before ``is Hiring``/``Hiring`` phrasing.
4. Last resort: a couple of body patterns (``offered by X``, ``selected by
   X``); otherwise the company stays ``None`` (typical for administrative
   mail — OTHER category).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------- lead-ins --
# Administrative prefixes that are *not* part of the company/topic name.
_LEAD_IN_RE = re.compile(
    r"^(?:"
    r"imp|important|urgent|caution|attention|humble reminder|very important"
    r"|report on time|report to labs on time and follow instructions"
    r"|amendment of date in subject line"
    r"|notification regarding"
    r"|with clarification"
    r"|slides presented by head"
    r"|your chance to shine[^:]*"
    r"|golden opportunity to grab internship at"
    r"|preparation (?:tips|guidelines) for"
    r"|prep(?:aration)? for"
    r"|registration open for"
    r"|reminder\d*(?: with extended timeline| with instruction for filling the online form\.?| to (?:attend|register|apply|participate|join))?"
    r"|revised(?:\s*&\s*updated\s+lab\s+allocation\s+for)?"
    r"|updated\s+lab\s+allocation\s+for"
    r"|correction|corrected"
    r"|fwd|fw|re|aw"
    r")\s*:?\s*",
    re.IGNORECASE,
)

# --------------------------------------------------------------- canonical --
# (alias -> canonical). Case-insensitive matching; aliases with hyphens /
# punctuation must appear exactly as written after normalization.
COMPANY_ALIASES: dict[str, str] = {
    "hackwithinfy 2026": "Infosys",
    "hackwithinfy": "Infosys",
    "infosys springboard": "Infosys",
    "infosys niche roles (sp & dse) full-time hiring for batch 2027": "Infosys",
    "infosys niche roles (sp & dse) for batch 2027": "Infosys",
    "google india": "Google",
    "google": "Google",
    "amazon wow program": "Amazon",
    "amazon wow": "Amazon",
    "amazon ml summer school": "Amazon",
    "amazon ml challenge 2026": "Amazon",
    "amazon ml challenge": "Amazon",
    "amazon hackon 6": "Amazon",
    "amazon": "Amazon",
    "accenture-mass recruitment drive": "Accenture",
    "accenture": "Accenture",
    "cognizant mass recruitment drive-hiring for full time role from 2027 batch": "Cognizant",
    "cognizant mass recruitment drive hiring for full time role from 2027 batch": "Cognizant",
    "cognizant mass recruitment drive 2027 batch": "Cognizant",
    "cognizant® technoverse hackathon 2026": "Cognizant",
    "cognizant technoverse hackathon 2026": "Cognizant",
    "cognizant": "Cognizant",
    "tata consultancy services ltd. (tcs) flagship contest codevita season 13": "TCS",
    "tcs ion": "TCS iON",
    "tcs": "TCS",
    "zs associates": "ZS Associates",
    "zs campus beats 2026": "ZS Associates",
    "zs campus beats": "ZS Associates",
    "zs": "ZS Associates",
    "ltimindtree guest lecture": "LTIMindtree",
    "ltimindtree campus engagement program": "LTIMindtree",
    "ltimindtree (ltm)": "LTIMindtree",
    "ltmindtree": "LTIMindtree",
    "ltimindtree": "LTIMindtree",
    "ltm": "LTIMindtree",
    "exclusive industry visit opportunity at ltm(ltimindtree) for batch 2027": "LTIMindtree",
    "industry visit at ltimindtree": "LTIMindtree",
    "st microelectronics": "STMicroelectronics",
    "stmicroelectronics": "STMicroelectronics",
    "hcltech amplified: the ai challenge": "HCLTech",
    "hcltech amplified": "HCLTech",
    "hcltech": "HCLTech",
    "tata technologies innovent-27": "Tata Technologies",
    "tata crucible campus quiz 2025": "Tata Group",
    "tata imagination challenge by tata group": "Tata Group",
    "smartshift technologies": "smartShift Technologies",
    "keyence india": "Keyence India",
    "play simple games": "PlaySimple Games",
    "playsimple games": "PlaySimple Games",
    "hyperverge": "HyperVerge",
    "precisely software & data india": "Precisely",
    "precision software": "Precisely",
    "d. e. shaw india": "D. E. Shaw",
    "d e shaw india": "D. E. Shaw",
    "d. e. shaw": "D. E. Shaw",
    "decimal point analytics": "Decimal Point Analytics",
    "indus valley partners": "IVP (Indus Valley Partners)",
    "ivp (indus valley partners)": "IVP (Indus Valley Partners)",
    "josh technology group (jtg)": "Josh Technology Group",
    "josh technology group": "Josh Technology Group",
    "bny code divas hackathon cum campus hiring for girl students only -2027 batch": "BNY Mellon",
    "bny code divas": "BNY Mellon",
    "fidelity international": "Fidelity International",
    "paypal india": "PayPal",
    "paypal": "PayPal",
    "zscaler": "Zscaler",
    "zcaler (summer internship drive)": "Zscaler",
    "adobe india hackathon for 2027 batch: an opportunity to get adobe internship-registration link-rush to register": "Adobe",
    "adobe india hackathon": "Adobe",
    "zopdev summer of code by zopsmart technology": "ZopSmart Technology",
    "zopsmart technology": "ZopSmart Technology",
    "my ntra": "Myntra",
    "myntra weforshe hackerramp 2026 kick-off webinar -23 june": "Myntra",
    "myntra presents \"weforshe hackerramp 2026\"-coding & innovation hackathon for women engineering students-volunteer to participate by 10 am on 21 june": "Myntra",
    "myntra weforshe hackerramp 2025": "Myntra",
    "myntra": "Myntra",
    "flipkart grid 8.0 \"prompt the future\"": "Flipkart",
    "flipkart": "Flipkart",
    "tata tcs": "TCS",
    "hartree": "Hartree",
    "symphony": "Symphony",
    "l'oréal sustainability challenge 2025: hiring challenge for engineering students batch": "L'Oreal",
    "l'oréal sustainability challenge 2025": "L'Oreal",
    "l'oréal brandstorm: global innovation challenge 2026": "L'Oreal",
    "l'oreal": "L'Oreal",
    "bajaj finserv hackrx 6.0 for 2027 batch: an opportunity to get internship [ppi & 10 lakhs cash prize] -volunteer by 10 am on 18 july 2025": "Bajaj Finserv",
    "bain- brainwars 2026": "Bain",
    "brainwars 2026": "Bain",
    "bounteous x accolite": "Bounteous x Accolite",
    "nxp cup india 2026": "NXP",
    "nxp: technical session": "NXP",
    "nxp technical session": "NXP",
    "nxp india tech startup challenge": "NXP",
    "nxp": "NXP",
    "tata elxsi teliport season 3 case challenge": "Tata Elxsi",
    "lam research challenge 2025": "Lam Research",
    "the lam research challenge 2025": "Lam Research",
    "et ai hackathon 2.0 by economic times": "Economic Times",
    "tally code brewers national coding hackathon by tally solutions": "Tally Solutions",
    "voyagehack 3.0 hackathon by tbo": "TBO",
    "quia ala": "Quia",
    "real time data services": "Real Time Data Services",
    "real time data services-hiring for ft role from batch 2027- to join as interns from june 2026, prior to joining in full-time role-final offer": "Real Time Data Services",
    "buyhutke internet": "Buyhutke Internet",
    "dr. reddy's": "Dr. Reddy's",
    "dr reddy's": "Dr. Reddy's",
    "dr. omics labs": "Dr. Omics Labs",
    "ctrls datacenter": "CtrlS Datacenter",
    "students' industrial visit to noida office of ctrls datacenter": "CtrlS Datacenter",
    "internshala portal for summer internships": "Internshala",
    "internshala portal for internships": "Internshala",
    "geeksforgeeks lms to prepare students of jus on testing of core it skills as required by product and service based companies during the placement drives": "GeeksforGeeks",
    "splunk": "Splunk",
    "publicis sapient": "Publicis Sapient",
    "vmware": "VMware",
    "goldman sachs": "Goldman Sachs",
    "morgan stanley": "Morgan Stanley",
    "summer internship opportunity at chetan trip solution pvt. ltd. for 2027 batch students": "Chetan Trip Solution",
    "chetan trip solution": "Chetan Trip Solution",
    "ltm campus engagement program": "LTIMindtree",
    "tvs credit e.p.i.c season 8": "TVS Credit",
    "gofr summer of code coding challenge for 2027 batch": "GoFr",
    "nest 2.0": "Novartis",
    "ai-driven mentoring program under aicte neat 4.0": "AICTE",
    "watchguard technology": "Watchguard Technologies",
    "watchguard technologies": "Watchguard Technologies",
    "iaa (india aviation academy) webinar series \"wings of opportunity\"": "IAA (India Aviation Academy)",
    "salescode.ai": "SalesCode.ai",
    "salescode.ai gurgaon": "SalesCode.ai",
    "salescode.ai": "SalesCode.ai",
    "prospecta software: solution consultant intern": "Prospecta Software",
    "fundwave is hiring interns only from batch 2027 to be converted to a full-time role based on performance during the 06-month internship from january 2027 to june 2027-final offers": "Fundwave",
    "juspay is hiring interns only from batch 2027 to be converted to a full-time role based on performance during the 12-month internship from september 2026-final offers": "Juspay",
    "zomato is hiring interns only from batch 2027 to be converted to full time role based on performance during 06 months internships from january 2027 to june 2027-final offers": "Zomato",
    "mu sigma hiring for full-time roles from the 2027 batch-no conversion": "Mu Sigma",
    "iit": "IIT",
    "whirlpool": "Whirlpool",
}

# Longest-alias-first list of (alias, canonical) built at import time.
_ALIAS_PAIRS: list[tuple[str, str]] = sorted(
    ((k.casefold(), v) for k, v in COMPANY_ALIASES.items()),
    key=lambda kv: len(kv[0]),
    reverse=True,
)

# Canonical names are also matchable (e.g. subject contains "Infosys" directly).
_CANONICALS = sorted({v for v in COMPANY_ALIASES.values()} | {
    "Accenture", "Amazon", "Cognizant", "Infosys", "TCS", "ZS Associates",
    "LTIMindtree", "HCLTech", "Google", "Cisco", "Adobe", "Flipkart", "Myntra",
    "Optum", "Deloitte", "Coforge", "Cadence", "Procol", "Uber", "Hyperdart",
    "MoveInSync", "Watchguard Technology", "Watchguard Technologies",
    "Razorpay", "Precisely", "Imarticus Learning", "FarmingFork Innovations",
    "Amantya Technologies", "Codestore Technologies", "ZopSmart Technology",
    "Keyence India", "PlaySimple Games", "IVP (Indus Valley Partners)",
    "Josh Technology Group", "SalesCode.ai", "HyperVerge", "Novartis",
    "Hero", "IBM", "Microsoft", "LinkedIn", "Sprinklr", "Swiggy", "Zomato",
    "Rockwell Automation", "L&T Technology Services", "KPIT", "Nvidia",
    "Rohde & Schwarz", "Progress Software", "Caelius Consulting",
    "Contata Solutions", "Penthara Technologies", "Pallav Technologies",
    "ZenTrades", "Grexa", "Twidix", "Meritshot", "Magicpin", "Vinsol Stadium",
    "Beyond the Degree", "Technum Opus", "Quokka Labs", "UNICEF",
    "Airport Authority of Indian Navy", "Indian Navy", "Indian Army",
    "Digital India Internship (NIC)", "Bharat Space Education Research Centre",
    "Majid Al Futtaim", "Economic Times", "Tally Solutions", "TBO",
    "Bajaj Finserv", "L'Oreal", "Lam Research", "Tata Elxsi", "Tata Group",
    "Tata Technologies", "BNY Mellon", "Fundwave", "Juspay", "Mu Sigma",
    "Dr. Reddy's", "Dr. Omics Labs", "CtrlS Datacenter", "GeeksforGeeks",
    "Internshala", "Bain", "D. E. Shaw", "Decimal Point Analytics",
    "Fidelity International", "PayPal", "Zscaler", "NXP", "Infosys",
    "ProcDNA", "Real Time Data Services", "Buyhutke Internet",
    "Bounteous x Accolite", "Prospecta Software", "Chetan Trip Solution",
}, key=len, reverse=True)

_GENERIC_SEGMENTS = {
    "jiit", "jaypee", "placement policy", "placement activities",
    "administrative instructions", "caution", "remider", "reminder",
    "reminder2", "reminder3", "humble reminder", "very important",
    "mock interviews", "mass recruitment drives", "seminar at open air theatre",
    "nation with namo", "the big code", "soft skills for assured dream offers",
    "online soft skills training program to prepare students for the placement drives",
    "slides presented by head", "interaction with head t&p",
    "interaction of head t&p", "debarring from placement drives/events of 2027 batch",
}

_SEPARATOR_RE = re.compile(r"\s+[-–—|]\s+|\s*[|]\s*|\s+:\s+|:\s+|\s+-|\s+–\s+")

_IS_HIRING_RE = re.compile(r"^(?P<name>.{2,60}?)\s+is\s+[Hh]iring\b")
_HIRING_RE = re.compile(r"^(?P<name>.{2,60}?)\s+[Hh]iring\s+(?:for|interns?|one|full|from|engineers?)\b")

_BODY_PATTERNS = (
    re.compile(r"(?:offered|selected)\s+by\s+\*?(?P<name>[A-Z][\w.&'() -]{1,40}?)\*?[\s.]"),
    re.compile(r"(?:offer(?:s)?\s+(?:have|has)\s+been\s+(?:made\s+)?(?:to|by))\s+\*?(?P<name>[A-Z][\w.&'() -]{1,40}?)\*?[\s.]"),
    re.compile(r"by\s+\*?(?P<name>[A-Z][\w.&'() -]{2,40}?)\*?,?\s+(?:the\s+)?hiring\s+team"),
)

# Body-captured "names" that are actually internal actors, not companies.
_BODY_STOPWORDS = re.compile(
    r"(?i)\b(department|department|students?|college|university|institute|cell|"
    r"t&p|training\s*&\s*placement|head|jiit|jaypee|batch|committee|authorities|"
    r"superset|portal|team|admin)\b"
)


def strip_lead_in(subject: str) -> str:
    text = subject
    while True:
        m = _LEAD_IN_RE.match(text)
        if not m or m.end() == 0:
            break
        text = text[m.end() :]
        if not text:
            break
    return text.strip() or subject


def _canonical(name: str) -> str:
    key = re.sub(r"\s+", " ", name).strip().casefold()
    key = key.strip(" .,:-")
    # direct alias table hit
    for alias, canon in _ALIAS_PAIRS:
        if key == alias:
            return canon
    # substring alias hit (longest first)
    for alias, canon in _ALIAS_PAIRS:
        if len(alias) >= 4 and alias in key:
            return canon
    for canon in _CANONICALS:
        if canon.casefold() == key:
            return canon
    return name.strip()


def _looks_like_company(segment: str) -> bool:
    seg = segment.strip()
    if not (2 <= len(seg) <= 70):
        return False
    if not re.search(r"[A-Za-z]", seg):
        return False
    low = seg.casefold().strip(" .,:-")
    if low in _GENERIC_SEGMENTS:
        return False
    if low.startswith((
        "interaction ", "submission of", "submit ", "register for",
        "students'", "summer internship", "national hiring assessment",
        "jiit", "jaypee", "placement", "your chance to shine",
        "online soft skills", "soft skills", "mock ", "mass recruitment",
        "debarring", "nominations for", "report ", "seminar",
        "invitation to join", "winter internship opportunity in",
        "exclusive ai event at", "exclusive industry visit opportunity at",
        "caution", "reminder", "remider", "important", "notification",
        "amendment", "admin", "the placement", "with clarification",
        "golden opportunity", "preparation ", "prep for", "your ", "the big code",
        "nation with", "off-campus", "off campus", "humble", "very important",
        "feedback from", "pending submission", "instructions ",
        "training & placements", "t&p department", "t & p department",
        "invitation to", "national hiring assessment",
    )):
        return False
    # must not be an instructiony sentence
    if seg.count(" ") > 8 and not re.search(r"(?i)\b(pvt|ltd|inc|technologies|solutions|labs|india)\b", seg):
        return False
    return True


def _match_known(text: str) -> str | None:
    low = text.casefold()
    # longest-first global match; ties broken by earliest position
    best: tuple[int, int, str] | None = None
    for alias, canon in _ALIAS_PAIRS:
        if len(alias) < 4:
            continue
        idx = low.find(alias)
        if idx == -1:
            continue
        # word-boundary-ish check
        before = low[idx - 1] if idx > 0 else " "
        after = low[idx + len(alias)] if idx + len(alias) < len(low) else " "
        if before.isalnum() or after.isalnum():
            continue
        cand = (len(alias), -idx, canon)
        if best is None or cand > best:
            best = cand
    if best:
        return best[2]
    for canon in _CANONICALS:
        idx = low.find(canon.casefold())
        if idx == -1:
            continue
        before = low[idx - 1] if idx > 0 else " "
        after = low[idx + len(canon)] if idx + len(canon) < len(low) else " "
        if before.isalnum() or after.isalnum():
            continue
        return canon
    return None


def extract_company(subject: str, body: str = "") -> tuple[str | None, str | None]:
    """Return ``(company_raw, company_canonical)``; either may be ``None``."""
    from placement_pipeline.normalize import clean_subject, flat, strip_markdown

    base = clean_subject(subject).base
    stripped = strip_lead_in(base).lstrip("- ").strip()

    known = _match_known(stripped) or _match_known(base)
    if known:
        return _raw_for(stripped, known), known

    # Explicit body statements ("selected by X") outrank the generic segment.
    clean_body = flat(strip_markdown(body))[:6000]
    for pattern in _BODY_PATTERNS:
        m = pattern.search(clean_body)
        if m:
            name = m.group("name").strip(" *.,:-")
            name = re.sub(r"^(?:the|a|an)\s+", "", name, flags=re.IGNORECASE)
            if _looks_like_company(name) and not _BODY_STOPWORDS.search(name):
                return name, _canonical(name)

    # separator first segment
    seg = _SEPARATOR_RE.split(stripped, maxsplit=1)[0].strip()
    if _looks_like_company(seg):
        return seg, _canonical(seg)

    # "X is Hiring ..." / "X Hiring for ..."
    m = _IS_HIRING_RE.match(stripped) or _HIRING_RE.match(stripped)
    if m:
        name = m.group("name").strip(" -")
        if _looks_like_company(name):
            return name, _canonical(name)

    return None, None


def _raw_for(subject: str, canonical: str) -> str:
    """Best-effort raw span for the canonical company inside the subject."""
    low = subject.casefold()
    for alias, canon in _ALIAS_PAIRS:
        if canon == canonical:
            idx = low.find(alias)
            if idx != -1:
                return subject[idx : idx + len(alias)]
    idx = low.find(canonical.casefold())
    if idx != -1:
        return subject[idx : idx + len(canonical)]
    return canonical
