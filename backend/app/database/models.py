from app.database.base import Base
from app.domains.cases.models import (
    AuditEvent,
    CaseEvent,
    CaseRequirement,
    CaseRuleAssignment,
    CaseStatusHistory,
    ImmigrationCase,
)
from app.domains.documents.models import Document, DocumentCheck, DocumentVersion
from app.domains.identity.models import Actor, ApplicantProfile
from app.domains.institutions.models import Institution, Programme
from app.domains.knowledge.models import (
    ApprovalEvent,
    KnowledgeSource,
    KnowledgeSyncRun,
    Requirement,
    RequirementSource,
    RequirementVersion,
    RuleDefinition,
    RuleRequirement,
    RuleSet,
    RuleSetVersion,
    RuleVersion,
    SourceRevision,
)
from app.domains.student_pass.models import StudentPassCaseProfile
from app.domains.submissions.models import CaseSubmission, SubmissionDocument

__all__ = [
    "Actor",
    "ApplicantProfile",
    "ApprovalEvent",
    "AuditEvent",
    "Base",
    "CaseEvent",
    "CaseRequirement",
    "CaseRuleAssignment",
    "CaseSubmission",
    "CaseStatusHistory",
    "Document",
    "DocumentCheck",
    "DocumentVersion",
    "ImmigrationCase",
    "Institution",
    "KnowledgeSource",
    "KnowledgeSyncRun",
    "Programme",
    "Requirement",
    "RequirementSource",
    "RequirementVersion",
    "RuleDefinition",
    "RuleRequirement",
    "RuleSet",
    "RuleSetVersion",
    "RuleVersion",
    "SourceRevision",
    "StudentPassCaseProfile",
    "SubmissionDocument",
]
