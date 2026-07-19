"""
数据初始化脚本
用于导入示例数据和构建索引
"""
import sys
import os

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.knowledge import Category, KnowledgeItem, KnowledgeTag
from app.models.qa import QARecord, QAConversation, SuggestedQuestion
from app.sample_data import CATEGORIES, SAMPLE_KNOWLEDGE_ITEMS, SAMPLE_QA_RECORDS
from app.services.rag_engine import get_rag_engine
from app.services.data_processor import import_knowledge, build_knowledge_graph


def init_categories():
    """初始化分类"""
    print("正在初始化分类...")
    created = 0
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
            created += 1
        else:
            # 更新现有分类
            existing.name = cat_data["name"]
            existing.description = cat_data.get("description", "")
            existing.icon = cat_data.get("icon", "")
            existing.sort_order = cat_data.get("sort_order", 0)
    db.session.commit()
    print(f"  - 分类初始化完成，创建/更新 {len(CATEGORIES)} 个分类")


def init_knowledge_items():
    """初始化知识条目"""
    print("正在初始化知识条目...")
    created = 0
    updated = 0

    for item_data in SAMPLE_KNOWLEDGE_ITEMS:
        # 检查是否已存在
        existing = KnowledgeItem.query.filter_by(title=item_data["title"]).first()

        if existing:
            # 更新现有条目
            existing.content = item_data["content"]
            existing.summary = item_data["content"][:200] + "..."
            existing.category_id = item_data.get("category_id")
            existing.difficulty = item_data.get("difficulty", "medium")
            existing.source = item_data.get("source", "")
            existing.status = "published"
            updated += 1
        else:
            # 创建新条目
            item = KnowledgeItem(
                title=item_data["title"],
                content=item_data["content"],
                summary=item_data["content"][:200] + "...",
                category_id=item_data.get("category_id"),
                difficulty=item_data.get("difficulty", "medium"),
                source=item_data.get("source", ""),
                status="published",
                author_id=1  # 默认admin
            )
            db.session.add(item)
            db.session.flush()

            # 添加标签
            for tag_name in item_data.get("tags", []):
                tag = KnowledgeTag(knowledge_id=item.id, tag_name=tag_name)
                db.session.add(tag)

            created += 1

    db.session.commit()
    print(f"  - 知识条目完成，创建 {created} 个，更新 {updated} 个")


def init_vector_index():
    """初始化向量索引"""
    print("正在构建向量索引...")

    try:
        items = KnowledgeItem.query.filter_by(status="published").all()
        items_data = [
            {
                "id": item.id,
                "title": item.title,
                "content": item.content,
                "category_name": item.category.name if item.category else "",
                "source": item.source or "",
                "difficulty": item.difficulty,
                "tags": [kt.tag_name for kt in item.tags]
            }
            for item in items
        ]

        if items_data:
            result = import_knowledge(items_data)
            print(f"  - 向量索引完成，索引了 {result.get('vectors_indexed', 0)} 个文档")
        else:
            print("  - 没有找到已发布的知识条目")

    except Exception as e:
        print(f"  - 向量索引失败: {e}")


def init_knowledge_graph():
    """初始化知识图谱"""
    print("正在构建知识图谱...")

    try:
        items = KnowledgeItem.query.filter_by(status="published").all()
        items_data = [
            {
                "id": item.id,
                "title": item.title,
                "content": item.content,
                "category": item.category.name if item.category else "",
                "tags": [kt.tag_name for kt in item.tags]
            }
            for item in items
        ]

        if items_data:
            result = build_knowledge_graph(items_data)
            print(f"  - 知识图谱完成，添加了 {result.get('nodes_added', 0)} 个节点")
        else:
            print("  - 没有找到已发布的知识条目")

    except Exception as e:
        print(f"  - 知识图谱构建失败: {e}")


def init_suggested_questions():
    """初始化追问建议"""
    print("正在初始化追问建议...")

    suggestions = [
        ("SQL注入", ["SQL注入的原理是什么？", "如何预防SQL注入攻击？", "有哪些著名的SQL注入案例？"]),
        ("XSS攻击", ["XSS攻击有哪些类型？", "如何防止XSS攻击？", "CSP是什么？"]),
        ("CSRF", ["CSRF和XSS有什么区别？", "如何防范CSRF攻击？", "SameSite Cookie如何使用？"]),
        ("密码加密", ["什么是对称加密？", ["非对称加密的优缺点？", "AES和RSA哪个更安全？"]),
        ("渗透测试", ["渗透测试的流程是什么？", ["nmap有哪些常用命令？", "Metasploit如何使用？"]),
        ("应急响应", ["如何处理安全事件？", ["数字取证的基本流程？", ["如何进行溯源分析？"]]),
    ]

    created = 0
    for question, related in suggestions:
        existing = SuggestedQuestion.query.filter_by(question__contains=question[:20]).first()
        if not existing:
            sq = SuggestedQuestion(
                question=question,
                suggestions=related,
                category="网络安全"
            )
            db.session.add(sq)
            created += 1

    db.session.commit()
    print(f"  - 追问建议初始化完成，创建 {created} 个")


def run_init(include_index=True):
    """
    执行完整的初始化

    Args:
        include_index: 是否包含向量索引和知识图谱构建
    """
    app = create_app()

    with app.app_context():
        print("=" * 50)
        print("CyberGuard 数据初始化")
        print("=" * 50)

        init_categories()
        init_knowledge_items()

        if include_index:
            init_vector_index()
            init_knowledge_graph()

        init_suggested_questions()

        print("=" * 50)
        print("初始化完成！")
        print("=" * 50)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CyberGuard 数据初始化脚本")
    parser.add_argument("--skip-index", action="store_true", help="跳过向量索引和知识图谱构建")
    args = parser.parse_args()

    run_init(include_index=not args.skip_index)