from __future__ import annotations


PROTOCOL_VERSION: int = 2

# Operations
OP_UPSERT_TASK = "upsert_task"
OP_UPSERT_TASKS_BATCH = "upsert_tasks_batch"
OP_SET_PHASE = "set_phase"
OP_REMOVE_TASK = "remove_task"
OP_MERGE_TASKS = "merge_tasks"
OP_GET_TASK = "get_task"
OP_LIST_TASKS_BRIEF = "list_tasks_brief"
OP_LIST_TASKS_FULL = "list_tasks_full"
OP_HEALTH = "health"

# Locked fold phases - phases where tasks cannot be folded into other tasks
LOCKED_FOLD_PHASES = ("active", "ready-to-merge", "pr-pending")

# Response fields
FIELD_OK = "ok"
FIELD_CONTENT = "content"
FIELD_HASH = "hash"
FIELD_ERROR_TYPE = "error_type"
FIELD_ERROR = "error"
FIELD_OP = "op"
FIELD_TOKEN = "token"
FIELD_PATH = "path"
FIELD_FILES = "files"
FIELD_MESSAGE = "message"
FIELD_BASE_HASH = "base_hash"
FIELD_NEW_CONTENT = "new_content"

# Error types
ERR_NOT_FOUND = "not_found"
ERR_CONFLICT = "conflict"
ERR_PUSH_FAILED = "push_failed"
ERR_PROTOCOL = "protocol_error"
ERR_AUTH = "auth_error"
ERR_PATH = "path_error"


class WikiError(Exception):
    """Base exception for all wiki module errors."""
    pass


class WikiNotFoundError(WikiError):
    """File or resource not found."""
    pass


class WikiConflictError(WikiError):
    """Concurrent write conflict detected."""
    pass


class WikiPushError(WikiError):
    """Git push operation failed."""
    pass


class WikiProtocolError(WikiError):
    """Protocol or message format error."""
    pass


class WikiStartupError(WikiError):
    """Wiki module initialization error."""
    pass


class WikiPathError(WikiError):
    """Invalid or problematic file path."""
    pass
