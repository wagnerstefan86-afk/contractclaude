"""Centralized German label mappings for the Review UI."""

THEME_LABELS = {
    "audit_rights": "Audit- und Prüfungsrechte",
    "incident_reporting": "Incident Reporting und Meldepflichten",
    "sla_feasibility": "SLA-Machbarkeit",
    "bcm_itscm": "BCM / IT Service Continuity",
    "security_controls": "Sicherheitsmaßnahmen",
    "certifications": "Zertifizierungen",
    "liability_transfer": "Haftungsübertragung",
    "subcontractor": "Subunternehmer",
    "exit": "Exit-Regelungen",
    "change_management": "Change Management",
    "regulatory_passthrough": "Regulatorische Durchreichung",
    "data_protection": "Datenschutz",
    "other": "Sonstiges",
}

STATUS_LABELS = {
    "open": "Offen",
    "accepted": "Akzeptiert",
    "mitigated": "Mitigiert",
    "rejected": "Abgelehnt",
    "pending": "Ausstehend",
    "parsed": "Geparst",
    "failed": "Fehlgeschlagen",
    "completed": "Abgeschlossen",
    "running": "Läuft",
}

SEVERITY_LABELS = {
    "critical": "Kritisch",
    "high": "Hoch",
    "medium": "Mittel",
    "low": "Niedrig",
    "info": "Info",
}

MATERIALITY_LABELS = {
    "critical": "Kritisch",
    "high": "Hoch",
    "medium": "Mittel",
    "low": "Niedrig",
}

DOC_TYPE_LABELS = {
    "framework_agreement": "Rahmenvertrag",
    "security_annex": "Sicherheitsanlage",
    "sla": "Service Level Agreement",
    "questionnaire": "Fragebogen",
    "dpa": "Auftragsverarbeitungsvertrag",
    "subcontractor_agreement": "Subunternehmervertrag",
    "other": "Sonstiges",
    "pdf": "PDF",
    "docx": "DOCX",
    "xlsx": "XLSX",
}

DOC_TYPE_OPTIONS = [
    ("framework_agreement", "Rahmenvertrag"),
    ("security_annex", "Sicherheitsanlage"),
    ("sla", "Service Level Agreement"),
    ("questionnaire", "Fragebogen"),
    ("dpa", "Auftragsverarbeitungsvertrag"),
    ("subcontractor_agreement", "Subunternehmervertrag"),
    ("other", "Sonstiges"),
]


def label(mapping: dict, key: str | None) -> str:
    if not key:
        return "–"
    val = key.value if hasattr(key, "value") else str(key)
    return mapping.get(val, val)


def theme_label(key) -> str:
    return label(THEME_LABELS, key)


def status_label(key) -> str:
    return label(STATUS_LABELS, key)


def severity_label(key) -> str:
    return label(SEVERITY_LABELS, key)


def materiality_label(key) -> str:
    return label(MATERIALITY_LABELS, key)


def doc_type_label(key) -> str:
    return label(DOC_TYPE_LABELS, key)


def short_id(id_str: str | None) -> str:
    if not id_str:
        return "–"
    return id_str[:8] + "…"
