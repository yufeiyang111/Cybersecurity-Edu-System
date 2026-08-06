"""
问答相关路由
"""
import json
import inspect
import os
import uuid
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.qa import QAConversation, QARecord, Favorite, FeedbackLog
from app.models.user import UserPreference
from app.services.rag_engine import get_rag_engine
from app.services.document_parser import parse_document

qa_bp = Blueprint("qa", __name__)

QA_ATTACHMENT_FOLDER = 'uploads/qa_attachments'
_TEXT_ATTACHMENT_EXTS = {'txt', 'md', 'markdown', 'html', 'htm', 'docx', 'doc', 'pdf', 'csv', 'json', 'xml', 'yaml', 'yml', 'log'}
_IMAGE_ATTACHMENT_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'}


def _safe_filename(filename: str) -> str:
    """清理上传文件名，仅保留基础名并移除空字节"""
    name = filename.replace('\\', '/').split('/')[-1].replace('\x00', '').strip()
    return name or 'unnamed_file'


def _save_qa_attachments(files) -> list:
    """保存问答附件，文本类附件提取内容供上下文使用"""
    if not files:
        return []
    upload_path = os.path.join(current_app.root_path, '..', QA_ATTACHMENT_FOLDER)
    os.makedirs(upload_path, exist_ok=True)
    attachments = []
    for file in files:
        if not file or not file.filename:
            continue
        display_name = _safe_filename(file.filename)
        ext = display_name.rsplit('.', 1)[-1].lower() if '.' in display_name else ''
        stored_name = f"{uuid.uuid4().hex[:8]}_{display_name}"
        filepath = os.path.join(upload_path, stored_name)
        file.save(filepath)
        entry = {
            "name": display_name,
            "type": "image" if ext in _IMAGE_ATTACHMENT_EXTS else ("text" if ext in _TEXT_ATTACHMENT_EXTS else "file"),
            "size": os.path.getsize(filepath),
            "text": ""
        }
        if ext in _TEXT_ATTACHMENT_EXTS:
            try:
                should_clean = ext not in ('html', 'htm', 'md', 'markdown', 'docx', 'doc', 'pdf')
                result = parse_document(filepath, clean_text=should_clean)
                entry["text"] = (result.get("content") or "")[:20000]
            except Exception:
                entry["text"] = ""
        attachments.append(entry)
    return attachments


def _sse_event(name: str, data: dict) -> str:
    """构造 SSE 事件文本"""
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _prepare_ask_inputs(user_id: int):
    """解析问题、会话、附件并组装引擎输入（ask / ask_stream 复用）"""
    payload = request.get_json(silent=True) or {}
    question = (request.form.get("question") or payload.get("question", "")).strip()
    conversation_id = request.form.get("conversation_id", type=int)
    if conversation_id is None:
        conversation_id = payload.get("conversation_id")

    # 处理附件：文本类附件提取内容注入上下文，图片附件记录名称
    attachments = []
    if request.files:
        attachments = _save_qa_attachments(request.files.getlist("files"))
    engine_query = question
    attachment_parts = []
    for att in attachments:
        if att.get("text"):
            attachment_parts.append(f"[附件] {att['name']}\n{att['text']}")
        elif att.get("type") == "image":
            attachment_parts.append(f"[图片附件] {att['name']}")
    if attachment_parts:
        engine_query = "用户上传了以下附件内容，请结合附件内容与知识库回答：\n\n" + \
            "\n\n".join(attachment_parts) + f"\n\n用户问题：{question}"

    # 获取会话历史
    conversation_history = []
    if conversation_id:
        conversation = QAConversation.query.filter_by(
            id=conversation_id,
            user_id=user_id
        ).first()
        if conversation:
            for record in conversation.records[-10:]:
                conversation_history.append({
                    "role": "user",
                    "content": record.question
                })
                if record.answer:
                    conversation_history.append({
                        "role": "assistant",
                        "content": record.answer
                    })

    preferences = UserPreference.query.filter_by(user_id=user_id).first()
    return question, conversation_id, engine_query, conversation_history, attachments, (preferences.to_dict() if preferences else None)


