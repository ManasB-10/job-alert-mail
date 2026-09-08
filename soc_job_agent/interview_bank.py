"""Curated SOC Analyst interview Q&A bank.

Hand-written rather than Gemini-generated: technical accuracy matters for
interview prep, and a static curated bank is cheaper and more reliable than
per-run generation. Expand this list over time as you find real questions.
"""

from __future__ import annotations

QUESTIONS: list[dict] = [
    # --- SIEM & Log Analysis ---
    {"category": "SIEM & Log Analysis", "question": "What is a SIEM and what are its core functions?",
     "answer": "A Security Information and Event Management system aggregates logs/events from across the "
               "environment, correlates them to detect suspicious patterns, generates alerts, and supports "
               "investigation with search and dashboards. Core functions: log collection, normalization, "
               "correlation, alerting, and reporting."},
    {"category": "SIEM & Log Analysis", "question": "What's the difference between a false positive and a true positive alert?",
     "answer": "A true positive is an alert that correctly identifies real malicious/anomalous activity. A false "
               "positive fires on benign activity that superficially matches a detection rule (e.g. an admin's "
               "legitimate remote login flagged as 'impossible travel'). Tuning rules to reduce false positives "
               "without missing true positives is a core SOC skill."},
    {"category": "SIEM & Log Analysis", "question": "What log sources would you prioritize when investigating a suspected compromised endpoint?",
     "answer": "Windows Security/Event logs (logon events 4624/4625, process creation 4688), EDR telemetry "
               "(process tree, network connections), firewall/proxy logs (outbound connections), DNS logs, and "
               "authentication logs (AD/VPN). Correlate timestamps across sources to build a timeline."},
    # --- Incident Response ---
    {"category": "Incident Response", "question": "What are the phases of the incident response lifecycle?",
     "answer": "Preparation, Identification, Containment, Eradication, Recovery, and Lessons Learned (post-"
               "incident review). Some frameworks split Containment into short-term and long-term."},
    {"category": "Incident Response", "question": "What is the difference between containment and eradication?",
     "answer": "Containment stops the threat from spreading further (e.g. isolating an infected host from the "
               "network) without necessarily removing it yet. Eradication actually removes the root cause "
               "(malware, backdoor, compromised account) after containment has limited the damage."},
    {"category": "Incident Response", "question": "As a Tier-1 analyst, what would you do first when you receive a high-severity alert?",
     "answer": "Validate the alert isn't a false positive, gather context (asset criticality, user, related "
               "events), assess scope/impact, and follow the playbook -- escalate to Tier-2 if it's confirmed "
               "malicious or beyond your authority to act, while documenting everything in the ticket."},
    # --- Networking ---
    {"category": "Networking", "question": "What's the difference between a firewall, an IDS, and an IPS?",
     "answer": "A firewall enforces allow/deny rules on traffic based on ports/protocols/IPs. An IDS "
               "(Intrusion Detection System) monitors traffic and alerts on suspicious patterns but doesn't "
               "block. An IPS (Intrusion Prevention System) does the same detection but can actively block/drop "
               "the traffic in-line."},
    {"category": "Networking", "question": "What is a three-way handshake and why does it matter for a SOC analyst?",
     "answer": "TCP's SYN, SYN-ACK, ACK sequence to establish a connection. It matters because incomplete "
               "handshakes (many SYNs, no ACKs) are a classic sign of a SYN flood/port scan, visible in packet "
               "captures or flow logs."},
    {"category": "Networking", "question": "What is DNS tunneling and why is it a security concern?",
     "answer": "Encoding data (commands, exfiltrated data) inside DNS queries/responses to bypass firewalls that "
               "allow DNS traffic. It's a concern because it can be used for C2 communication or data "
               "exfiltration that looks like normal DNS traffic unless specifically inspected."},
    # --- MITRE ATT&CK & Threat Intel ---
    {"category": "MITRE ATT&CK & Threat Intel", "question": "What is the MITRE ATT&CK framework and how would you use it as an analyst?",
     "answer": "A knowledge base of real-world adversary tactics and techniques (e.g. Initial Access, "
               "Execution, Persistence). Analysts use it to map observed activity to known techniques, "
               "understand attacker intent/next steps, and build/tune detections around specific techniques."},
    {"category": "MITRE ATT&CK & Threat Intel", "question": "What is an IOC and give three examples.",
     "answer": "Indicator of Compromise -- an artifact suggesting a breach. Examples: a malicious file hash, a "
               "known-bad IP/domain, or a suspicious registry key/mutex created by malware."},
    {"category": "MITRE ATT&CK & Threat Intel", "question": "What's the difference between an IOC and a TTP?",
     "answer": "An IOC is a specific, often ephemeral artifact (a hash, an IP) that's easy for attackers to "
               "change. A TTP (Tactic, Technique, Procedure) describes the attacker's behavior/methodology, "
               "which is harder for them to change and more durable to detect against."},
    # --- Malware & Phishing ---
    {"category": "Malware & Phishing", "question": "How would you analyze a suspicious email reported as phishing?",
     "answer": "Check the sender's actual address/domain (not just display name), inspect headers for spoofing "
               "(SPF/DKIM/DMARC results), hover/inspect links without clicking (or use a sandbox), check for "
               "urgency/credential-harvesting language, and check attachments via sandbox/hash reputation "
               "before deciding to block sender/domain and notify affected users."},
    {"category": "Malware & Phishing", "question": "What is the difference between a virus, a worm, and a trojan?",
     "answer": "A virus attaches to a host file and needs user action to spread. A worm self-replicates and "
               "spreads across networks without user action. A trojan disguises itself as legitimate software "
               "to trick users into running it, without self-replicating."},
    {"category": "Malware & Phishing", "question": "What is a C2 (command and control) server?",
     "answer": "An attacker-controlled server that compromised machines ('beacons') communicate with to receive "
               "commands and exfiltrate data. Detecting C2 beaconing (regular outbound connections to unusual "
               "destinations) is a key SOC detection use case."},
    # --- Tools & Scripting ---
    {"category": "Tools & Scripting", "question": "Why would a SOC analyst want basic scripting skills (e.g. Python)?",
     "answer": "To automate repetitive tasks (parsing logs, enriching IOCs against threat intel APIs, bulk "
               "lookups), write small tools when no ready-made one exists, and eventually contribute to "
               "SOAR playbooks."},
    {"category": "Tools & Scripting", "question": "What would you use Wireshark for during an investigation?",
     "answer": "Inspecting raw packet captures to see exact protocol-level traffic -- e.g. confirming data "
               "exfiltration, examining a suspicious connection's payload, or verifying whether traffic matches "
               "a known malware family's network signature."},
    # --- Fresher-specific / Behavioral ---
    {"category": "Fresher/Behavioral", "question": "You don't have professional SOC experience yet -- how do you demonstrate readiness for an L1 role?",
     "answer": "Talk concretely about hands-on practice: home-lab SIEM setups (e.g. Splunk free tier, Security "
               "Onion), TryHackMe/LetsDefend SOC-analyst rooms, CTFs, relevant certs (Security+/CySA+), and any "
               "personal projects analyzing logs or building detections -- tie each back to a real SOC task."},
    {"category": "Fresher/Behavioral", "question": "How would you handle an alert you don't know how to interpret?",
     "answer": "Don't guess or ignore it. Check the playbook/runbook for that alert type, search internal "
               "documentation/past tickets, escalate to a senior analyst with what you've found so far rather "
               "than sitting on it, and document what you learn for next time."},
    {"category": "Fresher/Behavioral", "question": "Why do you want to work in a SOC specifically, rather than another IT role?",
     "answer": "A genuine answer tying to interest in defensive security, pattern recognition/investigation, "
               "and wanting hands-on exposure to real attacks as a stepping stone toward incident response or "
               "threat hunting -- avoid a generic 'I like cybersecurity' answer with no specifics."},
]
