"""
管理后台路由
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db
from app.models.user import User, Role
from app.models.knowledge import Category, KnowledgeItem, KnowledgeTag
from app.models.qa import QARecord, QAConversation, Favorite
from app.services.rag_engine import get_rag_engine
from app.services.vector_store import get_vector_store
from app.services.graph_store import get_knowledge_graph

admin_bp = Blueprint("admin", __name__)


def require_admin():
    """检查是否为管理员"""
    claims = get_jwt()
    role = claims.get("role", "guest")
    if role != "admin":
        return False
    return True


@admin_bp.route("/stats/overview", methods=["GET"])
@jwt_required()
def get_overview_stats():
    """
    获取系统概览统计
    ---
    tags:
      - 管理员
    security:
      - Bearer: []
    responses:
      200:
        description: 系统统计信息
        schema:
          type: object
          properties:
            users:
              type: object
              properties:
                total:
                  type: integer
                  description: 用户总数
                active:
                  type: integer
                  description: 活跃用户数
            knowledge:
              type: object
              properties:
                total:
                  type: integer
                published:
                  type: integer
            qa:
              type: object
              properties:
                total_questions:
                  type: integer
                total_conversations:
                  type: integer
            vector:
              type: object
              properties:
                count:
                  type: integer
                  description: 向量索引数量
            graph:
              type: object
              properties:
                node_count:
                  type: integer
                edge_count:
                  type: integer
    """
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403
    
    # 用户统计
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    
    # 知识库统计
    total_knowledge = KnowledgeItem.query.count()
    published_knowledge = KnowledgeItem.query.filter_by(status="published").count()
    
    # 问答统计
    total_questions = QARecord.query.count()
    total_conversations = QAConversation.query.count()
    
    # 向量库统计
    try:
        vector_store = get_vector_store()
        vector_count = vector_store.count()
    except Exception:
        vector_count = 0
    
    # 知识图谱统计
    try:
        graph = get_knowledge_graph()
        graph_stats = graph.get_statistics()
    except Exception:
        graph_stats = {"node_count": 0, "edge_count": 0}
    
    return jsonify({
        "users": {
            "total": total_users,
            "active": active_users
        },
        "knowledge": {
            "total": total_knowledge,
            "published": published_knowledge
        },
        "qa": {
            "total_questions": total_questions,
            "total_conversations": total_conversations
        },
        "vector": {
            "count": vector_count
        },
        "graph": graph_stats
    }), 200


@admin_bp.route("/stats/qa", methods=["GET"])
@jwt_required()
def get_qa_stats():
    """获取问答统计"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403
    
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # 最近7天的问答数量
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_qa = QARecord.query.filter(
        QARecord.created_at >= week_ago
    ).count()
    
    # 平均响应时间
    avg_response_time = db.session.query(
        func.avg(QARecord.response_time)
    ).filter(QARecord.response_time.isnot(None)).scalar() or 0
    
    # 反馈统计
    feedback_stats = db.session.query(
        QARecord.feedback,
        func.count(QARecord.id)
    ).group_by(QARecord.feedback).all()
    
    feedback = {"good": 0, "neutral": 0, "bad": 0}
    for fb_type, count in feedback_stats:
        if fb_type in feedback:
            feedback[fb_type] = count
    
    # 热门问题（按收藏数排序）
    hot_records = db.session.query(
        QARecord,
        func.count(Favorite.id).label("favorite_count")
    ).outerjoin(Favorite, QARecord.id == Favorite.qa_record_id
    ).group_by(QARecord.id
    ).order_by(func.count(Favorite.id).desc()
    ).limit(10).all()
    
    return jsonify({
        "recent_week": recent_qa,
        "avg_response_time": round(avg_response_time, 2),
        "feedback": feedback,
        "hot_records": [{
            "id": r.id,
            "question": r.question[:100],
            "favorite_count": fav_count,
            "feedback": r.feedback
        } for r, fav_count in hot_records]
    }), 200