def _save_qa_record(user_id: int, conversation_id: int, question: str, result: dict, attachments: list) -> QARecord:
    """保存问答记录（ask / ask_stream 复用）"""
    record = QARecord(
        conversation_id=conversation_id,
        user_id=user_id,
        question=question,
        answer=result.get("answer"),
        sources=result.get("retrieved_docs") or result.get("sources"),
        confidence=result.get("confidence"),
        model_name=result.get("model_name"),
        response_time=result.get("response_time"),
        rag_warnings=result.get("rag_warnings") or None
    )
    db.session.add(record)
    db.session.commit()
    return record


def _engine_call(method, *args, user_id: int, **kwargs):
    """Pass user context to current engines while keeping legacy adapters usable."""
    try:
        supports_user_id = "user_id" in inspect.signature(method).parameters
    except (TypeError, ValueError):
        supports_user_id = True
    if supports_user_id:
        kwargs["user_id"] = user_id
    return method(*args, **kwargs)


@qa_bp.route("/ask", methods=["POST"])
@jwt_required()
def ask_question():
    """提交问题并获取答案"""
    user_id = get_jwt_identity()
    question, conversation_id, engine_query, conversation_history, attachments, preferences = _prepare_ask_inputs(user_id)

    if not question:
        return jsonify({"error": "问题不能为空"}), 400

    # 调用RAG引擎获取答案
    try:
        rag_engine = get_rag_engine()
        result = _engine_call(
            rag_engine.ask,
            engine_query,
            conversation_history,
            user_preferences=preferences,
            user_id=int(user_id),
        )
    except Exception as e:
        return jsonify({
            "error": f"生成答案失败: {str(e)}"
        }), 500

    # 保存问答记录
    record = _save_qa_record(user_id, conversation_id, question, result, attachments)

    return jsonify({
        "id": record.id,
        "question": question,
        "answer": result.get("answer"),
        "reasoning": result.get("reasoning"),
        "sources": result.get("retrieved_docs"),
        "confidence": result.get("confidence"),
        "response_time": result.get("response_time"),
        "rag_warnings": result.get("rag_warnings") or [],
        "attachments": attachments,
        "created_at": record.created_at.isoformat() if record.created_at else None
    }), 200


@qa_bp.route("/ask/stream", methods=["POST"])
@jwt_required()
def ask_question_stream():
    """流式提交问题并获取答案（SSE，ChatGPT 风格打字机输出）"""
    user_id = get_jwt_identity()
    question, conversation_id, engine_query, conversation_history, attachments, preferences = _prepare_ask_inputs(user_id)

    if not question:
        return jsonify({"error": "问题不能为空"}), 400

    rag_engine = get_rag_engine()

    def generate():
        try:
            for event in _engine_call(
                rag_engine.ask_stream,
                engine_query,
                conversation_history,
                user_preferences=preferences,
                user_id=int(user_id),
            ):
                if event["type"] in ("delta", "reasoning"):
                    yield _sse_event(event["type"], {"delta": event.get("content") or event.get("delta") or ""})
                elif event["type"] == "done":
                    record = _save_qa_record(user_id, conversation_id, question, event, attachments)
                    yield _sse_event("done", {
                        "id": record.id,
                        "answer": event.get("answer"),
                        "reasoning": event.get("reasoning"),
                        "sources": event.get("retrieved_docs") or event.get("sources") or [],
                        "confidence": event.get("confidence"),
                        "response_time": event.get("response_time"),
                        "attachments": attachments,
                        "created_at": record.created_at.isoformat() if record.created_at else None,
                        "warning_code": event.get("warning_code"),
                        "rag_warnings": event.get("rag_warnings") or [],
                    })
        except Exception:
            # 不向客户端泄漏内部实现细节
            yield _sse_event("error", {"error": "生成答案时发生异常，请稍后重试。"})

    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@qa_bp.route("/suggestions", methods=["GET"])
