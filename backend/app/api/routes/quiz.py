import base64
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Literal

from app.core.supabase_client import get_supabase
from app.dependencies import get_current_user, rate_limit_user
from app.services.llm_service import SYSTEM_EVAL, SYSTEM_QUIZ, llm
from app.services.pdf_service import generate_quiz_report_pdf

router = APIRouter(prefix="/quiz", tags=["Quiz Generator"])


class QuizGenerateRequest(BaseModel):
    topic: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    question_count: int = Field(ge=10, le=50)
    question_type: Literal["mcq", "true_false", "short_answer", "mixed"] = "mixed"


class QuizSubmitRequest(BaseModel):
    answers: Dict[str, Any]


@router.get("/history")
async def quiz_history(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    quizzes = sb.table("quizzes").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    attempts = sb.table("quiz_attempts").select("*, quizzes(topic)").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    return {"quizzes": quizzes.data or [], "attempts": attempts.data or []}


@router.post("/generate")
async def generate_quiz(body: QuizGenerateRequest, user: dict = Depends(rate_limit_user)):
    prompt = f"""Generate a {body.difficulty} difficulty quiz on "{body.topic}".
Number of questions: {body.question_count}
Question type: {body.question_type}
Return valid JSON with a "questions" array."""

    data = llm.generate_json(prompt, system=SYSTEM_QUIZ)
    questions = data.get("questions", [])
    if not questions:
        raise HTTPException(status_code=500, detail="Failed to generate quiz")

    quiz_id = str(uuid4())
    row = {
        "id": quiz_id,
        "user_id": user["id"],
        "topic": body.topic,
        "difficulty": body.difficulty,
        "question_count": body.question_count,
        "question_type": body.question_type,
        "questions": questions,
    }
    sb = get_supabase()
    sb.table("quizzes").insert(row).execute()
    return {"quiz_id": quiz_id, "questions": questions, "topic": body.topic}


@router.get("/{quiz_id}")
async def get_quiz(quiz_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("quizzes").select("*").eq("id", quiz_id).eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return result.data[0]


@router.post("/{quiz_id}/submit")
async def submit_quiz(quiz_id: str, body: QuizSubmitRequest, user: dict = Depends(rate_limit_user)):
    sb = get_supabase()
    quiz = sb.table("quizzes").select("*").eq("id", quiz_id).eq("user_id", user["id"]).execute()
    if not quiz.data:
        raise HTTPException(status_code=404, detail="Quiz not found")

    q_data = quiz.data[0]
    eval_prompt = f"""Evaluate this quiz attempt.
Topic: {q_data['topic']}
Questions: {q_data['questions']}
Student answers: {body.answers}
Provide detailed evaluation JSON."""

    evaluation = llm.generate_json(eval_prompt, system=SYSTEM_EVAL)
    score = evaluation.get("score", 0)
    accuracy = evaluation.get("accuracy", score)

    attempt_id = str(uuid4())
    sb.table("quiz_attempts").insert({
        "id": attempt_id,
        "quiz_id": quiz_id,
        "user_id": user["id"],
        "answers": body.answers,
        "score": score,
        "accuracy": accuracy,
        "evaluation": evaluation,
    }).execute()

    pdf_bytes = generate_quiz_report_pdf(evaluation, q_data["topic"])
    report_id = str(uuid4())
    sb.table("quiz_reports").insert({
        "id": report_id,
        "attempt_id": attempt_id,
        "user_id": user["id"],
        "report_data": evaluation,
    }).execute()

    return {
        "attempt_id": attempt_id,
        "score": score,
        "accuracy": accuracy,
        "evaluation": evaluation,
        "pdf_base64": base64.b64encode(pdf_bytes).decode(),
    }


@router.get("/reports/{attempt_id}/pdf")
async def download_report(attempt_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    attempt = sb.table("quiz_attempts").select("*, quizzes(topic)").eq("id", attempt_id).eq("user_id", user["id"]).execute()
    if not attempt.data:
        raise HTTPException(status_code=404, detail="Attempt not found")

    evaluation = attempt.data[0].get("evaluation", {})
    topic = attempt.data[0].get("quizzes", {}).get("topic", "Quiz")
    pdf_bytes = generate_quiz_report_pdf(evaluation, topic)
    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="quiz-report-{attempt_id[:8]}.pdf"'
    })
