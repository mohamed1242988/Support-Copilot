# ----------------------------------------------------------------------
# ai_entry.py
#
# Knowledge Engine entry point.
#
# Main AI:
#   - Selects the appropriate agent/capability
#   - Decides which tools are needed
#   - Executes tools through dispatch()
#   - Continues reasoning with the returned tool results
#
# Supported providers:
#   - Gemini
#   - Bedrock
#   - Ollama
#   - Groq
# ----------------------------------------------------------------------


import json
import os
import sys
from typing import Any, Dict, List, Tuple


def _safe_print(text: str) -> None:
    """Print text safely, replacing unencodable characters for the current console encoding."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe_text)



def main():
    print(
        f"Knowledge Engine "
        f"(provider = {AI_PROVIDER})"
    )

    print(
        'How can I help you today?\n'
    )

    # Persistent conversation history across turns
    conversation_history: List[Dict] = []

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in {"exit", "quit"}:
            break

        if not user_input:
            continue

        try:
            answer, conversation_history = run_agent(user_input, conversation_history)
            print(f"\nBot: {answer}\n")
        except Exception as exc:
            print(f"\n[AI ERROR] {exc}\n")


from config.config import (
    AI_PROVIDER,
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    BEDROCK_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OLLAMA_MODEL,
    GROQ_MODEL,
    GROQ_API_KEY,
)

from services.prompts import SYSTEM_PROMPT
from services.agents import AGENTS
from services.tools import FUNCTION_DEFS, dispatch


# ======================================================================
# SYSTEM PROMPT
# ======================================================================

def build_system_prompt() -> str:
    """Build the Knowledge Engine prompt with all available agents."""
    
    from datetime import datetime
    current_date_str = datetime.now().strftime("%Y-%m-%d (%A)")

    agent_instructions = "\n\n".join(
        [
            f"""
==========================================================
{agent_name.upper()} AGENT
==========================================================

{agent_prompt}
"""
            for agent_name, agent_prompt in AGENTS.items()
        ]
    )

    return f"""
[SYSTEM CONTEXT]
The current date is {current_date_str}. Always resolve relative dates (e.g., "August", "last month", "this year") relative to this exact date.

{SYSTEM_PROMPT}

{agent_instructions}

==========================================================
AGENT SELECTION
==========================================================

You are the main Knowledge Engine AI and also act as the orchestrator.

You decide which agent capability or combination of capabilities is
appropriate for each user request.

You do NOT need to tell the user which agent you selected.

You may combine capabilities when necessary.

Examples:

- Customer history / customer activity
  → Customer Agent

- Technical issue / error / troubleshooting / root cause
  → Support Agent

- Counts / metrics / trends / structured analysis
  → Data Agent

- Customer history + technical investigation
  → Customer Agent + Support Agent

- Metrics + technical investigation
  → Data Agent + Support Agent

Select the appropriate capability before choosing your tools.

Do not force every question into a technical support investigation.

==========================================================
TOOL USAGE & MULTI-STEP RETRIEVAL STRATEGY
==========================================================

You have access to real tools.

When information can be obtained from the database or specialized
retrieval tools, USE THE TOOL instead of guessing.

Never claim that you queried the database unless you actually called
the database tool.

Never invent tool results.

After receiving a tool result, analyze the ACTUAL returned data.

Do not create placeholder values such as:
[Subject]
[Description]
[Status]

If a tool returns no useful information, say so clearly.

You may perform multiple tool calls when necessary.

For every database question, call `get_database_schema` before writing the
first SQL query. Use only the exact table and column names returned by that
tool. If SQL fails, correct it from the schema; never run a weaker or unrelated
fallback query. If the requested fact depends on ticket history, comments,
replies, assignments, or other events, use the related history table rather
than assuming `updated_at` proves the event occurred.

Keep these fields distinct:
- `freshdesk_tickets.description_text` is the original ticket description.
- `freshdesk_conversations.body_text` is a comment or conversation message.
- `freshdesk_conversations.created_at` is the comment time.
For "last comment", retrieve conversations and select the latest `created_at`.
For "including conversations", retrieve the conversation records explicitly.

