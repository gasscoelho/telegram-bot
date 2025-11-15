"""Natural language command interpreter for Last War bot using LLM and LangGraph."""

from __future__ import annotations

from datetime import timedelta
from typing import Literal

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field, SecretStr

from src.config import config

from ..models import Kind


class ParsedCommand(BaseModel):
    """Structured command parsed from natural language input."""

    kind: Kind | None = Field(
        default=None,
        description="Task type, or null if it cannot be determined.",
    )
    task_name: str = Field(
        description="Human-readable task name extracted from the message.",
    )
    days: int = Field(default=0, ge=0)
    hours: int = Field(default=0, ge=0)
    minutes: int = Field(default=0, ge=0)
    language: Literal["pt", "en"] | None = Field(
        default=None,
        description="Detected language: 'pt' for Portuguese, 'en' for English.",
    )

    def to_timedelta(self) -> timedelta:
        """Convert parsed time components to timedelta."""
        return timedelta(days=self.days, hours=self.hours, minutes=self.minutes)

    def is_zero(self) -> bool:
        """Check if the duration is zero."""
        return self.days == 0 and self.hours == 0 and self.minutes == 0


class NLState(BaseModel):
    """LangGraph state for natural-language interpretation."""

    text: str
    parsed: ParsedCommand | None = None
    error: str | None = None
    attempts: int = 0


# ---------- LLM setup ----------


def _build_llm() -> ChatOpenAI:
    """Build OpenAI LLM client."""
    model = config.OPENAI_MODEL
    key = config.OPENAI_API_KEY
    return ChatOpenAI(
        model=model,
        temperature=0.0,
        api_key=SecretStr(key),
    )


SYSTEM_PROMPT = """
You are a command interpreter for a Telegram reminder bot for the mobile game "Last War".

Your job is to read a user message (in Portuguese or English) and extract a structured reminder command.

The bot supports these task kinds (internal values):
- "truck"    → references to supply trucks, convoys, vehicle arrivals, 'caminhão'
- "build"    → building or construction finishing, upgrades, 'construção'
- "research" → research tasks or lab upgrades, 'pesquisa'
- "train"    → troop training, 'treinar', 'treino'
- "ministry" → ministry / HQ / special building timers, 'ministério'
- "custom"   → any other task not clearly in the above categories

You must always output a JSON object that matches the ParsedCommand schema:
- kind: one of "truck", "build", "research", "train", "ministry", "custom", or null
- task_name: short label for the task in the user's own words
- days: non-negative integer
- hours: non-negative integer
- minutes: non-negative integer
- language: "pt" for Portuguese, "en" for English, or null if unsure

INTERPRETATION RULES:

- Focus on how long from NOW until the reminder fires.
  Examples:
    - "in 30 minutes" → 0 days, 0 hours, 30 minutes
    - "em 1 dia e 4 horas" → 1 day, 4 hours, 0 minutes
    - "em 90 minutos" → 0 days, 1 hour, 30 minutes
- Ignore seconds.
- Never produce negative durations.
- If the total duration is effectively zero, set all components to 0.

- Detect the task kind:
    - If the message clearly mentions truck / caminhão / convoy → "truck"
    - If it's about construction / prédios / build / upgrade → "build"
    - If it's about research / laboratório → "research"
    - If it's about training troops → "train"
    - If it's about ministry / HQ-like building → "ministry"
    - Otherwise use "custom"

- task_name should be a concise label for what the user cares about, e.g.:
    - "truck arrival"
    - "caminhão"
    - "castle build"
    - "pesquisa de tecnologia"

LANGUAGE:
- language = "pt" if the message is mainly Portuguese.
- language = "en" if it is mainly English.
"""

_llm = _build_llm()
_structured_llm = _llm.with_structured_output(ParsedCommand)

# ---------- Graph nodes ----------


async def interpret_node(state: NLState) -> NLState:
    """Call the LLM with structured output to interpret the user's text."""
    raw = await _structured_llm.ainvoke(
        [
            ("system", SYSTEM_PROMPT),
            ("user", state.text),
        ]
    )
    state.parsed = ParsedCommand.model_validate(raw)
    state.attempts += 1
    state.error = None
    return state


def validate_node(state: NLState) -> NLState:
    """Validate and normalize the parsed command."""
    if state.parsed is None:
        state.error = "no_parsed_command"
        return state

    if state.parsed.is_zero():
        state.error = "zero_duration"
        return state

    # Additional sanity checks could be added here if needed
    state.error = None
    return state


# ---------- Graph compilation ----------


def _build_graph():
    """Build the LangGraph workflow for NL interpretation."""
    workflow = StateGraph(NLState)
    workflow.add_node("interpret", interpret_node)
    workflow.add_node("validate", validate_node)
    workflow.set_entry_point("interpret")
    workflow.add_edge("interpret", "validate")

    def route_after_validate(state: NLState) -> str:
        if state.error is None:
            return "ok"
        if state.attempts < 2:
            return "retry"
        return "fail"

    workflow.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "ok": END,
            "retry": "interpret",
            "fail": END,
        },
    )
    return workflow.compile()


_nl_graph = _build_graph()


# ---------- Public entrypoint used by Telegram handlers ----------


async def interpret_natural_command(text: str) -> ParsedCommand | None:
    """
    Takes a free-form user message (PT or EN),
    runs it through the LangGraph workflow,
    and returns a ParsedCommand if successful, otherwise None.
    """
    initial = NLState(text=text)
    raw_state = await _nl_graph.ainvoke(initial)
    final_state = NLState.model_validate(raw_state)

    if final_state.parsed and not final_state.parsed.is_zero():
        return final_state.parsed

    return None
