"""JSON schemas for Structured Outputs: obligation extraction, relations, cross-theme."""

OBLIGATION_SCHEMA = {
    "name": "obligations_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "obligations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "obligation_text": {"type": "string"},
                        "obligation_type": {
                            "type": "string",
                            "enum": [
                                "obligation", "right", "restriction",
                                "representation", "condition",
                                "approval_requirement", "notification_requirement",
                            ],
                        },
                        "modality": {
                            "type": "string",
                            "enum": [
                                "must", "shall", "may", "is_entitled_to",
                                "is_prohibited_from", "should",
                            ],
                        },
                        "obligated_party": {
                            "type": "string",
                            "enum": ["provider", "client", "both", "unclear"],
                        },
                        "beneficiary": {
                            "type": "string",
                            "enum": [
                                "client", "provider", "client_end_customer",
                                "third_party", "regulator", "unclear",
                            ],
                        },
                        "trigger": {"type": ["string", "null"]},
                        "scope": {"type": ["string", "null"]},
                        "condition_precedent": {"type": ["string", "null"]},
                        "carve_outs": {"type": "array", "items": {"type": "string"}},
                        "limits": {
                            "type": "object",
                            "properties": {
                                "frequency_limit": {"type": ["string", "null"]},
                                "time_limit": {"type": ["string", "null"]},
                                "scope_limit": {"type": ["string", "null"]},
                                "cost_limit": {"type": ["string", "null"]},
                                "access_limit": {"type": ["string", "null"]},
                            },
                            "required": [
                                "frequency_limit", "time_limit", "scope_limit",
                                "cost_limit", "access_limit",
                            ],
                            "additionalProperties": False,
                        },
                        "time_constraint": {
                            "type": ["object", "null"],
                            "properties": {
                                "type": {"type": "string"},
                                "value": {"type": "string"},
                                "normalized_hours": {"type": ["number", "null"]},
                                "is_explicit": {"type": "boolean"},
                            },
                        },
                        "evidence_segment_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": [
                        "obligation_text", "obligation_type", "modality",
                        "obligated_party", "beneficiary", "trigger", "scope",
                        "condition_precedent", "carve_outs", "limits",
                        "time_constraint", "evidence_segment_ids", "confidence",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["obligations"],
        "additionalProperties": False,
    },
}


RELATION_SCHEMA = {
    "name": "obligation_relations",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_obligation_id": {"type": "string"},
                        "target_obligation_id": {"type": "string"},
                        "relation_type": {
                            "type": "string",
                            "enum": ["contradicts", "supplements", "overrides", "duplicates"],
                        },
                        "rationale": {"type": "string"},
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": [
                        "source_obligation_id", "target_obligation_id",
                        "relation_type", "rationale", "confidence",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["relations"],
        "additionalProperties": False,
    },
}


CROSS_THEME_SCHEMA = {
    "name": "cross_theme_check",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "result": {
                "type": "string",
                "enum": ["conflict_found", "no_conflict", "unclear"],
            },
            "rationale": {"type": "string"},
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "involved_obligation_ids_a": {
                "type": "array",
                "items": {"type": "string"},
            },
            "involved_obligation_ids_b": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "result", "rationale", "confidence",
            "involved_obligation_ids_a", "involved_obligation_ids_b",
        ],
        "additionalProperties": False,
    },
}
