# ----------------------------------------------------------------------
# ai_entry.py
#
# Provider-independent AI entry point for Support Copilot.
#
# Providers:
#   - Gemini
#   - Amazon Bedrock
#   - Groq
#   - Ollama
#
# Architecture:
#
#   User
#     ↓
#   LLM
#     ↓
#   Tool call?
#     ↓ yes
#   dispatch()
#     ↓
#   Tool result
#     ↓
#   LLM
#     ↓
#   Final answer
# ----------------------------------------------------------------------

import json
import os
from typing import List, Dict, Any

import requests

from services.prompts import SYSTEM_PROMPT
from services.tools import FUNCTION_DEFS, dispatch

from config.config import (
    AI_PROVIDER,
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    BEDROCK_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
)

# ----------------------------------------------------------------------
# Optional provider configuration
#
# These are imported dynamically so the project does not fail if a
# provider is not configured.
# ----------------------------------------------------------------------

MAX_TOOL_ROUNDS = 8


# ======================================================================
# Generic helpers
# ======================================================================

def safe_json(value):
    """
    Convert a value to a Python object safely.

    Handles:
        dict
        JSON string
        None
        malformed JSON
    """

    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, str):

        try:
            return json.loads(value)
        except json.JSONDecodeError:

            print(
                f"[WARNING] Could not parse tool arguments: {value}"
            )

            return {}

    return {}


def json_text(value):
    """
    Convert tool results to text safely.
    """

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )

    except Exception:

        return str(value)


# ======================================================================
# Tool definition normalization
# ======================================================================

def normalize_tool_definition(tool):
    """
    Convert the project's FUNCTION_DEFS into a common internal format.

    Supports several common formats.

    Format A:
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {...}
            }
        }

    Format B:
        {
            "name": "...",
            "description": "...",
            "parameters": {...}
        }

    Format C:
        {
            "type": "function",
            "name": "...",
            "description": "...",
            "parameters": {...}
        }
    """

    if not isinstance(tool, dict):
        raise ValueError(
            f"Invalid tool definition: {tool}"
        )

    # --------------------------------------------------------------
    # OpenAI-style
    # --------------------------------------------------------------

    if "function" in tool:

        function = tool["function"]

        return {
            "name": function["name"],
            "description": function.get(
                "description",
                "",
            ),
            "parameters": function.get(
                "parameters",
                {
                    "type": "object",
                    "properties": {},
                },
            ),
        }

    # --------------------------------------------------------------
    # Direct function definition
    # --------------------------------------------------------------

    if "name" in tool:

        return {
            "name": tool["name"],
            "description": tool.get(
                "description",
                "",
            ),
            "parameters": tool.get(
                "parameters",
                tool.get(
                    "inputSchema",
                    {
                        "type": "object",
                        "properties": {},
                    },
                ),
            ),
        }

    raise ValueError(
        f"Cannot determine tool name from definition: {tool}"
    )


def normalized_tools():
    """
    Return all project tools in normalized format.
    """

    return [
        normalize_tool_definition(tool)
        for tool in FUNCTION_DEFS
    ]


# ======================================================================
# OpenAI-compatible tool format
#
# Used by:
#   - Groq
#   - Ollama
# ======================================================================

def openai_tools():
    """
    Convert our internal tool definitions into OpenAI-compatible format.
    """

    result = []

    for tool in normalized_tools():

        result.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
        )

    return result


# ======================================================================
# Bedrock tool format
# ======================================================================

def bedrock_tools():
    """
    Convert project tools into Amazon Bedrock Converse format.
    """

    result = []

    for tool in normalized_tools():

        result.append(
            {
                "toolSpec": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": {
                        "json": tool["parameters"]
                    },
                }
            }
        )

    return result


# ======================================================================
# Gemini tool format
# ======================================================================

def gemini_tools():
    """
    Convert project tools into Gemini's FunctionDeclaration format.

    Current google-genai SDK expects tools to be supplied through:

        GenerateContentConfig(tools=[...])
    """

    from google.genai import types

    declarations = []

    for tool in normalized_tools():

        declarations.append(
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
            )
        )

    return [
        types.Tool(
            function_declarations=declarations
        )
    ]


# ======================================================================
# Execute a tool
# ======================================================================

def execute_tool(tool_name, arguments):
    """
    Central tool execution point.

    Every provider eventually comes here.
    """

    arguments = safe_json(arguments)

    print(
        f"\n[TOOL CALL] {tool_name}"
    )

    print(
        f"[ARGUMENTS] {arguments}"
    )

    try:

        result = dispatch(
            {
                "name": tool_name,
                "arguments": arguments,
            }
        )

        print(
            f"[TOOL RESULT] {str(result)[:1000]}"
        )

        return result

    except Exception as exc:

        print(
            f"[TOOL ERROR] {tool_name}: {exc}"
        )

        return {
            "error": str(exc),
            "tool": tool_name,
        }