@admin_bp.route("/users", methods=["GET"])
@jwt_required()
def get_users():
    """获取用户列表"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403
    
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    keyword = request.args.get("keyword", "")
    role = request.args.get("role", "")
    
    query = User.query
    
    if keyword:
        query = query.filter(
            db.or_(
                User.username.contains(keyword),
                User.email.contains(keyword),
                User.nickname.contains(keyword)
            )
        )
    
    if role:
        query = query.join(Role).filter(Role.name == role)
    
    pagination = query.order_by(User.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "users": [{
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "nickname": u.nickname,
            "role": u.role.name if u.role else "guest",
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None
        } for u in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages
    }), 200


@admin_bp.route("/users/<int:user_id>", methods=["PUT"])
@jwt_required()
def update_user(user_id):
    """更新用户（管理员操作）"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403
    
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if "is_active" in data:
        user.is_active = data["is_active"]
    if "role" in data:
        new_role = Role.query.filter_by(name=data["role"]).first()
        if new_role:
            user.role_id = new_role.id
    
    db.session.commit()
    
    return jsonify({
        "message": "用户更新成功",
        "user": user.to_dict()
    }), 200


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    """删除用户"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403
    
    current_user_id = get_jwt_identity()
    if user_id == current_user_id:
        return jsonify({"error": "不能删除自己"}), 400
    
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({"message": "用户删除成功"}), 200


@admin_bp.route("/knowledge/manage", methods=["GET"])
@jwt_required()
def get_all_knowledge():
    """获取所有知识（管理员视图）"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403
    
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    status = request.args.get("status", "")
    category_id = request.args.get("category_id", type=int)
    
    query = KnowledgeItem.query
    
    if status:
        query = query.filter_by(status=status)
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    pagination = query.order_by(KnowledgeItem.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "items": [item.to_dict() for item in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages
    }), 200


@admin_bp.route("/knowledge/<int:item_id>/audit", methods=["POST"])
@jwt_required()
def audit_knowledge(item_id):
    """审核知识条目"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403

    item = KnowledgeItem.query.get_or_404(item_id)
    data = request.get_json()

    action = data.get("action")  # approve, reject
    if action == "approve":
        item.status = "published"
    elif action == "reject":
        item.status = "archived"
    else:
        return jsonify({"error": "无效的审核操作"}), 400

    db.session.commit()

    return jsonify({
        "message": f"审核{action == 'approve' and '通过' or '拒绝'}成功",
        "item": item.to_dict()
    }), 200


@admin_bp.route("/knowledge/<int:item_id>", methods=["PUT"])
@jwt_required()
def update_knowledge(item_id):
    """更新知识条目"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403

    item = KnowledgeItem.query.get_or_404(item_id)
    data = request.get_json()

    # 更新允许的字段
    if "title" in data:
        item.title = data["title"]
    if "content" in data:
        item.content = data["content"]
        # 重新生成摘要
        if data["content"]:
            item.summary = data["content"][:200] + "..." if len(data["content"]) > 200 else data["content"]
    if "category_id" in data:
        item.category_id = data["category_id"]
    if "difficulty" in data:
        item.difficulty = data["difficulty"]
    if "status" in data:
        item.status = data["status"]
    if "source" in data:
        item.source = data["source"]

    db.session.commit()

    return jsonify({
        "message": "更新成功",
        "item": item.to_dict()
    }), 200


