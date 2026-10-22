from src.database import get_schema, run_query
from src.explainer import explain_result, is_arabic
from src.sql_generator import fix_sql, generate_sql
from src.sql_validator import validate_sql


def analyze_question(dataset_id, question):
    """Text -> LLM -> SQL -> validate -> SQLite -> result + explanation."""

    question = question.strip()

    if question == "":
        raise ValueError("The question is empty.")

    schema = get_schema(dataset_id)

    # Step 1: the LLM writes the SQL
    sql = generate_sql(question, schema)

    if "CANNOT_ANSWER" in sql.upper():
        raise ValueError("This question cannot be answered from the dataset.")

    # Step 2: check the SQL. If it is wrong, the LLM fixes it (one more try)
    is_valid, message = validate_sql(sql, dataset_id)

    if not is_valid:
        sql = fix_sql(question, schema, sql, message)
        is_valid, message = validate_sql(sql, dataset_id)

        if not is_valid:
            raise ValueError("Could not create a valid SQL query. " + message)

    # Step 3: run the SQL on SQLite
    result = run_query(dataset_id, sql)

    # Step 4: explain the result
    return {
        "question": question,
        "language": "ar" if is_arabic(question) else "en",
        "sql": sql,
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": len(result["rows"]),
        "explanation": explain_result(question, sql, result)
    }