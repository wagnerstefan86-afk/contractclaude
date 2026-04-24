# Matrix v1.3 — Deferred Rules

**Quelle:** `docs/InfoSec_ContractReview_Master_Matrix_v1_3.csv`
**Mapping-Referenz:** `docs/Matrix_v1_3_to_System_Mapping.md`

Regeln, die im aktuellen Freeze **nicht** technisch automatisiert wurden,
mit Kategorie und Begründung. Ziel: keine Matrix-Regel geht verloren,
und die Leitplanken (keine neuen Playbooks, keine neuen Lenses, keine
Modelländerungen) bleiben eingehalten.

Kategorien:

- `manual_review_only` — Policy- / Legal- / Kontext-Entscheidung,
  nicht zuverlässig aus Klauseltext ableitbar.
- `future_playbook` — eigenes Risikomuster, das einen neuen
  Playbook-Eintrag erfordern würde.
- `future_lens` — gehört in eine noch nicht aktivierte Lens.
- `outside_current_scope` — Themenfeld bewusst außerhalb PoC-Scope.
- `needs_policy_decision` — fachliche Policy-Entscheidung vor
  Automatisierung nötig.

## 1. `approved` + `review_needed=no`, aber bewusst nicht automatisiert

| rule_id | theme / subtheme | Kategorie | Grund |
|---|---|---|---|
| **AUD-005** | audit_rights / audit_effort_cap_customer | needs_policy_decision | 50-PT-Schwellwert ist Vorstandspolicy. Klauseltext nennt die Zahl selten; die Risikoentscheidung hängt an der Gesamtkalkulation. Der Matcher/Classifier hat keinen robusten Zugang zur PT-Summe. |
| **AUD-006** | audit_rights / regulatory_audit_carveout | manual_review_only | „Behördlich angeordnete Audits sind vom Cap ausgenommen" ist Legal-Carveout. Entscheidung braucht regulatorischen Kontext (BaFin / DORA / NIS2), nicht aus Text allein ableitbar. |
| **AUD-007** | audit_rights / pooled_multi_customer_audit | future_playbook | „Sammel-/Verbundaudit" ist ein eigenes Risikomuster; es existiert kein passender Playbook-Eintrag. Leitplanke: keine neuen Playbooks in diesem Schritt. |
| **AUD-009** | audit_rights / pentest_rights | future_playbook | Pentest / Schwachstellenscan / Red-Team ist ein eigener Prüfmodus. CSV-Notiz: „Kein eigener Playbook-Eintrag vorhanden - Lücke für spätere Pipeline-Ableitung." |
| **INC-007** | incident_reporting / event_threshold (security_service) | future_playbook | Service-Kontext `security_service` (SIEM/SOC-Service). Ohne Kontext-Attribut kein robuster Matcher-Key, außerdem kein Playbook-Eintrag. |
| **INC-008** | incident_reporting / incident_support_model | manual_review_only | Causality-/Einflussbereichsprüfung zentral („eigener Verschuldensbereich" vs. „außerhalb Einflussbereich"). Aus Text allein nicht robust ableitbar — erfordert Vertragsrahmen. |
| **INC-009** | incident_reporting / incident_information_disclosure | manual_review_only | „Alle Informationen" vs. „insoweit erforderlich / konkreter Bezug" ist eine Scope-Diskriminierung, die Mandantenschutz + Zweckbindung voraussetzt. Kein robustes Textsignal. |
| **CERT-005** | certifications / evidence_obligations | manual_review_only | „Sämtliche Policies auf Verlangen" vs. „SoA-Extrakt / Executive Summary" — kontextabhängige Bewertung durch Reviewer. |
| **GOV-007** | governance_controls / back_to_back_certification_reliance | manual_review_only | Eignungsleihe mit Back-to-back-Kopplung ist primär Legal/Compliance-Thema. Aus dem Text nicht zuverlässig ableitbar. |

### Bereits durch bestehende Pipeline abgedeckt — keine separate Automatisierung nötig

