"""Interaction handlers. One handler per command / component prefix / modal prefix."""

from typing import Any

from discord_core import InteractionContext, Router, responses
from discord_core.interactions import Interaction

router = Router()


@router.command("ping")
async def ping(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Reply with an ephemeral pong."""
    return responses.ephemeral(
        ctx.t("ping.reply", interaction, user=interaction.invoking_user.display_name)
    )
