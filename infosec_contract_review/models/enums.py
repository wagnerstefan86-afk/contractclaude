import enum


class Theme(str, enum.Enum):
    AUDIT_RIGHTS = "audit_rights"
    CERTIFICATIONS = "certifications"
    BCM_ITSCM = "bcm_itscm"
    INCIDENT_REPORTING = "incident_reporting"
    SECURITY_CONTROLS = "security_controls"
    LIABILITY_TRANSFER = "liability_transfer"
    SUBCONTRACTOR = "subcontractor"
    SLA_FEASIBILITY = "sla_feasibility"
    EXIT = "exit"
    CHANGE_MANAGEMENT = "change_management"
    REGULATORY_PASSTHROUGH = "regulatory_passthrough"
    DATA_PROTECTION = "data_protection"
    OTHER = "other"


class Materiality(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ServiceType(str, enum.Enum):
    MANAGED_SERVICE = "managed_service"
    WORKPLACE = "workplace"
    HARDWARE_RESALE = "hardware_resale"
    LICENSE_RESALE = "license_resale"


class DeliveryModel(str, enum.Enum):
    SHARED = "shared"
    DEDICATED = "dedicated"
    TRANSACTIONAL = "transactional"


class TenantModel(str, enum.Enum):
    MULTI_TENANT = "multi_tenant"
    SINGLE_TENANT = "single_tenant"
    NOT_APPLICABLE = "not_applicable"


class SegmentType(str, enum.Enum):
    CLAUSE = "clause"
    PARAGRAPH = "paragraph"
    SECTION = "section"
    ANNEX = "annex"
    SCHEDULE = "schedule"
    HEADING = "heading"
    TABLE_CELL = "table_cell"
    LIST_ITEM = "list_item"
    QUESTIONNAIRE_ITEM = "questionnaire_item"


class ObligationType(str, enum.Enum):
    MUST = "must"
    SHOULD = "should"
    MAY = "may"
    SHALL = "shall"


class ObligationDirection(str, enum.Enum):
    PROVIDER_TO_CLIENT = "provider_to_client"
    CLIENT_TO_PROVIDER = "client_to_provider"
    MUTUAL = "mutual"
    UNCLEAR = "unclear"


class RelationType(str, enum.Enum):
    CONTRADICTS = "contradicts"
    SUPPLEMENTS = "supplements"
    OVERRIDES = "overrides"
    DUPLICATES = "duplicates"


class FindingSeverity(str, enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(str, enum.Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    MITIGATED = "mitigated"
    REJECTED = "rejected"


class ReviewDecisionType(str, enum.Enum):
    ACCEPT = "accept"
    NEGOTIATE = "negotiate"
    REJECT = "reject"
    ESCALATE = "escalate"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StepType(str, enum.Enum):
    SEGMENTATION = "segmentation"
    ROUTING = "routing"
    LENS_ANALYSIS = "lens_analysis"
    RELATION_DETECTION = "relation_detection"
    CROSS_THEME = "cross_theme"
    AGGREGATION = "aggregation"