# ======================================================================
# GEMINI
# ======================================================================

def run_gemini(history):
    """
    Gemini client-side function-calling loop.

    Current google-genai SDK:
        tools go inside GenerateContentConfig.
    """

    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    # --------------------------------------------------------------
    # Build Gemini conversation
    # --------------------------------------------------------------

    contents = []

    # System instruction should NOT be inserted as a fake user message.
    # It belongs in GenerateContentConfig.system_instruction.

    for message in history:

        role = message["role"]

        if role == "assistant":
            role = "model"

        contents.append(
            types.Content(
                role=role,
                parts=[
                    types.Part(
                        text=message["content"]
                    )
                ],
            )
        )

    # --------------------------------------------------------------
    # Tool configuration
    # --------------------------------------------------------------

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=gemini_tools(),
    )

    # --------------------------------------------------------------
    # Agent loop
    # --------------------------------------------------------------

    for round_number in range(MAX_TOOL_ROUNDS):

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )

        candidate = response.candidates[0]

        function_calls = []

        for part in candidate.content.parts:

            function_call = getattr(
                part,
                "function_call",
                None,
            )

            if function_call:
                function_calls.append(
                    function_call
                )

        # ----------------------------------------------------------
        # No tool call → final response
        # ----------------------------------------------------------

        if not function_calls:

            text_parts = []

            for part in candidate.content.parts:

                text = getattr(
                    part,
                    "text",
                    None,
                )

                if text:
                    text_parts.append(text)

            return "\n".join(text_parts).strip()

        # ----------------------------------------------------------
        # Add model response to conversation
        # ----------------------------------------------------------

        contents.append(
            candidate.content
        )

        # ----------------------------------------------------------
        # Execute requested tools
        # ----------------------------------------------------------

        function_response_parts = []

        for function_call in function_calls:

            result = execute_tool(
                function_call.name,
                function_call.args,
            )

            function_response_parts.append(
                types.Part.from_function_response(
                    name=function_call.name,
                    response={
                        "result": result
                    },
                )
            )

        # ----------------------------------------------------------
        # Add tool results
        # ----------------------------------------------------------

        contents.append(
            types.Content(
                role="user",
                parts=function_response_parts,
            )
        )

    return (
        "I could not complete the investigation "
        "within the allowed number of tool calls."
    )


# ======================================================================
# BEDROCK
# ======================================================================

def run_bedrock(history):
    """
    Amazon Bedrock Converse client-side tool-calling loop.

    Bedrock supports toolConfig on Converse and returns toolUse
    blocks which the application executes and sends back as
    toolResult blocks.
    """

    import boto3

    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    # --------------------------------------------------------------
    # Build Bedrock messages
    # --------------------------------------------------------------

    messages = []

    for message in history:

        role = message["role"]

        if role not in {
            "user",
            "assistant",
        }:
            continue

        messages.append(
            {
                "role": role,
                "content": [
                    {
                        "text": message["content"]
                    }
                ],
            }
        )

    # --------------------------------------------------------------
    # Bedrock tool configuration
    # --------------------------------------------------------------

    tool_config = {
        "tools": bedrock_tools(),
        "toolChoice": {
            "auto": {}
        },
    }

    # --------------------------------------------------------------
    # Agent loop
    # --------------------------------------------------------------

    for round_number in range(MAX_TOOL_ROUNDS):

        response = bedrock.converse(
            modelId=BEDROCK_MODEL,
            system=[
                {
                    "text": SYSTEM_PROMPT
                }
            ],
            messages=messages,
            toolConfig=tool_config,
        )

        output_message = response["output"]["message"]

        content = output_message.get(
            "content",
            [],
        )

        # ----------------------------------------------------------
        # Find tool requests
        # ----------------------------------------------------------

        tool_uses = []

        for block in content:

            if "toolUse" in block:

                tool_uses.append(
                    block["toolUse"]
                )

        # ----------------------------------------------------------
        # No tool call → final answer
        # ----------------------------------------------------------

        if not tool_uses:

            answer_parts = []

            for block in content:

                if "text" in block:

                    answer_parts.append(
                        block["text"]
                    )

            return "\n".join(
                answer_parts
            ).strip()

        # ----------------------------------------------------------
        # Add model response exactly as returned
        # ----------------------------------------------------------

        messages.append(
            output_message
        )

        # ----------------------------------------------------------
        # Execute tools
        # ----------------------------------------------------------

        tool_result_blocks = []

        for tool_use in tool_uses:

            tool_name = tool_use["name"]

            arguments = tool_use.get(
                "input",
                {},
            )

            result = execute_tool(
                tool_name,
                arguments,
            )

            tool_result_blocks.append(
                {
                    "toolResult": {
                        "toolUseId": tool_use[
                            "toolUseId"
                        ],
                        "content": [
                            {
                                "json": result
                            }
                        ],
                    }
                }
            )

        # ----------------------------------------------------------
        # Send results back to Bedrock
        # ----------------------------------------------------------

        messages.append(
            {
                "role": "user",
                "content": tool_result_blocks,
            }
        )

    return (
        "I could not complete the investigation "
        "within the allowed number of tool calls."
    )


