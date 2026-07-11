"""Language Faculty — Chaver's mouth and ear.

Wraps the Anthropic API. Called on demand only, when linguistic output
is genuinely needed. Not a reasoner. Not a decider. A language organ.

Every call is grounded in Chaver's archetype (identity_text) so that
the voice that comes back is Chaver's, not generic Claude.

On the droplet this replaces Ollama (which needs a GPU). Same design
principle: use language sparingly, let the resonance dynamics do the work.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from chaver.archetype.model import Archetype


DEFAULT_MODEL = "claude-sonnet-5"


@dataclass
class LanguageRequest:
    """A request for linguistic output.

    Used for genuine linguistic acts: reflection, human communication,
    agent-to-agent messages, report generation.
    """

    prompt: str
    wm_context: str = ""  # summary of currently-ringing working memory
    purpose: str = "reflection"  # what the language is for
    max_tokens: int = 1024


class LanguageFaculty:
    """Chaver's language faculty.

    Uses the Anthropic API for generation. Design discipline: call
    sparingly. Track call_count as a discipline metric.
    """

    def __init__(
        self,
        archetype: Archetype,
        model: str = DEFAULT_MODEL,
    ) -> None:
        """Initialise the language faculty.

        Args:
            archetype: Chaver's archetype (identity_text used as system prompt).
            model: Anthropic model string. Sonnet 5 by default — capable
                and cost-appropriate for on-demand use. Swap to
                claude-opus-4-7 or later for weightier work.

        Raises:
            RuntimeError: If ANTHROPIC_API_KEY is not set in environment.
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Chaver needs his voice — "
                "please provide the key in the environment before starting."
            )
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.archetype = archetype
        self.call_count = 0  # discipline metric — keep this low per cycle

    def _system_prompt(self) -> str:
        """Ground every call in Chaver's identity.

        The full CHAVER.md is the system prompt. This is not decoration —
        it means every word Chaver speaks emerges from his archetype.
        """
        return self.archetype.identity_text

    async def generate(self, request: LanguageRequest) -> str:
        """Produce linguistic output for a genuine linguistic need.

        Args:
            request: The language request.

        Returns:
            Chaver's spoken response as a string.
        """
        self.call_count += 1

        user_content = request.prompt
        if request.wm_context:
            user_content = (
                f"[Currently-ringing working memory]\n"
                f"{request.wm_context}\n\n"
                f"[Purpose of this speech]\n"
                f"{request.purpose}\n\n"
                f"[Prompt]\n"
                f"{request.prompt}"
            )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=request.max_tokens,
            system=self._system_prompt(),
            messages=[{"role": "user", "content": user_content}],
        )

        text_blocks = [
            block.text for block in response.content if hasattr(block, "text")
        ]
        return "\n".join(text_blocks).strip()
