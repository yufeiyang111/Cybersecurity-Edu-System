"""CyberGuard backend entrypoint."""

import os

import click

from app import create_app, db
from app.utils.database import seed_sample_data
from app.scripts.apply_sql_migration import apply_security_scanning_migration

app = create_app()


@app.cli.command("init-db")
def init_db_command() -> None:
    """Initialize database tables."""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")


@app.cli.command("seed-db")
def seed_db_command() -> None:
    """Seed sample data."""
    seed_sample_data(app)


@app.cli.command("init-all")
def init_all_command() -> None:
    """Initialize all backend data."""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")
        seed_sample_data(app)


@app.cli.command("apply-security-migrations")
def apply_security_migrations_command() -> None:
    """Apply the additive security-scanning schema migration once."""
    with app.app_context():
        applied = apply_security_scanning_migration()
        print("Security migration applied" if applied else "Security migration already applied")


@app.cli.command("rq-worker")
def rq_worker_command() -> None:
    """Run an RQ worker for asynchronous scan tasks."""
    from redis import Redis
    from rq import Queue, Worker

    queue = Queue(app.config["RQ_QUEUE_NAME"], connection=Redis.from_url(app.config["REDIS_URL"]))
    Worker([queue], connection=queue.connection).work()


@app.cli.command("memory-dream")
@click.option("--user-id", type=int, default=None, help="只整合指定用户的记忆（默认全部启用记忆的用户）")
@click.option("--dry-run", is_flag=True, help="只分析不执行（不写库、不落审计）")
def memory_dream_command(user_id: int | None, dry_run: bool) -> None:
    """Run Dream consolidation over persistent memories (synthesize/supersede/merge)."""
    from app.services.memory import memory_dream

    with app.app_context():
        result = memory_dream.run_dream(user_id=user_id, dry_run=dry_run)
        print(
            f"Dream {'dry-run' if dry_run else 'applied'}: "
            f"users={result['users']} operations={result['operations']} failures={result['failures']}"
        )


@app.cli.command("reindex-knowledge")
def reindex_knowledge_command() -> None:
    """Rebuild embedding collections (embedding model change) and reindex public knowledge."""
    from app.models.knowledge import KnowledgeItem
    from app.services.enhanced_rag_engine import get_rag_engine
    from app.services.secbert_embedding import get_embedding_service
    from app.services.vector_stores.contracts import (
        DEFAULT_COLLECTION_NAME,
        SECURITY_KNOWLEDGE_COLLECTION_NAME,
    )
    from app.services.vector_stores.factory import create_vector_backend

    with app.app_context():
        dimension = int(get_embedding_service().dimension)
        for collection_name in (DEFAULT_COLLECTION_NAME, SECURITY_KNOWLEDGE_COLLECTION_NAME):
            backend = create_vector_backend(collection_name=collection_name)
            deleted = backend.delete_all()
            print(
                f"collection '{collection_name}' rebuilt "
                f"(delete_all={deleted}, dim={dimension}, model={app.config['EMBEDDING_MODEL']})"
            )

        items = [
            item.to_dict()
            for item in KnowledgeItem.query.filter_by(status="published").all()
        ]
        result = get_rag_engine().index_knowledge(items)
        print(
            f"reindexed knowledge: {result['vector_indexed']}/{result['total']} "
            f"vectors, graph entities: {result['graph_indexed']}"
        )


if __name__ == "__main__":
    # 默认关闭热重载（FLASK_USE_RELOADER=1 开启）：Windows venv 重定向机制会让
    # reloader 子进程命令行显示为 base 解释器（如 D:\Python\python.exe run.py），
    # 造成"系统 Python 启动"的误判与进程树混乱。关闭后改代码需手动重启后端。
    use_reloader = os.getenv("FLASK_USE_RELOADER", "0") == "1"
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=bool(app.config.get("DEBUG", False)),
        use_reloader=use_reloader,
    )
