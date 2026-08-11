"""
知识库管理路由
"""
import os
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from werkzeug.utils import secure_filename
from app import db
from app.models.knowledge import Category, KnowledgeItem, KnowledgeTag, KnowledgeFavorite
from app.models.qa import QARecord
from app.services.rag_engine import get_rag_engine
from app.services.document_parser import (
    DocumentParserFactory, TextCleaner, parse_document
)

knowledge_bp = Blueprint("knowledge", __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'html', 'htm', 'md', 'txt'}
UPLOAD_FOLDER = 'uploads/documents'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def check_permission(required_permission):
    """检查用户权限"""
    claims = get_jwt()
    role = claims.get("role", "guest")
    if role == "admin":
        return True
    if role == "teacher" and "knowledge" in required_permission:
        return True
    return False


@knowledge_bp.route("/categories", methods=["GET"])
def get_categories():
    """获取知识分类列表"""
    parent_id = request.args.get("parent_id", type=int)
    include_children = request.args.get("include_children", "true").lower() == "true"
    
    if parent_id is None:
        # 获取顶级分类
        categories = Category.query.filter_by(parent_id=None)\
            .order_by(Category.sort_order).all()
    else:
        categories = Category.query.filter_by(parent_id=parent_id)\
            .order_by(Category.sort_order).all()
    
    return jsonify({
        "categories": [
            cat.to_dict(include_children=include_children) 
            for cat in categories
        ]
    }), 200


@knowledge_bp.route("/categories/<int:category_id>", methods=["GET"])
def get_category(category_id):
    """获取分类详情"""
    category = Category.query.get_or_404(category_id)
    return jsonify({"category": category.to_dict(include_children=True)}), 200


@knowledge_bp.route("/categories", methods=["POST"])
@jwt_required()
def create_category():
    """创建知识分类"""
    if not check_permission("knowledge:create"):
        return jsonify({"error": "权限不足"}), 403
    
    data = request.get_json()
    
    if not data.get("name"):
        return jsonify({"error": "分类名称不能为空"}), 400
    
    category = Category(
        name=data["name"],
        description=data.get("description"),
        parent_id=data.get("parent_id"),
        icon=data.get("icon"),
        sort_order=data.get("sort_order", 0)
    )
    
    db.session.add(category)
    db.session.commit()
    
    return jsonify({
        "message": "分类创建成功",
        "category": category.to_dict()
    }), 201


@knowledge_bp.route("/categories/<int:category_id>", methods=["PUT"])
@jwt_required()
def update_category(category_id):
    """更新知识分类"""
    if not check_permission("knowledge:edit"):
        return jsonify({"error": "权限不足"}), 403
    
    category = Category.query.get_or_404(category_id)
    data = request.get_json()
    
    if "name" in data:
        category.name = data["name"]
    if "description" in data:
        category.description = data["description"]
    if "parent_id" in data:
        category.parent_id = data["parent_id"]
    if "icon" in data:
        category.icon = data["icon"]
    if "sort_order" in data:
        category.sort_order = data["sort_order"]
    
    db.session.commit()
    
    return jsonify({
        "message": "分类更新成功",
        "category": category.to_dict()
    }), 200


@knowledge_bp.route("/categories/<int:category_id>", methods=["DELETE"])
@jwt_required()
def delete_category(category_id):
    """删除知识分类"""
    if not check_permission("knowledge:delete"):
        return jsonify({"error": "权限不足"}), 403
    
    category = Category.query.get_or_404(category_id)
    
    # 检查是否有子分类或知识条目
    if category.children or category.items:
        return jsonify({"error": "请先删除子分类或知识条目"}), 400
    
    db.session.delete(category)
    db.session.commit()
    
    return jsonify({"message": "分类删除成功"}), 200


