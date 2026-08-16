"""Agent route package: durable runs and replayable event stream endpoints.

Importing this package registers the agent endpoints on the shared security
blueprint (runs.py and events.py must be imported for their decorators to run).
"""
from app.routes.security.agent import approvals as _approvals  # noqa: F401
from app.routes.security.agent import conversations as _conversations  # noqa: F401
from app.routes.security.agent import coverage as _coverage  # noqa: F401
from app.routes.security.agent import events as _events  # noqa: F401
from app.routes.security.agent import flags as _flags  # noqa: F401
from app.routes.security.agent import graph as _graph  # noqa: F401
from app.routes.security.agent import hypotheses as _hypotheses  # noqa: F401
from app.routes.security.agent import observations as _observations  # noqa: F401
from app.routes.security.agent import observability as _observability  # noqa: F401
from app.routes.security.agent import providers as _providers  # noqa: F401
from app.routes.security.agent import runs as _runs  # noqa: F401
