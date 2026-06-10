from groq import Groq
from app.core.config import Settings

client = Groq(api_key=Settings.GROQ_API_KEY)

def call_llm(prompt: str):
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
        {
            "role": "user",
            "content": prompt
        }
        ],
    )

    return response.choices[0].message.content



