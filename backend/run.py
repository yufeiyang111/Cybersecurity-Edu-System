"""CyberGuard backend entrypoint."""

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


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=bool(app.config.get("DEBUG", False)),
    )
