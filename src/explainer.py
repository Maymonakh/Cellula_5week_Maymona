import re

from src.llm_config import llm


def is_arabic(text):
    """True if the text contains Arabic letters."""
    return bool(re.search(r"[\u0600-\u06FF]", text))


def explain_result(question, sql, result):
    """Ask the LLM to explain the result in the language of the question."""
    arabic = is_arabic(question)

    if not result["rows"]:
        if arabic:
            return "لم يتم العثور على نتائج لهذا السؤال."
        return "No results were found for this question."

    language = "Arabic" if arabic else "English"

    # Only the first 20 rows are sent to the LLM
    lines = [" | ".join(result["columns"])]

    for row in result["rows"][:20]:
        lines.append(" | ".join(str(value) for value in row))

    preview = "\n".join(lines)

    prompt = f"""
You are a data analyst explaining results to a non-technical user.

User question: {question}
SQL query used: {sql}

Result (first rows):
{preview}

Total rows returned: {len(result["rows"])}

Write a short explanation (2 to 4 sentences) in {language}.
- Mention the most important numbers.
- Use only the numbers shown above. Do not invent anything.
- Do not mention SQL.
"""

    try:
        return str(llm.invoke(prompt).content).strip()
    except Exception as error:
        print("Explanation error:", error)
        return ""          # the explanation is a bonus, so we do not fail