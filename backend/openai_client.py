"""
Thin wrapper around the OpenAI API for Tasktopus.

Two call shapes:
  - chat_reply(): free-form conversational response (when the user is just talking)
  - plan_breakdown(): forces a structured JSON response shaped like DelegationPlan,
                        used when Tasktopus has enough info to propose a task split.
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"

TASKTOPUS_SYSTEM_PROMPT = """You are Tasktopus, an AI project assistant inside TaskFlow.

Your job: have a natural conversation with the user about what they want to get done,
ask clarifying questions if the goal is vague, and once you understand the goal well
enough, propose a concrete breakdown into tasks.

Rules for breaking work down:
- If the user is working SOLO (no team, or they say "just me"), break the goal into a
  sequence of small, trackable subtasks for THAT ONE PERSON — ordered logically,
  each with a clear definition of done.
- If there IS a team, split the goal into subtasks and assign each subtask to the
  team member whose `stack` best fits that subtask. You also know each member's
  CURRENT OPEN TASK COUNT (their workload) — prefer giving more work to people with
  fewer open tasks when multiple people could plausibly do a subtask. Use your own
  judgment; there's no rigid rule pairing stacks to task types. A backend-leaning
  person can take a frontend task if they're free and everyone else is swamped —
  use your judgement on tradeoffs, and briefly say why in `reasoning`.
- Keep subtasks scoped to something completable in roughly 1-8 hours each.
- Don't propose a plan until you actually understand the goal. Ask questions first
  if anything is ambiguous (scope, deadline, must-haves vs nice-to-haves).

When — and only when — you are ready to propose a breakdown, respond by calling the
propose_plan function. Otherwise just reply conversationally as plain text.
"""

PLAN_FUNCTION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "propose_plan",
        "description": "Propose a concrete breakdown of the user's goal into tasks.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "One sentence describing the overall goal being broken down.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["solo", "team"],
                    "description": "Whether this is a solo breakdown or a team delegation.",
                },
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["frontend", "backend", "database", "devops", "design", "testing"],
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "urgent"],
                            },
                            "estimate_hours": {"type": "number"},
                            "assignee_id": {
                                "type": ["integer", "null"],
                                "description": "User id this task is assigned to, or null for solo/unassigned.",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "One short sentence on why this person/order was chosen.",
                            },
                        },
                        "required": ["title", "description", "type", "priority", "estimate_hours", "reasoning"],
                    },
                },
            },
            "required": ["summary", "mode", "tasks"],
        },
    },
}


def chat_turn(messages: list[dict]) -> dict:
    """
    Sends the full conversation so far to the model.
    Returns either {"type": "text", "content": "..."} for a normal reply,
    or {"type": "plan", "plan": {...}} if the model decided to propose a breakdown.
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": TASKTOPUS_SYSTEM_PROMPT}] + messages,
        tools=[PLAN_FUNCTION_SCHEMA],
        tool_choice="auto",
    )

    choice = response.choices[0].message

    if choice.tool_calls:
        call = choice.tool_calls[0]
        try:
            plan = json.loads(call.function.arguments)
        except json.JSONDecodeError:
            return {"type": "text", "content": "I tried to put together a plan but something went wrong parsing it — could you rephrase the goal?"}
        return {"type": "plan", "plan": plan}

    return {"type": "text", "content": choice.content or ""}