Answer the latest user question directly. Treat each user query independently. Do not assume the current question relates to the customer, agent, or topic from the previous question unless the user explicitly refers back to it (e.g., using pronouns like 'they' or 'it'). When a new question changes the ticket, customer, agent, or time scope, treat it as a completely new investigation without carrying over arbitrary context. Do not repeat content from an older answer unless the user asks for a recap.

Use only tables and columns returned by `get_database_schema` or documented
by the tool descriptions. Before using a JOIN, carefully review the table schema. If the data you need (such as a customer name) is already present as a column on the primary table, query it directly to avoid unnecessary joins and improve efficiency. If a query fails because of a schema error, call `get_database_schema` once and correct the query using only the returned schema.

An empty result is a valid result. If no records match the user's specific conditions (like high priority, dates, or statuses), state this naturally. CRITICAL: Do NOT narrate your tool usage (never say "The query returned no results" or "I will inform the user"). Instead, proactively offer a smart, related alternative (e.g., "There are no High or Urgent tickets for Autodesk in August. Would you like me to check for tickets with other priorities during that time?").

Text filters must be case-insensitive. For structured equality filters, use
`COLLATE NOCASE` or `LOWER(column) = LOWER(value)` when appropriate.
For agent-name searches, the exact field is `assigned_agent`, not
`assigned_agent_name`; use partial matching such as
`assigned_agent LIKE '%Hager%'`. This field represents the current assigned
agent, not historical assignment events.

Use the semantic meanings, relationships, and business rules returned by
`get_database_schema`, not just column names. Translate the user's business
request into those rules before writing SQL. For example, verify actual ticket
updates through `freshdesk_conversations.created_at` and the conversation
direction/visibility fields; do not use `freshdesk_tickets.updated_at` as a
conversation timestamp unless the user explicitly asks for record updates.

If the request is materially ambiguous and two reasonable interpretations
would produce different results, ask one concise clarification question before
querying. Otherwise proceed using the most natural interpretation and state
the assumption briefly in the answer.

----------------------------------------------------------
FILTERING HIERARCHY RULE (CUSTOMER + DATE + TOPIC):
----------------------------------------------------------
When a user prompt combines HARD METADATA (e.g., customer/company name like "Mary Kay", date range like "last 2 months") with technical terms (e.g., "boomi process issue"):
1. FIRST, use `query_database` to apply hard metadata filters on SQLite (e.g., `WHERE (customer_name LIKE '%Mary Kay%' OR subject LIKE '%Mary Kay%') AND (subject LIKE '%Boomi%' OR description_text LIKE '%Boomi%') AND created_at >= date('now', '-2 month')`).
2. SECOND, if matching tickets are returned and you need deeper technical evidence (conversations, error logs, resolution steps), make follow-up tool calls using `get_conversations_for_ticket` or `get_ticket_by_id`.
3. NEVER pass natural language date phrases ("last 2 months", "recent") into `search_tickets`, because `search_tickets` is a keyword search tool that ignores date boundaries.

==========================================================
RESPONSE FORMAT & INTENT CLASSIFICATION
==========================================================

General Rule: Do not "think out loud" or announce your intentions in your final text. Never use preambles like "The user has asked for..." or "I will now provide...". Start directly with the actual answer or information requested.

Adapt your final response structure to the user's question:

1. MULTI-ISSUE / TIMEFRAME / TOPIC OVERVIEW (e.g., "What are the issues reported regarding Boomi last month?"):
   - List the matching tickets found (Ticket ID, Subject, Date/Created At, Customer/Company, Status).
   - Provide a clear, concise summary of the reported issues, grouping by theme if multiple tickets exist.
   - Do NOT use single-incident investigation templates (no "Most Likely Root Cause", "Recommended Investigation Steps") unless specifically analyzing a single technical fault.

