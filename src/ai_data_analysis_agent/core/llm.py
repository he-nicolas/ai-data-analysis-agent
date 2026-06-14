from abc import ABC, abstractmethod
from groq import Groq
from openai import OpenAI
from ai_data_analysis_agent.core.config import Settings


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass


class GroqProvider(LLMProvider):
    def __init__(self):
        self.client = Groq(api_key=Settings.GROQ_API_KEY)

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=Settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.client = OpenAI(api_key=Settings.OPENAI_API_KEY)

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=Settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

# Add more providers here as needed


def get_provider() -> LLMProvider:
    if Settings.LLM_PROVIDER == "groq":
        return GroqProvider()
    elif Settings.LLM_PROVIDER == "openai":
        return OpenAIProvider()
    else:
        raise ValueError(f"Unknown provider: {Settings.LLM_PROVIDER}")


_provider = get_provider()


def call_llm(prompt: str) -> str:
    return _provider.generate(prompt)