@knowledge_bp.route("", methods=["GET"])
def get_knowledge_list():
    """获取知识列表"""
    category_id = request.args.get("category_id", type=int)
    difficulty = request.args.get("difficulty")
    keyword = request.args.get("keyword")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    
    query = KnowledgeItem.query.filter_by(status="published")
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if keyword:
        query = query.filter(
            db.or_(
                KnowledgeItem.title.contains(keyword),
                KnowledgeItem.content.contains(keyword)
            )
        )
    
    pagination = query.order_by(KnowledgeItem.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "items": [item.to_dict(include_content=False) for item in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages
    }), 200


@knowledge_bp.route("/<int:item_id>", methods=["GET"])
def get_knowledge_item(item_id):
    """获取知识详情"""
    item = KnowledgeItem.query.get_or_404(item_id)
    
    # 增加浏览次数
    item.view_count += 1
    db.session.commit()
    
    return jsonify({"item": item.to_dict()}), 200


@knowledge_bp.route("", methods=["POST"])
@jwt_required()
def create_knowledge_item():
    """创建知识条目"""
    if not check_permission("knowledge:create"):
        return jsonify({"error": "权限不足"}), 403
    
    data = request.get_json()
    user_id = get_jwt_identity()
    
    if not data.get("title") or not data.get("content"):
        return jsonify({"error": "标题和内容不能为空"}), 400
    
    item = KnowledgeItem(
        title=data["title"],
        content=data["content"],
        summary=data.get("summary"),
        category_id=data.get("category_id"),
        difficulty=data.get("difficulty", "medium"),
        source=data.get("source"),
        author_id=user_id,
        status=data.get("status", "published")
    )
    
    db.session.add(item)
    db.session.flush()
    
    # 添加标签
    if data.get("tags"):
        for tag_name in data["tags"]:
            tag = KnowledgeTag(knowledge_id=item.id, tag_name=tag_name)
            db.session.add(tag)
    
    db.session.commit()
    
    # 更新向量索引
    try:
        rag_engine = get_rag_engine()
        rag_engine.index_knowledge([item.to_dict()])
    except Exception as e:
        print(f"索引更新失败: {e}")

    # 增量图谱索引（后台异步，只处理本文档）
    try:
        from app.services.kg.incremental_indexer import get_incremental_indexer
        get_incremental_indexer().on_knowledge_imported([item.to_dict()])
    except Exception as e:
        print(f"增量图谱索引失败: {e}")
    
    return jsonify({
        "message": "知识条目创建成功",
        "item": item.to_dict()
    }), 201


@knowledge_bp.route("/<int:item_id>", methods=["PUT"])
@jwt_required()
def update_knowledge_item(item_id):
    """更新知识条目"""
    if not check_permission("knowledge:edit"):
        return jsonify({"error": "权限不足"}), 403
    
    item = KnowledgeItem.query.get_or_404(item_id)
    data = request.get_json()
    
    if "title" in data:
        item.title = data["title"]
    if "content" in data:
        item.content = data["content"]
    if "summary" in data:
        item.summary = data["summary"]
    if "category_id" in data:
        item.category_id = data["category_id"]
    if "difficulty" in data:
        item.difficulty = data["difficulty"]
    if "source" in data:
        item.source = data["source"]
    if "status" in data:
        item.status = data["status"]
    
    # 更新标签
    if "tags" in data:
        KnowledgeTag.query.filter_by(knowledge_id=item.id).delete()
        for tag_name in data["tags"]:
            tag = KnowledgeTag(knowledge_id=item.id, tag_name=tag_name)
            db.session.add(tag)
    
    db.session.commit()
    
    # 重新索引
    try:
        rag_engine = get_rag_engine()
        rag_engine.index_knowledge([item.to_dict()])
    except Exception as e:
        print(f"索引更新失败: {e}")

    # 增量图谱索引（后台异步）
    try:
        from app.services.kg.incremental_indexer import get_incremental_indexer
        get_incremental_indexer().on_knowledge_imported([item.to_dict()])
    except Exception as e:
        print(f"增量图谱索引失败: {e}")
    
    return jsonify({
        "message": "知识条目更新成功",
        "item": item.to_dict()
    }), 200


