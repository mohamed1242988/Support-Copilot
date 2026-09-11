from services.ai import ask_ai
from services.retriever import build_context
from services.prompts import build_prompt
from services.sync import incremental_sync
from storage.database import initialize_database


#print("Initializing Support Copilot...")

#initialize_database()


#print("Synchronizing Freshdesk tickets...")

incremental_sync()


print("Support Copilot ready.\n")


conversation_history = []


while True:

    ticket_id = input(
        "Enter Freshdesk Ticket ID or N/A (or 'exit'): "
    ).strip()


    if ticket_id.lower() in ["exit", "quit"]:
        break


    try:

        if ticket_id.upper() == "N/A":

            issue_description = input(
                "Describe the incoming issue: "
            ).strip()

            context = build_context(
                issue_description=issue_description
            )

        else:

            context = build_context(
                ticket_id=int(ticket_id)
            )


        prompt = build_prompt(context)


        conversation_history.append(
            {
                "role": "user",
                "content": prompt
            }
        )

        print("\nAnalyzing issue with local AI...\n")


        response = ask_ai(
            conversation_history
        )


        ai_message = response["message"]["content"]


        conversation_history.append(
            {
                "role": "assistant",
                "content": ai_message
            }
        )


        print("\nAI Analysis:\n")

        print(ai_message)

        print()


    except Exception as e:

        print(
            f"\nError: {e}\n"
        )