def get_suggestions():
    """获取追问建议"""
    query = request.args.get("q", "")
    
    if not query:
        return jsonify({"suggestions": []}), 200
    
    try:
        rag_engine = get_rag_engine()
        suggestions = rag_engine.get_suggested_questions(query)
    except Exception:
        suggestions = [
            f"能详细解释一下{query.split()[0] if query.split() else '这个'}概念吗？",
            f"{query}在实际场景中如何应用？",
            "有什么相关的安全案例？"
        ]
    
    return jsonify({"suggestions": suggestions}), 200


@qa_bp.route("/similar", methods=["GET"])
def get_similar_questions():
    """获取相似问题"""
    keyword = request.args.get("q", "")
    limit = request.args.get("limit", 5, type=int)
    
    if not keyword:
        return jsonify({"questions": []}), 200
    
    # 基于关键词搜索历史问答
    similar = QARecord.query.filter(
        QARecord.question.contains(keyword)
    ).order_by(QARecord.created_at.desc()).limit(limit).all()
    
    return jsonify({
        "questions": [{
            "id": r.id,
            "question": r.question,
            "answer_preview": r.answer[:200] + "..." if r.answer and len(r.answer) > 200 else r.answer,
            "created_at": r.created_at.isoformat() if r.created_at else None
        } for r in similar]
    }), 200


@qa_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    """获取问答历史"""
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    conversation_id = request.args.get("conversation_id", type=int)
    keyword = request.args.get("keyword", "")
    
    query = QARecord.query.filter_by(user_id=user_id)
    
    if conversation_id:
        query = query.filter_by(conversation_id=conversation_id)
    
    if keyword:
        query = query.filter(QARecord.question.contains(keyword))
    
    pagination = query.order_by(QARecord.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "records": [r.to_dict() for r in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages
    }), 200


@qa_bp.route("/<int:record_id>", methods=["GET"])
@jwt_required()
def get_record(record_id):
    """获取问答详情"""
    user_id = get_jwt_identity()
    
    record = QARecord.query.filter_by(
        id=record_id, 
        user_id=user_id
    ).first()
    
    if not record:
        return jsonify({"error": "记录不存在"}), 404
    
    return jsonify({"record": record.to_dict()}), 200


@qa_bp.route("/<int:record_id>/feedback", methods=["POST"])
@jwt_required()
def submit_feedback(record_id):
    """提交反馈"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    record = QARecord.query.filter_by(
        id=record_id, 
        user_id=user_id
    ).first()
    
    if not record:
        return jsonify({"error": "记录不存在"}), 404
    
    feedback_type = data.get("feedback")
    if feedback_type not in ["good", "neutral", "bad"]:
        return jsonify({"error": "无效的反馈类型"}), 400
    
    # 更新记录反馈
    record.feedback = feedback_type
    
    # 添加反馈日志
    log = FeedbackLog(
        qa_record_id=record_id,
        user_id=user_id,
        feedback_type=feedback_type,
        comment=data.get("comment")
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({"message": "反馈提交成功"}), 200


# ========== 会话管理 ==========

@qa_bp.route("/conversations", methods=["GET"])
@jwt_required()
def get_conversations():
    """获取会话列表"""
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    
    pagination = QAConversation.query.filter_by(user_id=user_id)\
        .filter_by(is_archived=False)\
        .order_by(QAConversation.updated_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "conversations": [c.to_dict() for c in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages
    }), 200


@qa_bp.route("/conversations", methods=["POST"])
@jwt_required()
def create_conversation():
    """创建新会话"""
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    
    conversation = QAConversation(
        user_id=user_id,
        title=data.get("title", "新会话")
    )
    db.session.add(conversation)
    db.session.commit()
    
    return jsonify({
        "message": "会话创建成功",
        "conversation": conversation.to_dict()
    }), 201


@qa_bp.route("/conversations/<int:conversation_id>", methods=["GET"])
@jwt_required()
def get_conversation(conversation_id):
    """获取会话详情（含问答记录）"""
    user_id = get_jwt_identity()

    conversation = QAConversation.query.filter_by(
        id=conversation_id,
        user_id=user_id
    ).first()

    if not conversation:
        return jsonify({"error": "会话不存在"}), 404

    # 获取用户的所有收藏
    user_favorites = {f.qa_record_id: f.id for f in Favorite.query.filter_by(user_id=user_id).all()}

    # 构建记录列表，包含收藏ID
    records = []
    for r in conversation.records:
        record_dict = r.to_dict()
        record_dict["favoriteId"] = user_favorites.get(r.id)
        records.append(record_dict)

    return jsonify({
        "conversation": {
            "id": conversation.id,
            "user_id": conversation.user_id,
            "title": conversation.title,
            "is_archived": conversation.is_archived,
            "record_count": len(conversation.records),
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            "records": records
        }
    }), 200


@qa_bp.route("/conversations/<int:conversation_id>", methods=["PUT"])
@jwt_required()
def update_conversation(conversation_id):
    """更新会话（如标题、归档）"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    conversation = QAConversation.query.filter_by(
        id=conversation_id,
        user_id=user_id
    ).first()
    
    if not conversation:
        return jsonify({"error": "会话不存在"}), 404
    
    if "title" in data:
        conversation.title = data["title"]
    if "is_archived" in data:
        conversation.is_archived = data["is_archived"]
    
    db.session.commit()
    
    return jsonify({
        "message": "会话更新成功",
        "conversation": conversation.to_dict()
    }), 200