@admin_bp.route("/knowledge/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_knowledge(item_id):
    """删除知识条目"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403

    item = KnowledgeItem.query.get_or_404(item_id)

    # 删除关联的标签
    KnowledgeTag.query.filter_by(knowledge_id=item_id).delete()

    db.session.delete(item)
    db.session.commit()

    return jsonify({
        "message": "删除成功",
        "item_id": item_id
    }), 200


@admin_bp.route("/graph/stats", methods=["GET"])
@jwt_required()
def get_graph_stats():
    """获取知识图谱统计"""
    include_ranking = request.args.get("ranking", 0, type=int)
    try:
        graph = get_knowledge_graph()
        stats = graph.get_statistics()

        payload = {"stats": stats}

        # PageRank 计算开销大，仅在显式请求时计算
        if include_ranking:
            pagerank = graph.compute_pagerank()
            top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]
            payload["top_nodes"] = [{
                "node_id": node_id,
                "score": round(score, 4)
            } for node_id, score in top_nodes]

        return jsonify(payload), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/graph/nodes", methods=["GET"])
@jwt_required()
def get_graph_nodes():
    """获取图谱节点（用于可视化）"""
    limit = request.args.get("limit", 100, type=int)
    
    try:
        graph = get_knowledge_graph()
        nodes = []

        print(f"[DEBUG] get_graph_nodes: use_neo4j={graph.use_neo4j}, _nx_graph is None={graph._nx_graph is None}, _neo4j_graph driver={graph._neo4j_graph.driver if graph._neo4j_graph else None}")

        graph_data = graph.graph
        print(f"[DEBUG] graph_data type: {type(graph_data)}, nodes count: {len(graph_data.nodes())}")

        for node_id, data in list(graph_data.nodes(data=True))[:limit]:
            nodes.append({
                "id": node_id,
                "type": data.get("type", "unknown"),
                "title": data.get("title", node_id),
                "category": data.get("category", ""),
                "degree": graph_data.degree(node_id)
            })

        return jsonify({"nodes": nodes}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/graph/edges", methods=["GET"])
@jwt_required()
def get_graph_edges():
    """获取图谱边（用于可视化）"""
    limit = request.args.get("limit", 500, type=int)
    try:
        graph = get_knowledge_graph()
        edges = []

        print(f"[DEBUG] get_graph_edges: use_neo4j={graph.use_neo4j}, _nx_graph is None={graph._nx_graph is None}")

        graph_data = graph.graph
        print(f"[DEBUG] graph_data type: {type(graph_data)}, edges count: {len(graph_data.edges())}")

        for u, v, data in list(graph_data.edges(data=True))[:limit]:
            edges.append({
                "source": u,
                "target": v,
                "relation": data.get("relation", ""),
                "weight": data.get("weight", 1.0)
            })

        return jsonify({"edges": edges}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/graph/clear", methods=["DELETE"])
@jwt_required()
def clear_graph():
    """清空知识图谱"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403

    try:
        graph = get_knowledge_graph()
        graph.delete_all()
        return jsonify({"message": "图谱已清空"}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/graph/related/<node_id>", methods=["GET"])
@jwt_required()
def get_related_nodes(node_id):
    """获取节点关联信息"""
    depth = request.args.get("depth", 1, type=int)

    try:
        graph = get_knowledge_graph()

        # 获取节点信息
        if not graph.graph.has_node(node_id):
            return jsonify({"error": "节点不存在"}), 404

        node_data = graph.graph.nodes[node_id]
        node_type = node_data.get("type", "")
        node_title = node_data.get("title", "")
        source_item = node_data.get("source_item", "")

        # 如果是 Knowledge 节点，尝试获取完整内容
        knowledge_info = None
        knowledge_item_id = None

        if node_type == "knowledge":
            try:
                # 从数据库查询完整知识条目
                item_id = int(node_id)
                item = KnowledgeItem.query.get(item_id)
                if item:
                    knowledge_info = {
                        "id": item.id,
                        "title": item.title,
                        "content": item.content,
                        "summary": item.summary,
                        "category": item.category.name if item.category else "",
                        "tags": [tag.tag_name for tag in item.tags],
                        "difficulty": item.difficulty,
                        "source": item.source,
                        "view_count": item.view_count,
                        "created_at": item.created_at.isoformat() if item.created_at else None
                    }
            except Exception:
                pass

        # 获取邻居
        neighbors = graph.get_neighbors(node_id, depth=depth)

        # 为每个邻居添加详细信息
        enhanced_neighbors = []
        for neighbor in neighbors:
            neighbor_id = neighbor.get("node_id", "")
            neighbor_data = {
                "node_id": neighbor_id,
                "name": neighbor.get("name", ""),
                "type": neighbor.get("type", ""),
                "relation": neighbor.get("relation", ""),
                "distance": neighbor.get("distance", 1)
            }

            # 如果邻居是 Knowledge 节点，尝试获取完整信息
            if neighbor.get("type") == "knowledge":
                try:
                    item_id = int(neighbor_id)
                    item = KnowledgeItem.query.get(item_id)
                    if item:
                        neighbor_data["title"] = item.title
                        neighbor_data["summary"] = item.summary
                        neighbor_data["category"] = item.category.name if item.category else ""
                except Exception:
                    pass

            enhanced_neighbors.append(neighbor_data)

        return jsonify({
            "node": {
                "id": node_id,
                "type": node_type,
                "title": node_title,
                "source_item": source_item,
                "knowledge_item_id": int(source_item) if source_item and source_item.isdigit() else None,
                "properties": {k: v for k, v in node_data.items()
                             if k not in ["type", "title", "source_item"]},
                "knowledge_info": knowledge_info
            },
            "neighbors": enhanced_neighbors
        }), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/vector/rebuild", methods=["POST"])
@jwt_required()
def rebuild_vector_index():
    """重建向量索引"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403
    
    try:
        # 获取所有知识条目
        items = KnowledgeItem.query.filter_by(status="published").all()
        items_data = [item.to_dict() for item in items]
        
        # 重建索引
        rag_engine = get_rag_engine()
        result = rag_engine.index_knowledge(items_data)
        
        return jsonify({
            "message": "索引重建成功",
            "result": result
        }), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/roles", methods=["GET"])
@jwt_required()
def get_roles():
    """获取所有角色"""
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403
    
    roles = Role.query.all()

    return jsonify({
        "roles": [{
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "permissions": r.permissions,
            "user_count": len(r.users)
        } for r in roles]
    }), 200


@admin_bp.route("/data/init", methods=["POST"])
@jwt_required()
def init_sample_data():
    """
    初始化示例数据
    ---
    tags:
      - 管理员
    security:
      - Bearer: []
    responses:
      200:
        description: 初始化结果
      403:
        description: 权限不足
    """
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403

    from app.sample_data import CATEGORIES, SAMPLE_KNOWLEDGE_ITEMS
    from app.models.knowledge import Category, KnowledgeItem, KnowledgeTag, KnowledgeTag

    results = {
        "categories": {"created": 0, "updated": 0},
        "knowledge": {"created": 0, "updated": 0}
    }

    # 初始化分类
    for cat_data in CATEGORIES:
        existing = Category.query.filter_by(id=cat_data["id"]).first()
        if not existing:
            cat = Category(
                id=cat_data["id"],
                name=cat_data["name"],
                description=cat_data.get("description", ""),
                icon=cat_data.get("icon", ""),
                sort_order=cat_data.get("sort_order", 0)
            )
            db.session.add(cat)
            results["categories"]["created"] += 1
        else:
            existing.name = cat_data["name"]
            existing.description = cat_data.get("description", "")
            results["categories"]["updated"] += 1

    db.session.commit()

    # 初始化知识条目
    for item_data in SAMPLE_KNOWLEDGE_ITEMS:
        existing = KnowledgeItem.query.filter_by(title=item_data["title"]).first()
        if not existing:
            item = KnowledgeItem(
                title=item_data["title"],
                content=item_data["content"],
                summary=item_data["content"][:200] + "...",
                category_id=item_data.get("category_id"),
                difficulty=item_data.get("difficulty", "medium"),
                source=item_data.get("source", ""),
                status="published",
                author_id=1
            )
            db.session.add(item)
            db.session.flush()

            for tag_name in item_data.get("tags", []):
                tag = KnowledgeTag(knowledge_id=item.id, tag_name=tag_name)
                db.session.add(tag)

            results["knowledge"]["created"] += 1
        else:
            results["knowledge"]["updated"] += 1

    db.session.commit()

    return jsonify({
        "message": "示例数据初始化成功",
        "results": results
    }), 200


@admin_bp.route("/data/rebuild-index", methods=["POST"])
@jwt_required()
def rebuild_all_index():
    """
    重建所有索引（向量+知识图谱）
    ---
    tags:
      - 管理员
    security:
      - Bearer: []
    responses:
      200:
        description: 重建结果
      403:
        description: 权限不足
    """
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403

    try:
        rag_engine = get_rag_engine()

        # 获取所有已发布的知识
        items = KnowledgeItem.query.filter_by(status="published").all()
        items_data = [item.to_dict() for item in items]

        # 重建向量索引
        vector_result = rag_engine.index_knowledge(items_data)

        # 重建知识图谱
        from app.services.data_processor import build_knowledge_graph
        graph_result = build_knowledge_graph(items_data)

        return jsonify({
            "message": "索引重建成功",
            "vector_index": vector_result,
            "graph_index": graph_result
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/config", methods=["GET"])
@jwt_required()
def get_configs():
    """
    获取系统配置
    ---
    tags:
      - 管理员
    security:
      - Bearer: []
    responses:
      200:
        description: 系统配置列表
    """
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403

    from app.models.qa import SystemConfig

    configs = SystemConfig.query.all()

    return jsonify({
        "configs": [{
            "id": c.id,
            "config_key": c.config_key,
            "config_value": c.config_value,
            "description": c.description
        } for c in configs]
    }), 200


@admin_bp.route("/config/<key>", methods=["PUT"])
@jwt_required()
def update_config(key):
    """
    更新系统配置
    ---
    tags:
      - 管理员
    security:
      - Bearer: []
    parameters:
      - name: key
        in: path
        type: string
        required: true
        description: 配置键
    responses:
      200:
        description: 更新成功
      403:
        description: 权限不足
    """
    if not require_admin():
        return jsonify({"error": "权限不足"}), 403

    from app.models.qa import SystemConfig

    config = SystemConfig.query.filter_by(config_key=key).first()
    if not config:
        return jsonify({"error": "配置不存在"}), 404

    data = request.get_json()
    if "config_value" in data:
        config.config_value = data["config_value"]

    db.session.commit()

    return jsonify({
        "message": "配置更新成功",
        "config": {
            "id": config.id,
            "config_key": config.config_key,
            "config_value": config.config_value
        }
    }), 200
