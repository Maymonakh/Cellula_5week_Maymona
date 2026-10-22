import re

from src.llm_config import llm


def schema_to_text(schema):
    """Turn the schema dictionary into text for the LLM prompt."""
    lines = [f"Table: {schema['table']} ({schema['row_count']} rows)", "Columns:"]

    for column in schema["columns"]:
        line = f"- {column['name']} ({column['type']})"

        if column["values"]:
            values = ", ".join(repr(value) for value in column["values"])
            line += f" possible values: {values}"

        lines.append(line)

    lines.append("Sample rows:")

    for row in schema["sample_rows"]:
        lines.append(str(tuple(row)))

    return "\n".join(lines)


def clean_sql(text):
    """Take only the SQL query from the LLM answer."""
    text = str(text).replace("```sql", "").replace("```", "").strip()

    # If the model wrote a sentence before the query, start from SELECT
    if not text.upper().startswith("SELECT") and "SELECT" in text.upper():
        text = text[text.upper().find("SELECT"):]

    text = re.sub(r"--[^\n]*", "", text)     # remove -- comments
    return text.rstrip(";").strip()


def generate_sql(question, schema):
    """Ask the LLM to write a SQL query for the question (Arabic or English)."""

    prompt = f"""
You are an expert SQLite data analyst.

Database schema:
{schema_to_text(schema)}

User question (it may be in Arabic or English):
{question}

Rules:
- Write ONE SQLite SELECT query that answers the question.
- Use only the table and columns shown above.
- Do NOT use double quotes. Write table and column names exactly as shown.
- The question may be in Arabic while the data is in English (or the opposite).
  Understand the meaning and use the exact values from the lists above.
- Give clear column names using AS (for example AS total_sales).
- For top / best / most questions, use ORDER BY with LIMIT.
- For detailed lists, add LIMIT 100.
- If the question cannot be answered with this table, reply exactly: CANNOT_ANSWER
- Return ONLY the SQL query, without any explanation.
"""

    response = llm.invoke(prompt)
    return clean_sql(response.content)


def fix_sql(question, schema, bad_sql, error):
    """Give the LLM the error message and ask for a corrected query."""

    prompt = f"""
You are an expert SQLite data analyst.

Database schema:
{schema_to_text(schema)}

User question:
{question}

The SQL query below failed.
SQL:
{bad_sql}

Problem:
{error}

Write a corrected SQLite SELECT query. Use only the table and columns
shown in the schema. Do NOT use double quotes.
Return ONLY the SQL query.
"""

    response = llm.invoke(prompt)
    return clean_sql(response.content)