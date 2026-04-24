# Matrix v1.3 — Deferred Rules

**Quelle:** `docs/InfoSec_ContractReview_Master_Matrix_v1_3.csv` (44 Regeln)
**Mapping-Referenz:** `docs/Matrix_v1_3_to_System_Mapping.md`

Liste aller rule_ids, die im aktuellen Matrix-v1.3-Integrationsschritt
**nicht** technisch übernommen wurden. Jede rule_id kommt genau
einmal vor und hat genau eine Kategorie.

## Kategorien

| Kategorie | Bedeutung |
|---|---|
| `manual_review_only` | Entscheidung nicht zuverlässig aus Klauseltext ableitbar; Reviewer-/Legal-/Policy-Arbeit. |
| `future_playbook` | Eigenes Risikomuster, das einen neuen Playbook-Eintrag erfordern würde. |
| `future_lens` | Bräuchte eine eigene, aktuell nicht vorhandene Lens (z. B. LENS-GOV, LENS-REG). |
| `outside_current_scope` | Themenfeld bewusst außerhalb PoC-Scope. |
| `needs_policy_decision` | Fachliche Policy-/Schwellwertentscheidung vor Automatisierung nötig. |

## Deferred rule_ids (26 von 44)

### manual_review_only (10)

| rule_id | theme / subtheme | Grund |
|---|---|---|
| AUD-006 | audit_rights / regulatory_audit_carveout | Regulatorischer Audit-Carveout ist Legal-Einzelfallentscheidung. |
| INC-008 | incident_reporting / incident_support_model | Kausalitäts-/Einflussbereichsprüfung aus Text nicht robust ableitbar. |
| INC-009 | incident_reporting / incident_information_disclosure | Scope-Diskriminierung („alle Informationen" vs. „insoweit erforderlich") braucht Kontext. |
| CERT-004 | certifications / audit_report_evidence | `status=review`. NDA-/Einzelfallfreigabe für Vollberichte. |
| CERT-005 | certifications / evidence_obligations | „Sämtliche Policies auf Verlangen" vs. „SoA-Extrakt/Executive-Summary" — Kontextbewertung. |
| GOV-005 | governance_controls / joint_risk_assessment | Gemeinsame Risikobewertung als Consulting-Zusatzleistung — Solution-Design-Policy. |
| GOV-007 | governance_controls / back_to_back_certification_reliance | Eignungsleihe + Back-to-back-Kopplung ist primär Legal/Compliance. |
| BCM-001 | bcm_resilience / provider_bcms_baseline | Nachweis-/Vertriebsentscheidung („ISO 22301 als Modul der ISO 27001"). |
| BCM-002 | bcm_resilience / customer_environment_bcm_scope | Scope-Abgrenzung gegen Kundenumgebung — kontextsensitiv. |
| BCM-006 | bcm_resilience / notfall_mitwirkung | Notfallmitwirkung im eigenen Verantwortungsbereich — Einzelfall. |

### future_playbook (3)

| rule_id | theme / subtheme | Grund |
|---|---|---|
| AUD-007 | audit_rights / pooled_multi_customer_audit | Sammel-/Verbundaudit ist eigenes Risikomuster ohne Playbook-Eintrag. |
| AUD-009 | audit_rights / pentest_rights | Pentest/Vulnerability-Scan/Red-Team hat keinen Playbook-Eintrag (CSV-Notiz bestätigt die Lücke). |
| INC-007 | incident_reporting / event_threshold (security_service) | SIEM-/SOC-spezifisches Muster — eigenes Risikomuster, kein Playbook. |

### future_lens (9)

| rule_id | theme / subtheme | Grund |
|---|---|---|
| GOV-002 | governance_controls / generic_iks_erm_requirement | Bräuchte Governance-Lens (LENS-GOV); bewusst nicht in LENS-AUDIT/INC/SLA pressen. |
| GOV-003 | governance_controls / contract_specific_iks | Vertragsspezifisches IKS ohne Lens-Fit. |
| GOV-004 | governance_controls / wirksamkeitsnachweis | Wirksamkeitsnachweis über Kontrollen — ohne Governance-Lens nicht robust. |
| GOV-006 | governance_controls / central_risk_management_integration | Zentrale Risikomanagement-Integration benötigt Governance-Lens. |
| REG-002 | regulatory_obligations / dora_obligations | DORA-Artikelbezug bräuchte Regulatorik-Lens (LENS-REG). |
| REG-003 | regulatory_obligations / nis2_obligations | NIS2-Adressatenbestimmung bräuchte Regulatorik-Lens. |
| REG-004 | regulatory_obligations / kritis_obligations | KRITIS-Betreiberpflichten bräuchten Regulatorik-Lens. |
| REG-005 | regulatory_obligations / marisk_obligations | MaRisk AT 9 — Regulatorik-Lens. |
| REG-006 | regulatory_obligations / regulatory_special_services | Regulatorische Sonderleistungen — Regulatorik-Lens. |

### needs_policy_decision (3)

| rule_id | theme / subtheme | Grund |
|---|---|---|
| AUD-005 | audit_rights / audit_effort_cap_customer | 50-PT-Schwellwert ist Vorstandspolicy; Entscheidung hängt an Gesamtaufwand, nicht am Einzeltext. |
| BCM-003 | bcm_resilience / customer_specific_bcm | Kundenspezifisches BCM als Consulting-Zusatzleistung — Solution-Design-Policy. |
| REG-001 | regulatory_obligations / regulatory_blanket_takeover | Pauschale regulatorische Übernahme ist `no_go` / Legal-Standardposition. |

### outside_current_scope (1)

| rule_id | theme / subtheme | Grund |
|---|---|---|
| INC-006 | incident_reporting / notification_deadlines (cloud_saas) | `status=review`. SaaS-Statuspage-Thematik bleibt bis Matrix-Update außen vor. |

## Summenkontrolle

| Gruppe | n |
|---|---|
| `manual_review_only` | 10 |
| `future_playbook` | 3 |
| `future_lens` | 9 |
| `outside_current_scope` | 1 |
| `needs_policy_decision` | 3 |
| **Deferred total** | **26** |
| Technisch übernommen (siehe Mapping-Doc) | 18 |
| **Summe == Total rule_ids in CSV** | **44** ✓ |

Jede deferred rule_id kommt in genau einer Kategorie vor; keine
Doppel-, keine Mehrfachzählung. Die Abdeckung ist lückenlos gegen die
44 Regeln der CSV.