@knowledge_bp.route("/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_knowledge_item(item_id):
    """删除知识条目（同步清理向量索引，避免已删内容仍被召回）"""
    if not check_permission("knowledge:delete"):
        return jsonify({"error": "权限不足"}), 403
    
    item = KnowledgeItem.query.get_or_404(item_id)
    
    db.session.delete(item)
    db.session.commit()
    
    # 同步删除向量索引（按 doc_id 清理全部块）
    try:
        from app.services.vector_stores.factory import get_vector_backend
        get_vector_backend().delete(where={"doc_id": str(item_id)})
    except Exception as e:
        print(f"向量索引删除失败 item={item_id}: {e}")

    # 同步清理图谱中的知识节点与孤儿实体（增量索引删除侧）
    try:
        from app.services.kg.incremental_indexer import get_incremental_indexer
        get_incremental_indexer().on_knowledge_deleted(str(item_id))
    except Exception as e:
        print(f"图谱节点清理失败 item={item_id}: {e}")
    
    return jsonify({"message": "知识条目删除成功"}), 200


@knowledge_bp.route("/import", methods=["POST"])
@jwt_required()
def import_knowledge():
    """批量导入知识"""
    if not check_permission("knowledge:create"):
        return jsonify({"error": "权限不足"}), 403
    
    data = request.get_json()
    items = data.get("items", [])
    user_id = get_jwt_identity()
    
    if not items:
        return jsonify({"error": "请提供要导入的知识条目"}), 400
    
    imported = []
    errors = []
    
    for i, item_data in enumerate(items):
        try:
            if not item_data.get("title") or not item_data.get("content"):
                errors.append({"index": i, "error": "标题或内容为空"})
                continue
            
            item = KnowledgeItem(
                title=item_data["title"],
                content=item_data["content"],
                summary=item_data.get("summary"),
                category_id=item_data.get("category_id"),
                difficulty=item_data.get("difficulty", "medium"),
                source=item_data.get("source"),
                author_id=user_id
            )
            db.session.add(item)
            db.session.flush()
            
            if item_data.get("tags"):
                for tag_name in item_data["tags"]:
                    tag = KnowledgeTag(knowledge_id=item.id, tag_name=tag_name)
                    db.session.add(tag)
            
            imported.append(item.to_dict())
        except Exception as e:
            errors.append({"index": i, "error": str(e)})
    
    db.session.commit()
    
    # 更新向量索引
    if imported:
        try:
            rag_engine = get_rag_engine()
            rag_engine.index_knowledge(imported)
        except Exception as e:
            print(f"批量索引失败: {e}")

    # 增量图谱索引（后台异步）
    if imported:
        try:
            from app.services.kg.incremental_indexer import get_incremental_indexer
            get_incremental_indexer().on_knowledge_imported(imported)
        except Exception as e:
            print(f"批量增量图谱索引失败: {e}")
    
    return jsonify({
        "message": f"成功导入 {len(imported)} 条知识",
        "imported": imported,
        "errors": errors
    }), 200


@knowledge_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_document():
    """上传并解析文档"""
    if not check_permission("knowledge:create"):
        return jsonify({"error": "权限不足"}), 403

    if 'file' not in request.files:
        return jsonify({"error": "没有文件"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "文件名为空"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "不支持的文件格式"}), 400

    # 创建上传目录
    upload_path = os.path.join(current_app.root_path, '..', UPLOAD_FOLDER)
    os.makedirs(upload_path, exist_ok=True)

    # 保存文件
    original_filename = file.filename
    # 保留原始文件名（支持中文），但做基本的安全处理
    filename = original_filename.replace('\\', '/').split('/')[-1]  # 只取最后一部分
    # 移除路径分隔符和空字节
    filename = filename.replace('\x00', '').strip()
    if not filename:
        filename = 'unnamed_file'

    filepath = os.path.join(upload_path, filename)
    print(f"DEBUG: 保存文件到: {filepath}")
    file.save(filepath)

    try:
        # 解析文档 - HTML/Markdown/Word/PDF不清理格式
        file_ext = filename.rsplit('.', 1)[-1].lower() if filename else ''
        should_clean = file_ext not in ['html', 'htm', 'md', 'markdown', 'docx', 'doc', 'pdf']
        print(f"DEBUG: 开始解析文件: {filepath}, ext={file_ext}, clean={should_clean}")
        result = parse_document(filepath, clean_text=should_clean)
        print(f"DEBUG: 解析完成, content长度={len(result.get('content', ''))}")

        # 提取元数据
        metadata = result.get("metadata", {})
        content = result.get("content", "")

        # 获取分类ID
        category_id = request.form.get('category_id', type=int)
        difficulty = request.form.get('difficulty', 'medium')
        source = request.form.get('source', result.get("source", filename))

        # 生成摘要
        summary = content[:200] + "..." if len(content) > 200 else content

        user_id = get_jwt_identity()

        # 创建知识条目
        item = KnowledgeItem(
            title=metadata.get("title", filename.rsplit('.', 1)[0]),
            content=content,
            summary=summary,
            category_id=category_id,
            difficulty=difficulty,
            source=source,
            author_id=user_id,
            status="published"
        )
        db.session.add(item)
        db.session.flush()

        # 自动提取标签（从标题和内容中）
        tags = extract_tags_from_content(content, metadata.get("title", ""))
        for tag_name in tags[:5]:  # 最多5个标签
            tag = KnowledgeTag(knowledge_id=item.id, tag_name=tag_name)
            db.session.add(tag)

        db.session.commit()

        # 更新向量索引
        try:
            rag_engine = get_rag_engine()
            rag_engine.index_knowledge([item.to_dict()])
        except Exception as e:
            print(f"索引更新失败: {e}")

        # 增量图谱索引（后台异步）
        try:
            from app.services.kg.incremental_indexer import get_incremental_indexer
            get_incremental_indexer().on_knowledge_imported([item.to_dict()])
        except Exception as e:
            print(f"增量图谱索引失败: {e}")

        return jsonify({
            "message": "文档上传成功",
            "item": item.to_dict(),
            "metadata": metadata
        }), 201

    except Exception as e:
        import traceback
        print(f"文档上传失败: {str(e)}")
        print(f"详细错误: {traceback.format_exc()}")
        return jsonify({"error": f"文档解析失败: {str(e)}"}), 500
    finally:
        # 清理上传的文件
        if os.path.exists(filepath):
            os.remove(filepath)


@knowledge_bp.route("/upload/batch", methods=["POST"])
@jwt_required()
def upload_documents_batch():
    """批量上传并解析文档"""
    if not check_permission("knowledge:create"):
        return jsonify({"error": "权限不足"}), 403

    if 'files' not in request.files:
        return jsonify({"error": "没有文件"}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({"error": "没有文件"}), 400

    category_id = request.form.get('category_id', type=int)
    difficulty = request.form.get('difficulty', 'medium')

    uploaded = []
    errors = []

    for file in files:
        if file.filename == '' or not allowed_file(file.filename):
            errors.append({"filename": file.filename, "error": "无效文件"})
            continue

        upload_path = os.path.join(current_app.root_path, '..', UPLOAD_FOLDER)
        os.makedirs(upload_path, exist_ok=True)

        filename = secure_filename(file.filename)
        filepath = os.path.join(upload_path, filename)

        try:
            file.save(filepath)
            file_ext = filename.rsplit('.', 1)[-1].lower() if filename else ''
            should_clean = file_ext not in ['html', 'htm', 'md', 'markdown', 'docx', 'doc', 'pdf']
            result = parse_document(filepath, clean_text=should_clean)
            metadata = result.get("metadata", {})
            content = result.get("content", "")

            if len(content) < 50:  # 内容太短跳过
                errors.append({"filename": filename, "error": "内容过短"})
                continue

            summary = content[:200] + "..." if len(content) > 200 else content
            user_id = get_jwt_identity()

            item = KnowledgeItem(
                title=metadata.get("title", filename.rsplit('.', 1)[0]),
                content=content,
                summary=summary,
                category_id=category_id,
                difficulty=difficulty,
                source=result.get("source", filename),
                author_id=user_id,
                status="published"
            )
            db.session.add(item)
            db.session.flush()

            tags = extract_tags_from_content(content, metadata.get("title", ""))
            for tag_name in tags[:5]:
                tag = KnowledgeTag(knowledge_id=item.id, tag_name=tag_name)
                db.session.add(tag)

            uploaded.append(item.to_dict())

        except Exception as e:
            errors.append({"filename": filename, "error": str(e)})
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    db.session.commit()

    # 批量索引
    if uploaded:
        try:
            rag_engine = get_rag_engine()
            rag_engine.index_knowledge(uploaded)
        except Exception as e:
            print(f"批量索引失败: {e}")

    return jsonify({
        "message": f"成功上传 {len(uploaded)} 个文档",
        "uploaded": uploaded,
        "errors": errors
    }), 200


def extract_tags_from_content(content, title=""):
    """从内容中提取标签"""
    import re
    tags = set()

    # 网络安全关键词
    security_keywords = [
        "SQL注入", "XSS", "CSRF", "SSRF", "webshell", "DDoS", "APT",
        "缓冲区溢出", "栈溢出", "堆溢出", "格式化字符串", "竞态条件",
        "密码学", "AES", "RSA", "DES", "SHA", "MD5", "加密", "解密",
        "防火墙", "入侵检测", "入侵防御", "VPN", "SSL", "TLS", "HTTPS",
        "渗透测试", "漏洞扫描", "代码审计", "逆向工程", "恶意软件",
        "僵尸网络", "蠕虫", "病毒", "木马", "后门", "Rootkit",
        "会话劫持", "中间人攻击", "钓鱼", "社会工程学",
        "Web安全", "网络安全", "系统安全", "应用安全", "数据安全",
        "身份认证", "访问控制", "权限管理", "安全协议"
    ]

    content_lower = (content + title).lower()

    for keyword in security_keywords:
        if keyword.lower() in content_lower:
            tags.add(keyword)

    # 提取英文术语作为标签
    english_terms = re.findall(r'\b([A-Z]{2,}[A-Za-z]*)\b', content)
    for term in english_terms[:5]:
        if len(term) > 2:
            tags.add(term)

    # 去重（大小写不敏感）：MySQL utf8mb4_0900_ai_ci 唯一索引忽略大小写，
    # 同一条目下 "JBOSS"/"JBoss" 这类变体会触发 unique_knowledge_tag 冲突
    unique_tags = []
    seen = set()
    for tag in tags:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            unique_tags.append(tag)

    return unique_tags[:10]


@knowledge_bp.route("/search", methods=["GET"])
def search_knowledge():
    """搜索知识"""
    keyword = request.args.get("q", "")
    category_id = request.args.get("category_id", type=int)
    tags = request.args.getlist("tags")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    
    query = KnowledgeItem.query.filter_by(status="published")
    
    if keyword:
        query = query.filter(
            db.or_(
                KnowledgeItem.title.contains(keyword),
                KnowledgeItem.content.contains(keyword)
            )
        )
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if tags:
        for tag in tags:
            query = query.filter(
                KnowledgeItem.id.in_(
                    db.session.query(KnowledgeTag.knowledge_id)
                    .filter(KnowledgeTag.tag_name == tag)
                )
            )
    
    pagination = query.order_by(KnowledgeItem.view_count.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "items": [item.to_dict(include_content=False) for item in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages
    }), 200


@knowledge_bp.route("/tags", methods=["GET"])
def get_all_tags():
    """获取所有标签"""
    tags = db.session.query(KnowledgeTag.tag_name)\
        .distinct()\
        .order_by(KnowledgeTag.tag_name)\
        .all()
    
    return jsonify({
        "tags": [tag[0] for tag in tags]
    }), 200


@knowledge_bp.route("/hot", methods=["GET"])
def get_hot_knowledge():
    """获取热门知识"""
    limit = request.args.get("limit", 10, type=int)

    items = KnowledgeItem.query.filter_by(status="published")\
        .order_by(KnowledgeItem.view_count.desc())\
        .limit(limit)\
        .all()

    return jsonify({
        "items": [item.to_dict(include_content=False) for item in items]
    }), 200


@knowledge_bp.route("/<int:item_id>/favorite", methods=["GET"])
@jwt_required()
def get_favorite_status(item_id):
    """获取收藏状态"""
    user_id = get_jwt_identity()
    favorite = KnowledgeFavorite.query.filter_by(
        user_id=user_id, knowledge_id=item_id
    ).first()

    return jsonify({
        "is_favorited": favorite is not None,
        "favorite_id": favorite.id if favorite else None
    }), 200


@knowledge_bp.route("/<int:item_id>/favorite", methods=["POST"])
@jwt_required()
def add_favorite(item_id):
    """添加收藏"""
    user_id = get_jwt_identity()

    item = KnowledgeItem.query.get_or_404(item_id)

    existing = KnowledgeFavorite.query.filter_by(
        user_id=user_id, knowledge_id=item_id
    ).first()

    if existing:
        return jsonify({"message": "已经收藏过了", "is_favorited": True}), 200

    favorite = KnowledgeFavorite(user_id=user_id, knowledge_id=item_id)
    db.session.add(favorite)

    item.favorite_count += 1
    db.session.commit()

    return jsonify({
        "message": "收藏成功",
        "is_favorited": True,
        "favorite_id": favorite.id,
        "favorite_count": item.favorite_count
    }), 201


@knowledge_bp.route("/<int:item_id>/favorite", methods=["DELETE"])
@jwt_required()
def remove_favorite(item_id):
    """取消收藏"""
    user_id = get_jwt_identity()

    item = KnowledgeItem.query.get_or_404(item_id)

    favorite = KnowledgeFavorite.query.filter_by(
        user_id=user_id, knowledge_id=item_id
    ).first()

    if not favorite:
        return jsonify({"message": "未收藏", "is_favorited": False}), 200

    db.session.delete(favorite)
    item.favorite_count = max(0, item.favorite_count - 1)
    db.session.commit()

    return jsonify({
        "message": "取消收藏成功",
        "is_favorited": False,
        "favorite_count": item.favorite_count
    }), 200


@knowledge_bp.route("/favorites", methods=["GET"])
@jwt_required()
def get_my_favorites():
    """获取我的收藏列表"""
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    query = KnowledgeItem.query.join(KnowledgeFavorite).filter(
        KnowledgeFavorite.user_id == user_id
    )

    pagination = query.order_by(KnowledgeFavorite.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [item.to_dict(include_content=False) for item in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages
    }), 200


@knowledge_bp.route("/<int:item_id>/related", methods=["GET"])
def get_related_knowledge(item_id):
    """获取相关知识推荐（混合算法：向量相似度+图谱关联+分类加成）"""
    item = KnowledgeItem.query.get_or_404(item_id)

    top_k = request.args.get("top_k", 5, type=int)

    try:
        rag_engine = get_rag_engine()

        # 构建知识条目字典
        item_dict = item.to_dict()

        # 使用RAG引擎的混合推荐算法
        related = rag_engine.find_related_knowledge(item_dict, top_k=top_k)

        # 获取完整的知识详情
        related_ids = [r["id"] for r in related]
        related_items = KnowledgeItem.query.filter(
            KnowledgeItem.id.in_(related_ids)
        ).all() if related_ids else []

        # 按RAG返回的顺序排序
        id_to_item = {str(it.id): it for it in related_items}
        ordered_items = []
        for r in related:
            it = id_to_item.get(r["id"])
            if it:
                item_data = it.to_dict(include_content=False)
                item_data["relevance_score"] = r["final_score"]
                item_data["relevance_reason"] = []
                if r.get("same_category"):
                    item_data["relevance_reason"].append("同分类")
                if r.get("common_tags"):
                    item_data["relevance_reason"].append(f"共享标签: {', '.join(r['common_tags'])}")
                if r.get("graph_relation"):
                    item_data["relevance_reason"].append(f"图谱关联: {r['graph_relation']}")
                ordered_items.append(item_data)

        return jsonify({
            "items": ordered_items,
            "total": len(ordered_items)
        }), 200

    except Exception as e:
        import traceback
        print(f"相关知识推荐失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")

        # 降级：使用简单的同分类推荐
        fallback_items = KnowledgeItem.query.filter(
            KnowledgeItem.category_id == item.category_id,
            KnowledgeItem.id != item_id,
            KnowledgeItem.status == "published"
        ).order_by(KnowledgeItem.view_count.desc()).limit(top_k).all()

        return jsonify({
            "items": [it.to_dict(include_content=False) for it in fallback_items],
            "total": len(fallback_items),
            "fallback": True
        }), 200


@knowledge_bp.route("/<int:item_id>/related-qa", methods=["GET"])
def get_related_qa(item_id):
    """获取与知识条目相关的问答记录"""
    item = KnowledgeItem.query.get_or_404(item_id)

    limit = request.args.get("limit", 5, type=int)

    # 获取知识条目的关键词（标题词 + 标签）
    keywords = []
    if item.title:
        # 提取标题中的关键词（简单分词）
        import re
        title_words = re.findall(r'[\u4e00-\u9fa5a-zA-Z]{2,}', item.title)
        keywords.extend(title_words[:5])
    if item.tags:
        keywords.extend([tag.tag_name for tag in item.tags])

    if not keywords:
        return jsonify({"questions": [], "reason": "无关键词"}), 200

    # 构建搜索条件：在问答记录中搜索相关关键词
    search_conditions = []
    for kw in keywords[:10]:
        search_conditions.append(QARecord.question.contains(kw))

    if not search_conditions:
        return jsonify({"questions": [], "reason": "无有效关键词"}), 200

    # 使用 OR 条件搜索
    query = QARecord.query.filter(db.or_(*search_conditions))

    # 按相关度排序（匹配次数）
    qa_records = query.order_by(QARecord.created_at.desc()).limit(limit * 2).all()

    # 计算每条记录与当前知识的匹配分数
    scored_records = []
    for qa in qa_records:
        score = 0
        matched_kws = []
        qa_text = (qa.question or "") + (qa.answer or "")
        for kw in keywords:
            if kw in (qa.question or ""):
                score += 3  # 标题匹配权重更高
                matched_kws.append(kw)
            elif kw in qa_text:
                score += 1
                matched_kws.append(kw)

        if matched_kws:
            scored_records.append({
                "id": qa.id,
                "question": qa.question,
                "answer_preview": (qa.answer[:200] + "..." if qa.answer and len(qa.answer) > 200 else qa.answer) if qa.answer else "暂无答案",
                "created_at": qa.created_at.isoformat() if qa.created_at else None,
                "score": score,
                "matched_keywords": list(set(matched_kws))[:5]
            })

    # 按分数排序
    scored_records.sort(key=lambda x: x["score"], reverse=True)

    return jsonify({
        "questions": scored_records[:limit],
        "total": len(scored_records[:limit])
    }), 200
