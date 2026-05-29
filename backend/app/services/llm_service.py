import json
from typing import Any, List, Optional

from groq import Groq
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config import get_settings

SYSTEM_TUTOR = """You are StudySphere AI Tutor — an expert teacher, mentor, and study assistant.
Provide clear, step-by-step explanations with examples. Use markdown only (headings, bullet lists, bold, code blocks).
Never return raw JSON or wrap the answer in curly braces. Write in natural, readable prose.
Ask thoughtful follow-up questions to deepen understanding. Be encouraging and pedagogical."""

SYSTEM_RAG = """You are a document Q&A assistant. Answer ONLY using the provided context from uploaded documents.
If the answer is not in the context, respond exactly: "I could not find this information in your uploaded documents."
Never hallucinate or use outside knowledge. Use markdown formatting; never return raw JSON."""

SYSTEM_QUIZ = """You are a quiz generator. Return valid JSON only with this structure:
{"questions": [{"id": 1, "type": "mcq|true_false|short_answer", "question": "...", "options": ["A","B","C","D"], "correct_answer": "...", "explanation": "..."}]}
Generate exactly the requested number of questions."""

SYSTEM_EVAL = """You are a quiz evaluator. Analyze student answers and return JSON:
{"score": 0-100, "accuracy": 0-100, "concept_understanding": "...", "weak_areas": [], "strong_areas": [], "improvement_suggestions": [], "per_question": []}"""


class LLMService:
    def __init__(self):
        settings = get_settings()
        self.model = settings.groq_model
        self.client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
        self._lc = None

    @property
    def lc(self) -> ChatGroq:
        if self._lc is None:
            settings = get_settings()
            self._lc = ChatGroq(
                api_key=settings.groq_api_key,
                model_name=settings.groq_model,
                temperature=0.7,
            )
        return self._lc

    def chat(
        self,
        messages: List[dict],
        system: str = SYSTEM_TUTOR,
        temperature: float = 0.7,
    ) -> str:
        if not self.client:
            return "LLM service is not configured. Please set GROQ_API_KEY."

        api_messages = [{"role": "system", "content": system}]
        for m in messages:
            api_messages.append({"role": m["role"], "content": m["content"]})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            temperature=temperature,
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""

    def chat_with_context(
        self,
        query: str,
        context: str,
        history: Optional[List[dict]] = None,
    ) -> str:
        prompt = f"""Context from documents:
---
{context}
---

User question: {query}

Remember: Answer ONLY from the context above."""
        messages = list(history or [])
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, system=SYSTEM_RAG, temperature=0.3)

    def generate_json(self, prompt: str, system: str = SYSTEM_QUIZ) -> dict:
        raw = self.chat([{"role": "user", "content": prompt}], system=system, temperature=0.5)
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
        return {"raw": raw}

    def langchain_invoke(self, messages: List, system: str = SYSTEM_TUTOR) -> str:
        lc_messages = [SystemMessage(content=system)]
        for m in messages:
            if m.get("role") == "user":
                lc_messages.append(HumanMessage(content=m["content"]))
            elif m.get("role") == "assistant":
                lc_messages.append(AIMessage(content=m["content"]))
        result = self.lc.invoke(lc_messages)
        return result.content if hasattr(result, "content") else str(result)


llm = LLMService()
