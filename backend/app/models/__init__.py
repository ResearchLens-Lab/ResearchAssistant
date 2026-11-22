"""SQLAlchemy ORM models. Importing this package registers all tables on Base.metadata."""

from backend.app.models.conversation import Conversation
from backend.app.models.document import Document, DocumentStatus
from backend.app.models.message import Message, MessageRole
from backend.app.models.paper import Paper, ComparisonRecord
from backend.app.models.refresh_token import RefreshToken
from backend.app.models.user import User
from backend.app.models.knowledge_graph import (
    KGGraphCandidate, KGGraphEvidence, KGIdentityDecision, KGImportRun,
    KGNode, KGNodeAlias, KGRelationship, KGReviewEvent,
)
from backend.app.models.research_memory import (
    MemoryAssociation, MemoryContradiction, MemoryGraphReference,
    MemoryObservationEvent, MemoryProcessingRun, MemoryRecord,
    MemoryResearchGap, MemoryReviewEvent, MemorySessionOptIn,
    MemorySourceEvidence,
)
from backend.app.models.research_intelligence import (
    ResearchClaimAssessment, ResearchIntelligenceRun, ResearchSourceQualityReview,
)

__all__ = [
    "Conversation",
    "Document",
    "DocumentStatus",
    "Message",
    "MessageRole",
    "Paper",
    "ComparisonRecord",
    "RefreshToken",
    "User",
    "KGGraphCandidate", "KGGraphEvidence", "KGIdentityDecision", "KGImportRun",
    "KGNode", "KGNodeAlias", "KGRelationship", "KGReviewEvent",
    "MemoryAssociation", "MemoryContradiction", "MemoryGraphReference",
    "MemoryObservationEvent", "MemoryProcessingRun", "MemoryRecord",
    "MemoryResearchGap", "MemoryReviewEvent", "MemorySessionOptIn",
    "MemorySourceEvidence",
    "ResearchClaimAssessment", "ResearchIntelligenceRun", "ResearchSourceQualityReview",
]