@qa_bp.route("/conversations/<int:conversation_id>", methods=["DELETE"])
@jwt_required()
def delete_conversation(conversation_id):
    """删除会话"""
    user_id = get_jwt_identity()
    
    conversation = QAConversation.query.filter_by(
        id=conversation_id,
        user_id=user_id
    ).first()
    
    if not conversation:
        return jsonify({"error": "会话不存在"}), 404
    
    db.session.delete(conversation)
    db.session.commit()
    
    return jsonify({"message": "会话删除成功"}), 200


# ========== 收藏管理 ==========

@qa_bp.route("/favorites", methods=["GET"])
@jwt_required()
def get_favorites():
    """获取收藏列表"""
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    
    pagination = Favorite.query.filter_by(user_id=user_id)\
        .order_by(Favorite.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "favorites": [{
            "id": f.id,
            "qa_record": f.qa_record.to_dict() if f.qa_record else None,
            "created_at": f.created_at.isoformat() if f.created_at else None
        } for f in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages
    }), 200


@qa_bp.route("/favorites", methods=["POST"])
@jwt_required()
def add_favorite():
    """添加收藏"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    record_id = data.get("qa_record_id")
    if not record_id:
        return jsonify({"error": "请指定要收藏的问答记录"}), 400
    
    # 检查记录是否存在
    record = QARecord.query.get(record_id)
    if not record:
        return jsonify({"error": "问答记录不存在"}), 404
    
    # 检查是否已收藏
    existing = Favorite.query.filter_by(
        user_id=user_id,
        qa_record_id=record_id
    ).first()
    
    if existing:
        return jsonify({"error": "已经收藏过了"}), 400

    favorite = Favorite(user_id=user_id, qa_record_id=record_id)
    db.session.add(favorite)
    db.session.commit()

    return jsonify({
        "message": "收藏成功",
        "id": favorite.id
    }), 201


@qa_bp.route("/favorites/<int:favorite_id>", methods=["DELETE"])
@jwt_required()
def remove_favorite(favorite_id):
    """取消收藏"""
    user_id = get_jwt_identity()
    
    favorite = Favorite.query.filter_by(
        id=favorite_id,
        user_id=user_id
    ).first()
    
    if not favorite:
        return jsonify({"error": "收藏不存在"}), 404

    db.session.delete(favorite)
    db.session.commit()

    return jsonify({"message": "取消收藏成功"}), 200
