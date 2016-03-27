from storm.zope.schema import ZSchema


def createSchema():
    """Create the L{Schema} instance for a logs database."""
    from fluiddb.schema import logs as patches

    return ZSchema(CREATE, DROP, DELETE, patches)


CREATE = [
    """
    CREATE TABLE error_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT NOT NULL,
        message TEXT NOT NULL,
        exception_class TEXT,
        traceback TEXT)
    """,
    """
    CREATE TABLE status_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT NOT NULL,
        code INT NOT NULL,
        method TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        content_length INT NOT NULL,
        agent TEXT)
    """,

    """
    CREATE TABLE trace_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        duration TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        session_id TEXT NOT NULL)
    """
]


DROP = [
    'DROP TABLE error_lines',
    'DROP TABLE status_lines',
    'DROP TABLE trace_logs',
]


DELETE = [
    'DELETE FROM error_lines',
    'DELETE FROM status_lines',
    'DELETE FROM trace_logs',
]
