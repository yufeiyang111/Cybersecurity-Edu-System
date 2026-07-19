"""
问答相关路由
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.qa import QAConversation, QARecord, Favorite, FeedbackLog
from app.services.rag_engine import get_rag_engine
import json

qa_bp = Blueprint("qa", __name__)


@qa_bp.route("/ask", methods=["POST"])
@jwt_required()
def ask_question():
    """提交问题并获取答案"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    question = data.get("question", "").strip()
    conversation_id = data.get("conversation_id")
    
    if not question:
        return jsonify({"error": "问题不能为空"}), 400
    
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
    
    # 调用RAG引擎获取答案
    try:
        rag_engine = get_rag_engine()
        result = rag_engine.ask(question, conversation_history)
    except Exception as e:
        return jsonify({
            "error": f"生成答案失败: {str(e)}"
        }), 500
    
    # 保存问答记录
    record = QARecord(
        conversation_id=conversation_id,
        user_id=user_id,
        question=question,
        answer=result.get("answer"),
        sources=result.get("retrieved_docs"),
        confidence=result.get("confidence"),
        model_name=result.get("model_name"),
        response_time=result.get("response_time")
    )
    db.session.add(record)
    db.session.commit()
    
    return jsonify({
        "id": record.id,
        "question": question,
        "answer": result.get("answer"),
        "sources": result.get("retrieved_docs"),
        "confidence": result.get("confidence"),
        "response_time": result.get("response_time"),
        "created_at": record.created_at.isoformat() if record.created_at else None
    }), 200


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
