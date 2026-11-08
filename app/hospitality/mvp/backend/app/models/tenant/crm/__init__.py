"""Tenant database — L. CRM, messaging & reputation."""

from app.models.tenant.crm.automation import (
    Automation,
    AutomationCreate,
    AutomationRead,
    AutomationUpdate,
)
from app.models.tenant.crm.campaign import Campaign, CampaignCreate, CampaignRead, CampaignUpdate
from app.models.tenant.crm.conversation import (
    Conversation,
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
)
from app.models.tenant.crm.guest_feedback import (
    GuestFeedback,
    GuestFeedbackCreate,
    GuestFeedbackRead,
    GuestFeedbackUpdate,
)
from app.models.tenant.crm.guest_segment import (
    GuestSegment,
    GuestSegmentCreate,
    GuestSegmentRead,
    GuestSegmentUpdate,
)
from app.models.tenant.crm.message import Message, MessageCreate, MessageRead, MessageUpdate
from app.models.tenant.crm.message_template import (
    MessageTemplate,
    MessageTemplateCreate,
    MessageTemplateRead,
    MessageTemplateUpdate,
)
from app.models.tenant.crm.messaging_account import (
    MessagingAccount,
    MessagingAccountCreate,
    MessagingAccountRead,
    MessagingAccountUpdate,
)
from app.models.tenant.crm.review import Review, ReviewCreate, ReviewRead, ReviewUpdate
from app.models.tenant.crm.scheduled_message import (
    ScheduledMessage,
    ScheduledMessageCreate,
    ScheduledMessageRead,
    ScheduledMessageUpdate,
)
from app.models.tenant.crm.survey_response import (
    SurveyResponse,
    SurveyResponseCreate,
    SurveyResponseRead,
    SurveyResponseUpdate,
)

__all__ = [
    "MessagingAccount",
    "MessagingAccountCreate",
    "MessagingAccountRead",
    "MessagingAccountUpdate",
    "MessageTemplate",
    "MessageTemplateCreate",
    "MessageTemplateRead",
    "MessageTemplateUpdate",
    "Conversation",
    "ConversationCreate",
    "ConversationRead",
    "ConversationUpdate",
    "Message",
    "MessageCreate",
    "MessageRead",
    "MessageUpdate",
    "GuestSegment",
    "GuestSegmentCreate",
    "GuestSegmentRead",
    "GuestSegmentUpdate",
    "Campaign",
    "CampaignCreate",
    "CampaignRead",
    "CampaignUpdate",
    "Automation",
    "AutomationCreate",
    "AutomationRead",
    "AutomationUpdate",
    "ScheduledMessage",
    "ScheduledMessageCreate",
    "ScheduledMessageRead",
    "ScheduledMessageUpdate",
    "Review",
    "ReviewCreate",
    "ReviewRead",
    "ReviewUpdate",
    "SurveyResponse",
    "SurveyResponseCreate",
    "SurveyResponseRead",
    "SurveyResponseUpdate",
    "GuestFeedback",
    "GuestFeedbackCreate",
    "GuestFeedbackRead",
    "GuestFeedbackUpdate",
]
