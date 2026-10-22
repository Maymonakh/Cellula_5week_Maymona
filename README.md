# Voice Data Analysis System (Cellula AI Engineering Internship)

Ask questions about your data **by voice** (Arabic or English).
The system turns your speech into text, writes the SQL query for you,
runs it on SQLite, and shows the result with a short explanation.

## How it works

```
Voice (microphone or audio file)
    |
Faster-Whisper (speech to text, Arabic + English)
    |
LLM writes a SQL query (from the question + the table structure)
    |
SQL validator (SELECT only, one statement, correct names)
    |-- not valid -> the LLM fixes the query (one more try)
    |
SQLite3 runs the query
    |
Result: table + chart + explanation (in the language of the question)
```

## Project structure

```
voice-data-analysis/
├── main.py                 # FastAPI app: all the endpoints
├── requirements.txt
├── sample_data/
│   └── sales.csv           # sample dataset for testing
├── static/
│   ├── index.html          # the web page
│   ├── style.css           # the design
│   └── script.js           # microphone, buttons, and results
└── src/
    ├── llm_config.py         # the LLM (OpenRouter)
    ├── speech_to_text.py     # Faster-Whisper
    ├── database.py           # loads CSV/Excel into SQLite and runs queries
    ├── sql_generator.py      # the LLM writes the SQL
    ├── sql_validator.py      # checks that the SQL is safe
    ├── explainer.py          # the LLM explains the result
    └── pipeline.py           # connects all the steps
```

## API endpoints

| Endpoint | What it does |
|---|---|
| `POST /datasets/upload` | upload a CSV or Excel file |
| `POST /datasets/sample` | load the sample sales dataset |
| `GET /datasets/{id}/schema` | show the table, columns, and sample rows |
| `POST /speech-to-text` | audio file -> text |
| `POST /generate-sql` | question -> SQL (not executed) |
| `POST /execute-sql` | check a SQL query and run it |
| `POST /analyze/text` | text question -> SQL -> result + explanation |
| `POST /analyze/voice` | voice -> text -> SQL -> result + explanation |

You can test every endpoint from `http://127.0.0.1:8000/docs`.

## How to run

1. `pip install -r requirements.txt`
2. `uvicorn main:app --reload`
3. Open `http://127.0.0.1:8000`

The first start downloads the Whisper model, so it takes a few minutes.

## Try these

1. Click **Use the sample sales dataset**.
2. "Show me total sales by category" -> table + chart.
3. "اعرض إجمالي المبيعات لكل فئة" -> same result, Arabic explanation.
4. Press the microphone and say: "Which region has the highest sales?"
5. `POST /execute-sql` with `DROP TABLE sales` -> error (only SELECT is allowed).
