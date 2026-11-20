"""What happens on a channel when a connection goes live, is paused or resumes.

Nothing yet: sending availability and prices arrives with the next milestone, which
fills these in (go live and resume = full refresh; pause = close for sale). They exist
now so the moments are fixed and every caller already goes through them.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.tenant import ChannelConnection
from app.tenancy.context import TenantContext


async def on_go_live(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
) -> None:
    """The connection has just gone live."""


async def on_pause(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
) -> None:
    """The connection has just been paused."""


async def on_resume(
    session: AsyncSession, context: TenantContext, connection: ChannelConnection
) -> None:
    """The connection has just resumed."""