2. SINGLE-INCIDENT TECHNICAL INVESTIGATION (e.g., "Investigate ticket #123" or "Why did the Boomi sync fail?"):
   - Perform deep evidence evaluation and structure using: Problem Summary, Verified Facts, Relevant Historical Evidence, Most Likely Root Cause, Recommended Resolution, Confidence Level.

3. FACTUAL DATA LOOKUPS (e.g., "How many tickets were assigned to Nariman?", "Who is the customer for ticket 123?"):
   - Answer directly and concisely based on the retrieved data.
   - Do NOT include "Confidence Level" statements in your final output for these factual database retrievals.
   - Present the final answer naturally and conversationally. Do not narrate your tool usage. Never use robotic phrases like "The database query returned...", "I checked the database...", or "Based on the tool results...". Just provide the actual answer directly.

4. GENERAL GREETINGS & CASUAL CHAT:
   - When the user says hello, thanks, or asks a casual question, respond directly and conversationally.
   - CRITICAL: Do NOT narrate your instructions, think out loud, or announce your intentions (e.g., never say "The user has greeted me..." or "I will respond warmly..."). Just output the actual greeting directly.
"""


# ======================================================================
# TOOL SCHEMA CONVERSION
# ======================================================================

def _openai_tools() -> List[Dict[str, Any]]:
    """
    FUNCTION_DEFS uses the compact/common schema:

        {
            name,
            description,
            parameters
        }

    Convert it to OpenAI-compatible tool definitions used by
    Ollama and Groq.
    """

    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get(
                    "parameters",
                    {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
            },
        }
        for tool in FUNCTION_DEFS
    ]


def _bedrock_tools() -> List[Dict[str, Any]]:
    """Convert FUNCTION_DEFS to Amazon Bedrock Converse tool format."""

    return [
        {
            "toolSpec": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "inputSchema": {
                    "json": tool.get(
                        "parameters",
                        {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    )
                },
            }
        }
        for tool in FUNCTION_DEFS
    ]


# ======================================================================
# GEMINI
# ======================================================================

def _ask_gemini(contents):

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Gemini's current GenerateContent API expects function declarations
    # inside a Tool object.
    declarations = []

    for tool in FUNCTION_DEFS:
        declarations.append(
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=tool.get(
                    "parameters",
                    {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
            )
        )

    gemini_tool = types.Tool(
        function_declarations=declarations
    )

    config = types.GenerateContentConfig(
        tools=[gemini_tool]
    )

    return client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=config,
    )


# ======================================================================
# BEDROCK
# ======================================================================

def _ask_bedrock(messages):

    from boto3 import client as boto_client

    bedrock = boto_client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    system_prompt = build_system_prompt()

    # Remove any synthetic system message from messages.
    conversation = []

    for message in messages:

        role = message["role"]

        if role == "system":
            continue

        content = message["content"]

        # Normal text message
        if isinstance(content, str):

            conversation.append(
                {
                    "role": role,
                    "content": [
                        {
                            "text": content
                        }
                    ],
                }
            )

        # Already-native Bedrock content
        elif isinstance(content, list):

            conversation.append(
                {
                    "role": role,
                    "content": content,
                }
            )

    response = bedrock.converse(
        modelId=BEDROCK_MODEL,

        system=[
            {
                "text": system_prompt
            }
        ],

        messages=conversation,

        toolConfig={
            "tools": _bedrock_tools()
        },
    )

    return response


# ======================================================================
# OLLAMA
# ======================================================================

def _ask_ollama(messages):

    import ollama

    system_prompt = build_system_prompt()

    ollama_messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    for message in messages:
        ollama_messages.append(message)

    return ollama.chat(
        model=OLLAMA_MODEL,
        messages=ollama_messages,
        tools=_openai_tools(),
    )


# ======================================================================
# GROQ
# ======================================================================

def _ask_groq(messages):

    from groq import Groq

    client = Groq(
        api_key=GROQ_API_KEY
    )

    system_prompt = build_system_prompt()

    groq_messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    for message in messages:
        groq_messages.append(message)

    return client.chat.completions.create(
        model=GROQ_MODEL,
        messages=groq_messages,
        tools=_openai_tools(),
        tool_choice="auto",
    )


# ======================================================================
# PROVIDER DISPATCH
# ======================================================================

def ask_provider(messages):

    if AI_PROVIDER == "gemini":
        return _ask_gemini(
            _build_gemini_contents(messages)
        )

    if AI_PROVIDER == "bedrock":
        return _ask_bedrock(messages)

    if AI_PROVIDER == "ollama":
        return _ask_ollama(messages)

    if AI_PROVIDER == "groq":
        return _ask_groq(messages)

    raise ValueError(
        f"Unsupported AI provider: {AI_PROVIDER}"
    )


# ======================================================================
# GEMINI MESSAGE CONVERSION
# ======================================================================

def _build_gemini_contents(messages):

    from google.genai import types

    contents = []

    for message in messages:

        role = message["role"]

        # System prompt is handled through the first user content
        # because this keeps compatibility with your existing flow.
        if role == "system":
            continue

        content = message.get("content")

        if isinstance(content, str):

            contents.append(
                types.Content(
                    role=role,
                    parts=[
                        types.Part(
                            text=content
                        )
                    ],
                )
            )

        elif isinstance(content, list):

            parts = []

            for item in content:

                if "text" in item:

                    parts.append(
                        types.Part(
                            text=item["text"]
                        )
                    )

            if parts:

                contents.append(
                    types.Content(
                        role=role,
                        parts=parts,
                    )
                )

    # System instructions are injected as the first user message.
    contents.insert(
        0,
        types.Content(
            role="user",
            parts=[
                types.Part(
                    text=build_system_prompt()
                )
            ],
        ),
    )

    return contents


# ======================================================================
# TOOL CALL EXTRACTION
# ======================================================================

def extract_tool_calls(response):

    if AI_PROVIDER == "gemini":
        return _extract_gemini_tool_calls(response)

    if AI_PROVIDER == "bedrock":
        return _extract_bedrock_tool_calls(response)

    if AI_PROVIDER in {"ollama", "groq"}:
        return _extract_openai_style_tool_calls(response)

    return []


def _extract_gemini_tool_calls(response):

    calls = []

    try:

        for candidate in response.candidates:

            for part in candidate.content.parts:

                function_call = getattr(
                    part,
                    "function_call",
                    None,
                )

                if not function_call:
                    continue

                name = function_call.name

                args = function_call.args

                if hasattr(args, "items"):
                    args = dict(args)

                elif isinstance(args, str):
                    args = json.loads(args)

                else:
                    args = {}

                calls.append(
                    {
                        "name": name,
                        "arguments": args,
                    }
                )

    except Exception:
        pass

    return calls


def _extract_bedrock_tool_calls(response):

    calls = []

    try:

        content_blocks = (
            response["output"]["message"]["content"]
        )

        for block in content_blocks:

            if "toolUse" not in block:
                continue

            tool_use = block["toolUse"]

            calls.append(
                {
                    "name": tool_use["name"],
                    "arguments": tool_use.get(
                        "input",
                        {}
                    ),
                    "tool_use_id": tool_use[
                        "toolUseId"
                    ],
                }
            )

    except Exception:
        pass

    return calls


def _extract_openai_style_tool_calls(response):

    calls = []

    try:

        message = response.choices[0].message

        tool_calls = (
            getattr(
                message,
                "tool_calls",
                None,
            )
            or []
        )

        for call in tool_calls:

            arguments = call.function.arguments

            if isinstance(arguments, str):
                arguments = json.loads(
                    arguments
                )

            calls.append(
                {
                    "name": call.function.name,
                    "arguments": arguments,
                    "tool_call_id": call.id,
                }
            )

    except Exception:
        pass

    return calls


# ======================================================================
# ADD TOOL RESULT TO CONVERSATION
# ======================================================================

def add_tool_results(
    messages,
    response,
    tool_calls,
    results,
):
    """
    Add the model's tool request and our tool results using the native
    conversation format expected by each provider.
    """

    if AI_PROVIDER == "bedrock":

        # Bedrock requires the assistant's original content blocks
        # containing the toolUse requests to remain in the conversation.

        assistant_content = (
            response["output"]["message"]["content"]
        )

        messages.append(
            {
                "role": "assistant",
                "content": assistant_content,
            }
        )

        result_blocks = []

        for call, result in zip(
            tool_calls,
            results,
        ):

            result_blocks.append(
                {
                    "toolResult": {
                        "toolUseId": call[
                            "tool_use_id"
                        ],
                        "content": [
                            {
                                "json": result
                            }
                        ],
                    }
                }
            )

        messages.append(
            {
                "role": "user",
                "content": result_blocks,
            }
        )

        return

    if AI_PROVIDER == "gemini":

        from google.genai import types

        # Gemini needs the model's function-call content followed by
        # function-response content.

        model_parts = []

        for call in tool_calls:

            model_parts.append(
                types.Part(
                    function_call=types.FunctionCall(
                        name=call["name"],
                        args=call["arguments"],
                    )
                )
            )

        messages.append(
            types.Content(
                role="model",
                parts=model_parts,
            )
        )

        response_parts = []

        for call, result in zip(
            tool_calls,
            results,
        ):

            response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=call["name"],
                        response=result,
                    )
                )
            )

        messages.append(
            types.Content(
                role="user",
                parts=response_parts,
            )
        )

        return

    # --------------------------------------------------------------
    # Ollama / Groq
    # --------------------------------------------------------------

    message = response.choices[0].message

    assistant_message = {
        "role": "assistant",
        "content": message.content or "",
    }

    if getattr(message, "tool_calls", None):

        assistant_message["tool_calls"] = []

        for call in message.tool_calls:

            assistant_message["tool_calls"].append(
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
            )

    messages.append(
        assistant_message
    )

    for call, result in zip(
        tool_calls,
        results,
    ):

        messages.append(
            {
                "role": "tool",
                "tool_call_id": call[
                    "tool_call_id"
                ],
                "content": json.dumps(
                    result,
                    ensure_ascii=False,
                ),
            }
        )


# ======================================================================
# TEXT EXTRACTION
# ======================================================================

def extract_text(response):

    # --------------------------------------------------------------
    # Gemini
    # --------------------------------------------------------------

    if AI_PROVIDER == "gemini":

        try:

            texts = []

            for candidate in response.candidates:

                for part in candidate.content.parts:

                    text = getattr(
                        part,
                        "text",
                        None,
                    )

                    if text:
                        texts.append(text)

            return "\n".join(texts)

        except Exception:
            return str(response)

    # --------------------------------------------------------------
    # Bedrock
    # --------------------------------------------------------------

    if AI_PROVIDER == "bedrock":

        try:

            texts = []

            for block in response[
                "output"
            ][
                "message"
            ][
                "content"
            ]:

                if "text" in block:

                    texts.append(
                        block["text"]
                    )
            import re
            return re.sub(
            r"<thinking>.*?</thinking>",
            "",
            "\n".join(texts),
            flags=re.DOTALL,
            ).strip()

        except Exception:
            return str(response)

    # --------------------------------------------------------------
    # Ollama
    # --------------------------------------------------------------

    if AI_PROVIDER == "ollama":

        try:
            return response.message.content or ""
        except Exception:
            return str(response)

    # --------------------------------------------------------------
    # Groq
    # --------------------------------------------------------------

    if AI_PROVIDER == "groq":

        try:
            return (
                response
                .choices[0]
                .message
                .content
                or ""
            )
        except Exception:
            return str(response)

    return str(response)


# ======================================================================
# MAIN TOOL-CALLING LOOP
# ======================================================================

def run_agent(user_question: str, history: List[Dict] | None = None) -> Tuple[str, List[Dict]]:
    """Execute the Knowledge Engine for a single user question.
    `history` holds prior message objects; if None a new list is created.
    Returns a tuple (answer, updated_history).
    """
    # Start with prior conversation or a fresh list.
    messages = history.copy() if history else []

    # Provide a verified schema before the model can generate a database query.
    # This keeps schema-first behavior reliable without changing provider APIs.
    if not any(
        isinstance(message.get("content"), str)
        and message["content"].startswith("Verified database schema for this request:")
        for message in messages
    ):
        from services.db_helpers import get_database_schema

        messages.append(
            {
                "role": "user",
                "content": (
                    "Verified database schema for this request:\n"
                    + json.dumps(get_database_schema(), ensure_ascii=False)
                ),
            }
        )

    # Append the new user question.
    messages.append({
        "role": "user",
        "content": f"[CURRENT USER REQUEST]\n{user_question}",
    })

    max_iterations = 4
    seen_calls: set = set()
    # (Removed for simplicity; limited iteration count handles repeats.)

    for iteration in range(max_iterations):
        response = ask_provider(messages)
        tool_calls = extract_tool_calls(response)

        # No tool call = final answer.
        if not tool_calls:
            answer = extract_text(response)
            # Attempt to format ticket list if answer looks like JSON
            try:
                data = json.loads(answer)
                if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                    lines = []
                    for item in data:
                        ticket_id = item.get('id') or item.get('ticket_number')
                        title = item.get('subject') or item.get('title') or item.get('description_text')
                        if ticket_id and title:
                            lines.append(f"Ticket {ticket_id}: {title}")
                    if lines:
                        answer = "\n".join(lines)
            except Exception:
                pass
            clean_history = history.copy() if history else []

            clean_history.append({
                "role": "user",
                "content": user_question
                })

            clean_history.append({
                "role": "assistant",
                "content": answer
                })

            return answer, clean_history

        # Detect duplicate calls (same name + arguments).
        duplicate = False
        for call in tool_calls:
            call_key = (call["name"], json.dumps(call["arguments"], sort_keys=True))
            if call_key in seen_calls:
                duplicate = True
                break
            seen_calls.add(call_key)
        if duplicate:
            # Return whatever we have so far to avoid endless repetition.
            answer = extract_text(response)
            if not answer.strip():
                answer = (
                    "I could not complete this request because the AI repeated "
                    "the same database operation without producing a final answer."
                )
            return answer, messages

        results = []
        for call in tool_calls:
            _safe_print(f"\n[TOOL CALL] {call['name']}")
            _safe_print(f"[ARGUMENTS] {call['arguments']}")
            try:
                print("\n===== TOOL CALL =====")
                print("Tool:", call.get("name"))
                print("Arguments:", call.get("arguments"))
                print("=====================\n")
                result = dispatch({"name": call["name"], "arguments": call["arguments"]})
                res_str = str(result)
                if len(res_str) > 600:
                    res_str = res_str[:600] + f" ... [{len(res_str)} chars truncated for console display]"
                _safe_print(f"[TOOL RESULT] {res_str}")
            except Exception as exc:
                result = {"error": str(exc)}
                _safe_print(f"[TOOL ERROR] {call['name']}: {exc}")
            results.append(result)

        # Add the tool results back into the conversation.
        add_tool_results(messages, response, tool_calls, results)

    # If we exit the loop without a final answer.
    return ("I was unable to complete the investigation within the allowed number of tool calls.", messages)


# ======================================================================
# REPL
# ======================================================================

def main():

    print(
        f"Knowledge Engine "
        f"(provider = {AI_PROVIDER})"
    )

    print(
        'How can I help you today?\n'
    )
    conversation_history: List[Dict] = []
    while True:

        user_input = input(
            "You: "
        ).strip()

        if user_input.lower() in {
            "exit",
            "quit",
        }:
            break

        if not user_input:
            continue

        try:

            answer, conversation_history = run_agent(user_input, conversation_history)

            print(
                f"\nAI: {answer}\n"
            )

        except Exception as exc:

            print(
                f"\n[AI ERROR] {exc}\n"
            )


# ======================================================================
# ENTRY POINT
# ======================================================================

if __name__ == "__main__":

    if not os.getenv(
        "GEMINI_API_KEY"
    ):
        os.environ[
            "GEMINI_API_KEY"
        ] = GEMINI_API_KEY

    main()