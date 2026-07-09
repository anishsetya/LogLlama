import os

from logllama import track_openai
from openai import OpenAI


client = track_openai(
    OpenAI(api_key=os.environ["OPENAI_API_KEY"]),
    api_key=os.getenv("LOGLLAMA_API_KEY", "llama-dev-key"),
    endpoint=os.getenv("LOGLLAMA_ENDPOINT", "http://localhost:8000"),
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write one sentence about observability."}],
    metadata={"route": "/demo", "user_id": "local-dev"},
)

print(response.choices[0].message.content)