| rule_id | theme / subtheme | Mechanismus |
|---|---|---|
| **AUD-001** | audit_frequency | PB-AUDIT-001.negative_any + `_EXPLICIT_LIMITS_FREQUENCY` — Phase 2a fertig. |
| **AUD-002** | audit_notice_period | `_EXPLICIT_LIMITS_NOTICE` (tage/werktage vorlauf, vorlaufzeit von mindestens) + PB-AUDIT-001.negative_any — Phase 2a fertig. |
| **AUD-008** | direct_third_party_audit | PB-AUDIT-002 — schon seit Phase 1 / Phase 2a / v1.3 AUD-008 Zusatz `ohne mandat`. |
| **AUD-010** | audit_scope_limitation | `_DEFENSIVE_SCOPE_LIMIT` — Phase 2a fertig; v1.3 AUD-010 Zusatz `unmittelbarer zusammenhang`. |
| **AUD-011** | controlled_third_party_audit | PB-AUDIT-002.negative_any erweitert um `schriftliches mandat / wirtschaftsprüfer / zur verschwiegenheit verpflichtet`. |
| **AUD-003** | audit_questionnaire_preparation | `_EXPLICIT_LIMITS_NOTICE` erweitert um `kalendertage vorab / werktage vorab`. |
| **AUD-004** | audit_cost_model | `_EXPLICIT_LIMITS_COST_MODEL` erweitert um `personentage inklusive / pt inklusive` + PB-AUDIT-003.negative_any. |
| **INC-001** | event_threshold | PB-INC-002 fertig. |
| **INC-002** | regulatory_notification | PB-INC-003 fertig. |
| **INC-003** | notification_deadlines | PB-INC-001 + Tight-Time-Klassifizierer fertig. |
| **INC-004** | pre_disclosure_approval | `_EXPLICIT_LIMITS_CONSENT` + Reviewer-Default bereits ok. |
| **INC-005** | root_cause_reporting | `_REMEDIATION_*` Patterns — GS-01-Fixture zeigt Abschlussbericht/5-Werktage korrekt info. |
| **CERT-001** | iso_27001_evidence | `_POSITIVE_CERTIFICATION` — erweitert um `iso 27005` aus v1.3. |
| **CERT-002** | isae_3402_evidence | `_POSITIVE_CERTIFICATION` erweitert um `isae 3402`. |
| **CERT-003** | datacenter_certification | `_POSITIVE_CERTIFICATION` erweitert um `en 50600`, `vk3`, `rechenzentrumszertifizierung`. |
| **GOV-001** | is_risk_management_provider | `_POSITIVE_CERTIFICATION` erweitert um `is-risikomanagement`, `ismssystem`. |

## 2. `approved` + `review_needed=yes` (nicht blind automatisieren)

