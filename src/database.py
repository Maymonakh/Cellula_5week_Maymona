import re
import sqlite3
import uuid
from io import BytesIO
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DB_FOLDER = BASE_DIR / "databases"
DB_FOLDER.mkdir(exist_ok=True)

MAX_ROWS = 200      # the most rows we send back to the user

# These words cannot be used as names in SQL without quotes
RESERVED_WORDS = ["select", "from", "where", "order", "group", "table", "index", "key", "values", "limit", "default"]


def clean_name(name):
    """Make a simple table / column name (Arabic letters are allowed)."""
    name = re.sub(r"\W+", "_", str(name).strip()).strip("_")

    if name == "" or name[0].isdigit() or name.lower() in RESERVED_WORDS:
        name = "col_" + name

    return name


def open_database(dataset_id):
    """Open the SQLite file of a dataset (every dataset has its own file)."""
    if not dataset_id.isalnum():
        raise ValueError("Invalid dataset id.")

    path = DB_FOLDER / f"{dataset_id}.db"

    if not path.exists():
        raise FileNotFoundError("Dataset not found. Please upload a dataset first.")

    return sqlite3.connect(path)


def read_dataframe(file_bytes, filename):
    """Read a CSV or Excel file into a pandas DataFrame."""
    extension = Path(filename).suffix.lower()

    if extension == ".csv":
        try:
            return pd.read_csv(BytesIO(file_bytes), encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(BytesIO(file_bytes), encoding="cp1256")     # Arabic Windows files

    if extension == ".xlsx":
        return pd.read_excel(BytesIO(file_bytes))

    raise ValueError("Only .csv and .xlsx files are supported.")


def create_dataset(file_bytes, filename):
    """Load a file into a new SQLite database and return its dataset_id."""
    try:
        df = read_dataframe(file_bytes, filename)
    except pd.errors.EmptyDataError:
        raise ValueError("The file is empty.")

    if df.empty:
        raise ValueError("The file has no data.")

    # Clean the column names and make sure they are unique
    new_columns = []

    for column in df.columns:
        name = clean_name(column)

        while name in new_columns:
            name += "_2"

        new_columns.append(name)

    df.columns = new_columns

    table_name = clean_name(Path(filename).stem)
    dataset_id = uuid.uuid4().hex[:8]

    connection = sqlite3.connect(DB_FOLDER / f"{dataset_id}.db")
    df.to_sql(table_name, connection, index=False)
    connection.close()

    return dataset_id


def get_schema(dataset_id):
    """Return the table name, columns, types, and a few sample rows."""
    connection = open_database(dataset_id)

    try:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchone()[0]

        row_count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

        columns = []

        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall():
            name = row[1]
            column_type = row[2]

            # For text columns with few different values, we save the values.
            # This helps the LLM match Arabic words with the real values.
            values = []

            if column_type == "TEXT":
                found = connection.execute(
                    f'SELECT DISTINCT "{name}" FROM "{table}" LIMIT 16'
                ).fetchall()

                if len(found) <= 15:
                    values = [item[0] for item in found if item[0] is not None]

            columns.append({"name": name, "type": column_type, "values": values})

        sample_rows = connection.execute(f'SELECT * FROM "{table}" LIMIT 3').fetchall()

    finally:
        connection.close()

    return {
        "table": table,
        "row_count": row_count,
        "columns": columns,
        "sample_rows": [list(row) for row in sample_rows]
    }


def run_query(dataset_id, sql):
    """Run a SELECT query with sqlite3 and return the columns and rows."""
    connection = open_database(dataset_id)

    try:
        cursor = connection.execute(sql)
        columns = [item[0] for item in cursor.description]
        rows = cursor.fetchmany(MAX_ROWS)
    finally:
        connection.close()

    return {"columns": columns, "rows": [list(row) for row in rows]}