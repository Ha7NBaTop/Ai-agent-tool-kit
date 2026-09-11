from .path_guard import Denied

WRITER_TOOLS = {"list_files", "read_file", "search_text", "create_file", "replace_text", "run_check"}


def require_tool(role, name):
    if role != "writer" or name not in WRITER_TOOLS:
        raise Denied("tool denied for role")
