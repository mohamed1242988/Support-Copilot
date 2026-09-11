from typing import Dict, List


# ----------------------------------------------------------------------
# Tools available to the AI
# ----------------------------------------------------------------------

FUNCTION_DEFS: List[Dict] = [

    {
        "name": "query_database",
        "description": (
            "Execute a READ-ONLY SQL query against the Support Copilot SQLite "
            "database. Use this for structured questions requiring filtering, "
            "timeframes/dates (e.g. created_at >= date('now', '-1 month')), customer_name, "
            "joins, aggregations, or direct access to fields. "
            "For database questions, call get_database_schema first and use only "
            "the table and column names it returns. "
            "The agent column is assigned_agent, not assigned_agent_name. "
            "For a partial agent name such as 'Hager', use assigned_agent LIKE '%Hager%'. "
            "This field represents the current assigned agent; it does not prove assignment history. "
            "Only SELECT/WITH queries are allowed. "
            "IMPORTANT: for customer or company names, prefer partial matching "
            "with LIKE '%value%'. Example: WHERE Customer_Name LIKE '%Mary Kay%'. "
            "Text comparisons are case-insensitive, including values such as "
            "priority = 'urgent' matching 'Urgent'. "
            "For date filtering, use SQLite date functions like "
            "created_at >= date('now', '-1 month') or created_at >= '2026-08-01'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": (
                        "A read-only SQLite SELECT or WITH query."
                    )
                }
            },
            "required": ["sql"],
        },
    },

    {
        "name": "get_database_schema",
        "description": (
            "Return the available database tables, columns, and important "
            "relationships, column meanings, and business rules. Use this "
            "before constructing a query when the user's request involves "
            "business concepts, dates, conversations, or multiple tables. "
            "The schema includes rules such as agent messages, public replies, "
            "and missed follow-ups."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    {
        "name": "search_tickets",
        "description": (
            "Use full-text keyword search to retrieve Freshdesk tickets matching "
            "technical concepts, symptoms, error messages, or keywords (e.g. 'Boomi process timeout'). "
            "NOTE: This tool performs FTS text matching and DOES NOT filter by date. "
            "If the user asks for tickets within a specific timeframe (e.g. 'last month'), "
            "use query_database first to filter by created_at date."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural-language or issue-focused search query, "
                        "for example: 'Boomi process timeout failures'"
                    )
                }
            },
            "required": ["query"],
        },
    },

    {
        "name": "get_ticket_by_id",
        "description": (
            "Return a Freshdesk ticket along with its full conversation history and comments "
            "when you know its ticket ID (freshdesk_tickets.id). Use this for a ticket summary "
            "when conversations are requested. The ticket description is description_text; "
            "conversation/comment content is body_text. Never report description_text as the "
            "last comment. For the last comment, choose the conversation with the latest "
            "created_at."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "integer",
                    "description": "Freshdesk ticket ID, not conversation ID."
                }
            },
            "required": ["ticket_id"],
        },
    },

    {
        "name": "get_conversations_for_ticket",
        "description": (
            "Return all Freshdesk conversations belonging to a specific "
            "Freshdesk ticket. The relationship is "
            "freshdesk_tickets.id = freshdesk_conversations.ticket_id. "
            "Each conversation's body_text is the comment content and created_at "
            "is when it was written. incoming = 0 means agent-authored and "
            "incoming = 1 means customer-authored; private = 1 means internal note. "
            "The supplied ticket_id MUST be a Freshdesk ticket ID, not a "
            "conversation ID."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "integer",
                    "description": "Freshdesk ticket ID."
                }
            },
            "required": ["ticket_id"],
        },
    },
]


# ----------------------------------------------------------------------
# Dispatcher
# ----------------------------------------------------------------------

def dispatch(call: Dict) -> Dict:
    name = call["name"]
    args = call.get("arguments", {})

    from services.db_helpers import (
        query_database,
        get_database_schema,
        get_ticket_by_id,
        search_tickets,
        get_conversations_for_ticket,
    )

    if name == "query_database":
        return {
            "results": query_database(args["sql"])
        }

    if name == "get_database_schema":
        return {
            "schema": get_database_schema()
        }

    if name == "search_tickets":
        return {
            "results": search_tickets(args["query"])
        }

    if name == "get_ticket_by_id":
        return {
            "ticket": get_ticket_by_id(args["ticket_id"])
        }

    if name == "get_conversations_for_ticket":
        return {
            "conversations": get_conversations_for_ticket(
                args["ticket_id"]
            )
        }

    raise ValueError(f"Unsupported tool: {name}")