from google import genai
from config.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

print("Models available for generateContent:\n")

for model in client.models.list():
    if "generateContent" in model.supported_actions:
        print(model.name)