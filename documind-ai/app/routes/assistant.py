import json
import uuid
from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    session,
)
from app.extensions import db
from app.models.conversation import Conversation, Message
from app.services.llm_provider import (
    LLMConfigurationError,
    LLMProviderError,
    get_llm_provider,
)
from app.services.rag_service import answer_question
from app.services.vector_store import VectorStore

assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")


def _get_or_create_conversation() -> Conversation:
    session_id = session.get("chat_session_id")
    if not session_id:
        session_id = uuid.uuid4().hex
        session["chat_session_id"] = session_id

    conv = Conversation.query.filter_by(session_identifier=session_id).first()
    if not conv:
        conv = Conversation(session_identifier=session_id)
        db.session.add(conv)
        db.session.commit()
    return conv


@assistant_bp.route("/")
def chat_page():
    """Render the AI Assistant chat interface."""
    conv = _get_or_create_conversation()
    history = []
    for msg in conv.messages:
        sources = json.loads(msg.sources_json) if msg.sources_json else []
        history.append({"role": msg.role, "content": msg.content, "sources": sources})
    return render_template("assistant.html", history=history)


@assistant_bp.route("/ask", methods=["POST"])
def ask():
    """Handle a user question via RAG and return JSON response with sources."""
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    response_language = (data.get("response_language") or "Auto (match question)").strip()
    if not question:
        return jsonify({"error": "Please enter a question."}), 400

    conv = _get_or_create_conversation()
    db.session.add(Message(conversation_id=conv.id, role="user", content=question))
    db.session.commit()

    try:
        provider = get_llm_provider()
        vector_store = VectorStore(current_app.config["VECTOR_INDEX_FOLDER"])
        result = answer_question(
            question=question,
            provider=provider,
            vector_store=vector_store,
            top_k=current_app.config.get("TOP_K_RESULTS", 5),
            response_language=response_language,
        )
    except LLMConfigurationError as exc:
        return jsonify({"error": f"AI not configured: {exc}"}), 503
    except LLMProviderError as exc:
        return jsonify({"error": f"AI service error: {exc}"}), 502

    db.session.add(
        Message(
            conversation_id=conv.id,
            role="assistant",
            content=result["answer"],
            sources_json=json.dumps(result["sources"], ensure_ascii=False),
        )
    )
    db.session.commit()

    return jsonify(result)


@assistant_bp.route("/clear", methods=["POST"])
def clear_chat():
    """Clear the current session's conversation history."""
    session_id = session.get("chat_session_id")
    if session_id:
        conv = Conversation.query.filter_by(session_identifier=session_id).first()
        if conv:
            db.session.delete(conv)
            db.session.commit()
    return jsonify({"status": "cleared"})
