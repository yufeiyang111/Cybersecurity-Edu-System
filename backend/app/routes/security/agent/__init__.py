"""Agent route package: durable runs and replayable event stream endpoints.

Importing this package registers the agent endpoints on the shared security
blueprint (runs.py and events.py must be imported for their decorators to run).
"""
from app.routes.security.agent import coverage as _coverage  # noqa: F401
from app.routes.security.agent import events as _events  # noqa: F401
from app.routes.security.agent import runs as _runs  # noqa: F401
