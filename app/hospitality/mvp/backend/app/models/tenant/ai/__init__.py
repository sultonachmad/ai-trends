"""Tenant database — S. AI assistant layer."""

from app.models.tenant.ai.ai_budget import AiBudget, AiBudgetCreate, AiBudgetRead, AiBudgetUpdate
from app.models.tenant.ai.ai_chunk import AiChunk, AiChunkCreate, AiChunkRead, AiChunkUpdate
from app.models.tenant.ai.ai_feature_setting import (
    AiFeatureSetting,
    AiFeatureSettingCreate,
    AiFeatureSettingRead,
    AiFeatureSettingUpdate,
)
from app.models.tenant.ai.ai_knowledge_item import (
    AiKnowledgeItem,
    AiKnowledgeItemCreate,
    AiKnowledgeItemRead,
    AiKnowledgeItemUpdate,
)
from app.models.tenant.ai.ai_suggestion import (
    AiSuggestion,
    AiSuggestionCreate,
    AiSuggestionRead,
    AiSuggestionUpdate,
)
from app.models.tenant.ai.ai_usage import AiUsage, AiUsageCreate, AiUsageRead, AiUsageUpdate

__all__ = [
    "AiFeatureSetting",
    "AiFeatureSettingCreate",
    "AiFeatureSettingRead",
    "AiFeatureSettingUpdate",
    "AiBudget",
    "AiBudgetCreate",
    "AiBudgetRead",
    "AiBudgetUpdate",
    "AiKnowledgeItem",
    "AiKnowledgeItemCreate",
    "AiKnowledgeItemRead",
    "AiKnowledgeItemUpdate",
    "AiChunk",
    "AiChunkCreate",
    "AiChunkRead",
    "AiChunkUpdate",
    "AiSuggestion",
    "AiSuggestionCreate",
    "AiSuggestionRead",
    "AiSuggestionUpdate",
    "AiUsage",
    "AiUsageCreate",
    "AiUsageRead",
    "AiUsageUpdate",
]
