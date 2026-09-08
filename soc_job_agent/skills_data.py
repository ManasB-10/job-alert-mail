"""Curated SOC-relevant skill/tool/certification keywords.

Deliberately deterministic (regex keyword matching, not an LLM call): this
list is what skill_gap.py and linkedin_coach.py count frequencies against,
so it costs nothing per run and gives reproducible results.
"""

from __future__ import annotations

import re

# (display name, category, regex pattern)
SKILL_KEYWORDS: list[tuple[str, str, str]] = [
    # SIEM platforms
    ("Splunk", "SIEM", r"\bsplunk\b"),
    ("IBM QRadar", "SIEM", r"\bqradar\b"),
    ("Microsoft Sentinel", "SIEM", r"\b(microsoft\s+)?sentinel\b"),
    ("ArcSight", "SIEM", r"\barcsight\b"),
    ("LogRhythm", "SIEM", r"\blogrhythm\b"),
    ("Elastic/ELK Stack", "SIEM", r"\b(elk\s+stack|elasticsearch|elastic\s+stack)\b"),
    ("Wazuh", "SIEM", r"\bwazuh\b"),
    # EDR / endpoint
    ("CrowdStrike", "EDR", r"\bcrowdstrike\b"),
    ("SentinelOne", "EDR", r"\bsentinelone\b"),
    ("Microsoft Defender", "EDR", r"\b(microsoft\s+)?defender\b"),
    ("Carbon Black", "EDR", r"\bcarbon\s*black\b"),
    ("Cortex XDR", "EDR", r"\bcortex\s*xdr\b"),
    # Network / analysis tools
    ("Wireshark", "Network Analysis", r"\bwireshark\b"),
    ("tcpdump", "Network Analysis", r"\btcpdump\b"),
    ("Firewall management", "Network Security", r"\bfirewalls?\b"),
    ("IDS/IPS", "Network Security", r"\b(ids/ips|intrusion\s+(detection|prevention))\b"),
    ("Proxy/Zscaler", "Network Security", r"\bzscaler\b"),
    # SOAR / automation
    ("SOAR", "Automation", r"\bsoar\b"),
    ("Palo Alto XSOAR", "Automation", r"\bxsoar\b"),
    ("Python scripting", "Automation", r"\bpython\b"),
    ("PowerShell", "Automation", r"\bpowershell\b"),
    # Core SOC skills
    ("Incident Response", "Core Skill", r"\bincident\s+response\b"),
    ("Threat Hunting", "Core Skill", r"\bthreat\s+hunt(ing)?\b"),
    ("Threat Intelligence", "Core Skill", r"\bthreat\s+intel(ligence)?\b"),
    ("MITRE ATT&CK", "Core Skill", r"\bmitre\s*att&?ck\b"),
    ("Malware Analysis", "Core Skill", r"\bmalware\s+analysis\b"),
    ("Phishing Analysis", "Core Skill", r"\bphishing\b"),
    ("Vulnerability Management", "Core Skill", r"\bvulnerabilit(y|ies)\s+(management|assessment)\b"),
    ("Log Analysis", "Core Skill", r"\blog\s+analysis\b"),
    ("Windows Event Logs", "Core Skill", r"\bwindows\s+event\s+logs?\b"),
    # OS / infra
    ("Linux", "Infrastructure", r"\blinux\b"),
    ("Active Directory", "Infrastructure", r"\bactive\s+directory\b"),
    ("Cloud Security (AWS)", "Cloud", r"\baws\b"),
    ("Cloud Security (Azure)", "Cloud", r"\bazure\b"),
    ("Cloud Security (GCP)", "Cloud", r"\bgcp\b|google\s+cloud"),
    # Ticketing / process
    ("ServiceNow", "Process/Tooling", r"\bservicenow\b"),
    ("Jira", "Process/Tooling", r"\bjira\b"),
    ("ITIL", "Process/Tooling", r"\bitil\b"),
    # Certifications
    ("CompTIA Security+", "Certification", r"\bsecurity\+\b"),
    ("CompTIA CySA+", "Certification", r"\bcysa\+\b"),
    ("Microsoft SC-200", "Certification", r"\bsc-?200\b"),
    ("GIAC GCIH", "Certification", r"\bgcih\b"),
    ("eLearnSecurity eJPT", "Certification", r"\bejpt\b"),
    ("Certified Ethical Hacker (CEH)", "Certification", r"\bceh\b|certified\s+ethical\s+hacker"),
    ("CISSP", "Certification", r"\bcissp\b"),
]

_COMPILED = [(name, category, re.compile(pattern, re.I)) for name, category, pattern in SKILL_KEYWORDS]


def extract_matches(text: str) -> set[str]:
    """Returns the set of skill display-names whose pattern matches `text`."""
    return {name for name, _category, pattern in _COMPILED if pattern.search(text)}


def all_skill_names() -> list[str]:
    return [name for name, _category, _pattern in SKILL_KEYWORDS]


def category_of(name: str) -> str:
    for skill_name, category, _pattern in SKILL_KEYWORDS:
        if skill_name == name:
            return category
    return "Other"
