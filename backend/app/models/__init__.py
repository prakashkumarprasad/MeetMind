# Imports every model module so all tables register on Base.metadata for Celery tasks.

from app.models import user  # noqa: F401
from app.models import workspace  # noqa: F401
from app.models import meeting  # noqa: F401
from app.models import transcript_chunk  # noqa: F401
from app.models import chat  # noqa: F401
from app.models import action_item  # noqa: F401
