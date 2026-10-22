import re
import sqlite3

from src.database import open_database


# Words that change data or the database. We only allow reading (SELECT).
FORBIDDEN_WORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX"
]


def validate_sql(sql, dataset_id):
    """Check that the SQL is safe and correct. Returns (is_valid, message)."""
    sql = sql.strip().rstrip(";").strip()

    if sql == "":
        return False, "The SQL query is empty."

    # Remove the 'text values' so we only check the SQL itself
    sql_only = re.sub(r"'[^']*'", "", sql)

    # 1) Must be a SELECT query
    if not sql_only.upper().startswith("SELECT"):
        return False, "Only SELECT queries are allowed."

    # 2) Only one statement
    if ";" in sql_only:
        return False, "Only one SQL statement is allowed."

    # 3) No dangerous words
    for word in FORBIDDEN_WORDS:
        if re.search(rf"\b{word}\b", sql_only, re.IGNORECASE):
            return False, f"The word {word} is not allowed (read-only queries only)."

    # 4) No double quotes. SQLite treats a wrong "name" as plain text
    #    (no error), so we ask for names without quotes.
    if '"' in sql_only:
        return False, "Do not use double quotes. Write table and column names without quotes."

    # 5) Ask SQLite to check the syntax, table and column names
    #    (EXPLAIN only plans the query, it does not run it)
    connection = open_database(dataset_id)

    try:
        connection.execute("EXPLAIN QUERY PLAN " + sql)
    except sqlite3.Error as error:
        return False, f"SQL error: {error}"
    finally:
        connection.close()

    return True, "OK"