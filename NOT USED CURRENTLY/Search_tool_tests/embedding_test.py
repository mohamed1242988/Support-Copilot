from knowledge.embeddings import create_embedding

text = "User cannot connect to QuickBooks Desktop integration"

vector = create_embedding(text)

print(type(vector))
print(len(vector))
print(vector[:5])