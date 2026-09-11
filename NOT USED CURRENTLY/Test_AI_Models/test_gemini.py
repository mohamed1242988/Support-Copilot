from google import genai

client = genai.Client(
    api_key="AQ.Ab8RN6LilOMUuwZARlF7KQVx2EMu6FR-4UmRiAz6Ikb-JD2wxQ"
)

response = client.models.generate_content(
    model="gemini-3.7-flash",
    contents="Say hello in one sentence."
)

print(response.text)