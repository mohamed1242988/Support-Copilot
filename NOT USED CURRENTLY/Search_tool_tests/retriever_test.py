from services.retriever import build_context

query = "Variance Between DHW and APP"

context = build_context(
    ticket_id=None,
    issue_description=query
)

print("\n===== DOCUMENTS =====")
for doc in context["documents"]:
    print("SOURCE:", doc.source)
    print("ID:", doc.id)
    print("TITLE:", doc.title)
    print("CONTENT PREVIEW:")
    print(doc.content[:300])
    print("--------------------")
#print(context)