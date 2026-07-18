import os

import logllama
from openai import OpenAI


logllama.init(api_key=os.getenv("LOGLLAMA_API_KEY", "llama-dev-key"))
client = logllama.wrap_openai(OpenAI(api_key=os.environ["OPENAI_API_KEY"]))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write one sentence about observability."}],
    metadata={"route": "/demo", "user_id": "local-dev"},
)

print(response.choices[0].message.content)