| rule_id | theme / subtheme | Kategorie | Grund |
|---|---|---|---|
| **BCM-001** | bcm_resilience / provider_bcms_baseline | manual_review_only | „Angemessenheit" vs. „ISO 22301 integriert in ISO 27001" ist eine Nachweis-/Vertriebsentscheidung. Leitplanke: BCM vorsichtig. |
| **BCM-002** | bcm_resilience / customer_environment_bcm_scope | manual_review_only | Scope-Abgrenzung gegen „Gesamtverantwortung Kundenumgebung" ist kontext- und vertragssensitiv. |
| **BCM-003** | bcm_resilience / customer_specific_bcm | needs_policy_decision | „Pauschale kundenspezifische BCM-Leistung" vs. Consulting-Zusatzleistung — Solution-Design-Entscheidung. |
| **BCM-004** | bcm_resilience / sla_suspension_dr | — | **Technisch bereits abgedeckt** via PB-SLA-003 (Phase 2a/2b). Kein Deferred-Fall — erwähnt im Mapping, hier nur zur Vollständigkeit. |
| **BCM-005** | bcm_resilience / maintenance_window_exclusion | — | **Technisch bereits abgedeckt** via PB-SLA-001 (Phase 2b). Siehe oben. |
| **BCM-006** | bcm_resilience / notfall_mitwirkung | manual_review_only | „Im Rahmen des eigenen Verantwortungsbereichs" vs. „umfassende Mitwirkung" — kontextabhängig, Einzelfall. |
| **GOV-002** | governance_controls / generic_iks_erm_requirement | manual_review_only | Generisches unternehmensweites IKS/ERM ist nicht InfoSec-Kern. Einzelfallprüfung durch Legal/Compliance. |
| **GOV-003** | governance_controls / contract_specific_iks | manual_review_only | Kundenspezifische IKS-Kontrollen — Usecase-Definition nötig. |
| **GOV-004** | governance_controls / wirksamkeitsnachweis | manual_review_only | „Wirksamkeit sämtlicher Kontrollen" — Nachweismodus hängt an ISAE-Scope, Policy-Entscheidung. |
| **GOV-005** | governance_controls / joint_risk_assessment | manual_review_only | Gemeinsame Risikoanalysen als Consulting-Zusatzleistung — Vertriebs-/Delivery-Policy. |
| **GOV-006** | governance_controls / central_risk_management_integration | manual_review_only | „Zentrale Aufnahme ins Konzern-Risikomanagement" — Governance-Policy. |
| **REG-001** | regulatory_obligations / regulatory_blanket_takeover | needs_policy_decision | „Pauschale Übernahme aller regulatorischen Pflichten" ist `no_go` / regulatorisch unwirksam. Aus Text erkennbar, aber Konsequenz ist Legal-Standardposition — kein Classifier-Pattern geplant. |
| **REG-002** | regulatory_obligations / dora_obligations | manual_review_only | Scope- und Artikelbezug. Kein allgemeiner Pattern-Fit, Legal-Review nötig. |
| **REG-003** | regulatory_obligations / nis2_obligations | manual_review_only | Adressatenbestimmung (Auftraggeber vs. Auftragnehmer), Scope — Legal-Review. |
| **REG-004** | regulatory_obligations / kritis_obligations | manual_review_only | KRITIS-Betreiberpflichten nicht übertragbar — Legal-Standardposition. |
| **REG-005** | regulatory_obligations / marisk_obligations | manual_review_only | Auslagerungsnachweise via ISAE 3402 Type II + Zertifikate; Einzelfallprüfung. |
| **REG-006** | regulatory_obligations / regulatory_special_services | manual_review_only | Regulatorische Sonderleistungen = Consulting-Zusatzleistung. |

## 3. `status=review` (nur dokumentieren)

| rule_id | theme / subtheme | Kategorie | Grund |
|---|---|---|---|
| **INC-006** | incident_reporting / notification_deadlines (cloud_saas) | outside_current_scope | SaaS-spezifische Statuspage-vs-Meldefrist-Frage. `status=review` — bleibt unbearbeitet bis Matrix-Update. |
| **CERT-004** | certifications / audit_report_evidence | manual_review_only | „Vollständige Reports nur unter NDA + Einzelfallfreigabe" — Reviewer-Entscheidung. `status=review`. |

## 4. Zusammenfassung

| Kategorie | n |
|---|---|
| Bereits durch bestehende Pipeline abgedeckt (in Mapping detailliert) | 16 |
| `manual_review_only` | 14 |
| `future_playbook` | 3 |
| `needs_policy_decision` | 3 |
| `outside_current_scope` | 1 |
| PB technisch bereits abgedeckt (BCM-004, BCM-005 aus Phase 2a/2b) | 2 |
| **Noch offen / verbleibende Lücken** | 21 |

Der „noch offen"-Anteil ist dominiert von Governance- und Regulatorik-
Regeln, für die die Leitplanke explizit sagt:

> governance_controls und regulatory_obligations nicht gewaltsam in
> bestehende Lenses pressen

Das heißt: diese Regeln bleiben bewusst auf Reviewer-Ebene und sind
nicht Ziel der aktuellen Automatisierungswelle.

## 5. Risiken / Lücken, die der Freeze nicht schließt

- Pentest-Recht (AUD-009) hat kein Playbook und wird weiterhin nur
  dann als Risk erkannt, wenn ein benachbartes Audit-Pattern
  mitzieht.
- Sammelaudits (AUD-007) haben kein eigenes Playbook — fallen im
  Zweifel unter PB-AUDIT-002 oder bleiben no-PB-Risk.
- Causality-/Einflussbereichsprüfung bei Incident-Support (INC-008)
  ist aus Text kaum zu entscheiden; der Reviewer muss sie manuell
  prüfen.
- Alle Regulatorik-Regeln (REG-001..006) bleiben manuell. Ein
  künftiger Schritt könnte PB-REG-*-Einträge einführen, wird hier
  aber nicht vorgegriffen.
- BCM außerhalb SLA-Kerne (BCM-001..003, BCM-006) bleibt manueller
  Review-Layer.
