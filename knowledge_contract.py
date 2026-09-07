"""Versioned behaviour and response identifiers for the knowledge agent."""

from __future__ import annotations

from typing import Final


AGENT_INSTRUCTION_VERSION: Final = "knowledge-agent-v1"
ANSWER_CONTRACT_VERSION: Final = "grounded-answer-v1"
ANSWER_MODE: Final = "extractive"


__all__ = [
    "AGENT_INSTRUCTION_VERSION",
    "ANSWER_CONTRACT_VERSION",
    "ANSWER_MODE",
]
