from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.database import create_dataset, get_schema, run_query
from src.pipeline import analyze_question
from src.speech_to_text import transcribe_audio
from src.sql_generator import generate_sql
from src.sql_validator import validate_sql


BASE_DIR = Path(__file__).resolve().parent
SAMPLE_FILE = BASE_DIR / "sample_data" / "sales.csv"

app = FastAPI(title="Voice Data Analysis API")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class QuestionRequest(BaseModel):
    dataset_id: str
    question: str


class SQLRequest(BaseModel):
    dataset_id: str
    sql: str


def raise_http_error(error):
    """Show the error in the terminal and send it to the user."""
    print("Error:", error)
    raise HTTPException(status_code=400, detail=str(error))


# Web page
@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


# Dataset input
@app.post("/datasets/upload")
def upload_dataset(file: UploadFile = File(...)):
    """Upload a CSV or Excel file."""
    try:
        file_bytes = file.file.read()

        if not file_bytes:
            raise ValueError("The file is empty.")

        dataset_id = create_dataset(file_bytes, file.filename or "data.csv")
        return {"dataset_id": dataset_id, "schema": get_schema(dataset_id)}

    except Exception as error:
        raise_http_error(error)


@app.post("/datasets/sample")
def use_sample_dataset():
    """Load the sample sales dataset (for testing)."""
    try:
        dataset_id = create_dataset(SAMPLE_FILE.read_bytes(), "sales.csv")
        return {"dataset_id": dataset_id, "schema": get_schema(dataset_id)}

    except Exception as error:
        raise_http_error(error)


@app.get("/datasets/{dataset_id}/schema")
def dataset_schema(dataset_id: str):
    """Show the table name, columns and sample rows."""
    try:
        return get_schema(dataset_id)

    except Exception as error:
        raise_http_error(error)


# Speech to text
@app.post("/speech-to-text")
def speech_to_text(audio: UploadFile = File(...), language: str = Form("")):
    """Upload audio, get the text. language: ar, en, or empty for auto."""
    try:
        audio_bytes = audio.file.read()

        if not audio_bytes:
            raise ValueError("The audio file is empty.")

        return transcribe_audio(audio_bytes, audio.filename, language or None)

    except Exception as error:
        raise_http_error(error)


# Text -> SQL
@app.post("/generate-sql")
def generate_sql_endpoint(request: QuestionRequest):
    """The LLM writes the SQL query (it is validated but NOT executed)."""
    try:
        schema = get_schema(request.dataset_id)
        sql = generate_sql(request.question, schema)

        if "CANNOT_ANSWER" in sql.upper():
            raise ValueError("This question cannot be answered from the dataset.")

        is_valid, message = validate_sql(sql, request.dataset_id)
        return {"sql": sql, "is_valid": is_valid, "message": message}

    except Exception as error:
        raise_http_error(error)


# Execute SQL
@app.post("/execute-sql")
def execute_sql(request: SQLRequest):
    """Validate a SQL query, then run it on SQLite."""
    try:
        is_valid, message = validate_sql(request.sql, request.dataset_id)

        if not is_valid:
            raise ValueError(message)

        result = run_query(request.dataset_id, request.sql)
        result["sql"] = request.sql
        result["row_count"] = len(result["rows"])
        return result

    except Exception as error:
        raise_http_error(error)


# Full pipeline
@app.post("/analyze/text")
def analyze_text(request: QuestionRequest):
    """Text question -> SQL -> result -> explanation."""
    try:
        return analyze_question(request.dataset_id, request.question)

    except Exception as error:
        raise_http_error(error)


@app.post("/analyze/voice")
def analyze_voice(
    dataset_id: str = Form(...),
    audio: UploadFile = File(...),
    language: str = Form("")
):
    """Voice -> Faster-Whisper -> text -> LLM -> SQL -> SQLite -> result."""
    try:
        audio_bytes = audio.file.read()

        if not audio_bytes:
            raise ValueError("The audio file is empty.")

        speech = transcribe_audio(audio_bytes, audio.filename, language or None)

        if not speech["text"]:
            raise ValueError("I could not hear any speech. Please try again.")

        result = analyze_question(dataset_id, speech["text"])
        result["transcription"] = speech["text"]
        result["detected_language"] = speech["language"]
        return result

    except Exception as error:
        raise_http_error(error)