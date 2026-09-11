from services.ai import ask_ai
from services.retriever import build_context
from services.prompts import build_prompt
from services.sync import incremental_sync
from storage.database import (initialize_database,get_jira_comments)
                              
from services.sync import sync_jira_projects
from storage.database import update_sync_state


from services.retriever import build_context



#print("Initializing Support Copilot...")

initialize_database()


#print("Synchronizing Freshdesk tickets...")

#incremental_sync()

context = build_context(
                issue_description="petroff renewal"
            )


def print_ranking(source, ranked_evidence, limit=5):
    print(f"\n===== {source.upper()} RANKING =====")
    if ranked_evidence:
        metadata = ranked_evidence[0].document.metadata
        print(
            "Retrieval query: {query} | anchors={anchors} | term_stats={stats}".format(
                query=metadata.get("retrieval_query"),
                anchors=metadata.get("selected_anchors"),
                stats=metadata.get("term_statistics"),
            )
        )
    for position, item in enumerate(ranked_evidence[:limit], start=1):
        breakdown = item.score_breakdown
        stage = item.document.get_metadata("retrieval_stage", "unknown")
        print(f"#{position} | {item.document.id} | {item.document.title} | stage={stage}")
        print(
            "BM25={bm25_rank:.4f} | lexical #{lexical_rank:.0f}={lexical_score:.3f} "
            "| semantic={semantic_score:.3f} | hybrid={hybrid_contribution:.2f} "
            "| phrase={phrase_bonus:.2f} | title={title_bonus:.2f} "
            "| content={content_bonus:.2f} | coverage={coverage_bonus:.2f} "
            "| complete={complete_match_bonus:.2f} "
            "| penalty={weak_match_penalty:.2f} | final={final_score:.2f}".format(
                **breakdown
            )
        )


print_ranking("Freshdesk", context.freshdesk_ranked_evidence)
print_ranking("Jira", context.jira_ranked_evidence)

#prompt = build_prompt(context)

#print(prompt)


"""
if __name__ == "__main__":

    sync_jira_projects(
        [
            "TE",
            "UA",
            "PTS",
            "PSR"
        ]
    )

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

        

        print("\nPrompt building ended, here is your context:\n")

        print(prompt)

    except Exception as e:
        
        print(
            f"\nError: {e}\n"
        )
"""
    