# ======================================================================
# GROQ / OLLAMA
# ======================================================================

def run_openai_compatible(
    history,
    base_url,
    api_key,
    model,
):
    """
    Generic tool-calling implementation for APIs that follow the
    OpenAI chat-completions tool format.

    This works for:
        - Groq
        - Ollama
    """

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    messages.extend(history)

    tools = openai_tools()

    headers = {
        "Content-Type": "application/json",
    }

    if api_key:

        headers["Authorization"] = (
            f"Bearer {api_key}"
        )

    # --------------------------------------------------------------
    # Agent loop
    # --------------------------------------------------------------

    for round_number in range(MAX_TOOL_ROUNDS):

        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }

        response = requests.post(
            base_url,
            headers=headers,
            json=payload,
            timeout=600,
        )

        response.raise_for_status()

        data = response.json()

        message = data["choices"][0]["message"]

        tool_calls = message.get(
            "tool_calls"
        )

        # ----------------------------------------------------------
        # No tool call → final answer
        # ----------------------------------------------------------

        if not tool_calls:

            return (
                message.get(
                    "content",
                    "",
                )
                or ""
            ).strip()

        # ----------------------------------------------------------
        # Add assistant tool-call message
        # ----------------------------------------------------------

        messages.append(
            message
        )

        # ----------------------------------------------------------
        # Execute requested tools
        # ----------------------------------------------------------

        for tool_call in tool_calls:

            function = tool_call["function"]

            tool_name = function["name"]

            arguments = safe_json(
                function.get(
                    "arguments",
                    "{}",
                )
            )

            result = execute_tool(
                tool_name,
                arguments,
            )

            # ------------------------------------------------------
            # Send result back to model
            # ------------------------------------------------------

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call[
                        "id"
                    ],
                    "content": json_text(
                        result
                    ),
                }
            )

    return (
        "I could not complete the investigation "
        "within the allowed number of tool calls."
    )


# ======================================================================
# PROVIDER ROUTER
# ======================================================================

def ask_with_tools(history):
    """
    Provider-independent entry point.
    """

    provider = AI_PROVIDER.lower().strip()

    # --------------------------------------------------------------
    # Gemini
    # --------------------------------------------------------------

    if provider == "gemini":

        return run_gemini(history)

    # --------------------------------------------------------------
    # Amazon Bedrock
    # --------------------------------------------------------------

    if provider == "bedrock":

        return run_bedrock(history)

    # --------------------------------------------------------------
    # Groq
    # --------------------------------------------------------------

    if provider == "groq":

        from config.config import (
            GROQ_API_KEY,
            GROQ_MODEL,
        )

        return run_openai_compatible(
            history=history,
            base_url=(
                "https://api.groq.com/openai/v1/"
                "chat/completions"
            ),
            api_key=GROQ_API_KEY,
            model=GROQ_MODEL,
        )

    # --------------------------------------------------------------
    # Ollama
    # --------------------------------------------------------------

    if provider == "ollama":

        from config.config import (
            OLLAMA_MODEL,
        )

        return run_openai_compatible(
            history=history,
            base_url=(
                "http://127.0.0.1:11434/v1/"
                "chat/completions"
            ),
            api_key="ollama",
            model=OLLAMA_MODEL,
        )

    raise ValueError(
        f"Unsupported AI_PROVIDER: {AI_PROVIDER}"
    )


# ======================================================================
# MAIN
# ======================================================================

def main():

    print(
        f"Support-Copilot "
        f"(provider = {AI_PROVIDER})"
    )

    print(
        'Type your question, or "exit" / "quit" to stop.\n'
    )

    history: List[Dict[str, str]] = []

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

        history.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        try:

            answer = ask_with_tools(
                history
            )

        except Exception as exc:

            print(
                f"\n[AI ERROR] {exc}\n"
            )

            # Don't leave failed request in history.
            history.pop()

            continue

        history.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        print(
            f"Bot: {answer}\n"
        )


# ======================================================================
# ENTRY POINT
# ======================================================================

if __name__ == "__main__":

    if GEMINI_API_KEY:

        os.environ[
            "GEMINI_API_KEY"
        ] = GEMINI_API_KEY

    main()