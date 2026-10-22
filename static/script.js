let datasetId = null;       
let currentSql = "";       
let busy = false;           

let mediaRecorder = null;   
let chunks = [];          
let timerId = null;
let startTime = 0;

function $(id) {
  return document.getElementById(id);
}

function setStatus(message, type = "") {
  $("statusText").textContent = message;
  document.querySelector(".status").className = "status " + type;
}

function setBusy(flag, message = "") {
  busy = flag;
  document.body.classList.toggle("busy", flag);  
  $("spinner").classList.toggle("hidden", !flag);

  if (flag) {
    setStatus(message);
  }
}

// 8240 -> "8,240" and null -> "NULL"
function formatValue(value) {
  if (value === null) return "NULL";
  if (typeof value === "number") return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(value);
}

// Send a request to the FastAPI server and return the JSON answer
async function callApi(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();

  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    throw new Error(detail);
  }

  return data;
}

function makeTable(columns, rows) {
  const table = document.createElement("table");
  const head = table.insertRow();

  columns.forEach(name => {
    const th = document.createElement("th");
    th.textContent = name;
    head.appendChild(th);
  });

  rows.forEach(row => {
    const tr = table.insertRow();

    row.forEach(value => {
      const cell = tr.insertCell();
      cell.textContent = formatValue(value);

      if (typeof value === "number") {
        cell.className = "number";
      }
    });
  });

  return table;
}

function makeChip(text, onClick = null) {
  const chip = document.createElement("span");
  chip.className = onClick ? "chip click" : "chip";
  chip.textContent = text;

  if (onClick) {
    chip.onclick = onClick;
  }

  return chip;
}


function exampleQuestions(schema) {
  if (schema.table === "sales") {
    return [
      "Show me total sales by category",
      "Which region has the highest sales?",
      "اعرض إجمالي المبيعات لكل فئة",
      "كم عدد الطلبات في كل منطقة؟"
    ];
  }

  return ["How many rows are there?", "Show the first 5 rows", "كم عدد الصفوف؟"];
}

function showDataset(data) {
  datasetId = data.dataset_id;
  const schema = data.schema;

  $("datasetBox").classList.remove("hidden");

  $("datasetChips").innerHTML = "";
  $("datasetChips").append(
    makeChip("Table: " + schema.table),
    makeChip(schema.row_count + " rows")
  );
  schema.columns.forEach(column => {
    $("datasetChips").appendChild(makeChip(column.name + " (" + column.type + ")"));
  });

  $("preview").innerHTML = "";
  $("preview").appendChild(makeTable(schema.columns.map(c => c.name), schema.sample_rows));

  $("examples").innerHTML = "";
  exampleQuestions(schema).forEach(text => {
    $("examples").appendChild(makeChip(text, () => {
      $("question").value = text;
      askText();
    }));
  });

  $("askCard").classList.remove("hidden");
  $("result").classList.add("hidden");
  setStatus("Dataset ready. Record or type your question!", "ok");
}

async function uploadFile() {
  const file = $("fileInput").files[0];

  if (!file || busy) return;

  const formData = new FormData();
  formData.append("file", file);

  setBusy(true, "Uploading...");

  try {
    showDataset(await callApi("/datasets/upload", { method: "POST", body: formData }));
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function useSample() {
  if (busy) return;

  setBusy(true, "Loading the sample dataset...");

  try {
    showDataset(await callApi("/datasets/sample", { method: "POST" }));
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function runRequest(url, options, message, onSuccess = null) {
  if (busy) return;

  setBusy(true, message);

  try {
    const data = await callApi(url, options);

    if (onSuccess) onSuccess(data);

    showResult(data);
    setStatus("Done ✓", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

function askText() {
  const question = $("question").value.trim();

  if (!question || !datasetId) return;

  runRequest(
    "/analyze/text",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_id: datasetId, question: question })
    },
    "Writing the SQL query and analyzing..."
  );
}

async function toggleRecording() {
  const button = $("recordButton");

  // Second click = stop recording
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    return;
  }

  if (busy) return;

  if (!navigator.mediaDevices) {
    setStatus("The microphone needs http://127.0.0.1:8000 or localhost.", "error");
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    chunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = event => chunks.push(event.data);

    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(track => track.stop());   // turn the microphone off
      clearInterval(timerId);
      button.textContent = "🎤";
      button.classList.remove("recording");
      $("timer").textContent = "Tap to speak";
      sendAudio();
    };

    mediaRecorder.start();
    button.textContent = "⏹";
    button.classList.add("recording");
    setStatus("Recording... press the button again to stop.");

    startTime = Date.now();
    timerId = setInterval(() => {
      const seconds = Math.floor((Date.now() - startTime) / 1000);
      $("timer").textContent = "Recording " + Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
    }, 500);

  } catch (error) {
    setStatus("Cannot use the microphone: " + error.message, "error");
  }
}

function sendAudio() {
  const blob = new Blob(chunks, { type: mediaRecorder.mimeType });

  if (blob.size < 2000) {
    setStatus("The recording is too short. Please try again.", "error");
    return;
  }

  let extension = "webm";
  if (blob.type.includes("ogg")) extension = "ogg";
  if (blob.type.includes("mp4")) extension = "mp4";

  const formData = new FormData();
  formData.append("dataset_id", datasetId);
  formData.append("language", document.querySelector('input[name="language"]:checked').value);
  formData.append("audio", blob, "recording." + extension);

  runRequest(
    "/analyze/voice",
    { method: "POST", body: formData },
    "Converting your voice to text, then analyzing...",
    data => { $("question").value = data.transcription; }   // show what Whisper heard
  );
}


function showResult(data) {
  currentSql = data.sql;

  $("result").classList.remove("hidden");

  // what the user said (voice) or typed (text)
  $("questionText").textContent = (data.transcription ? "🗣️ " : "💬 ") + (data.transcription || data.question);

  $("langBadge").textContent = data.detected_language || "";
  $("langBadge").classList.toggle("hidden", !data.detected_language);

  $("explanation").textContent = data.explanation;
  $("explanation").classList.toggle("hidden", !data.explanation);

  $("resultTable").innerHTML = "";
  $("resultTable").appendChild(makeTable(data.columns, data.rows));

  $("rowCount").textContent = data.row_count + (data.row_count === 1 ? " row" : " rows");

  $("sql").textContent = data.sql;

  drawBars(data);

  $("result").scrollIntoView({ behavior: "smooth" });
}

function drawBars(data) {
  const box = $("chart");
  box.innerHTML = "";

  const values = data.rows.map(row => row[1]);

  if (data.columns.length !== 2 || values.length < 2 || values.length > 20) return;
  if (!values.every(value => typeof value === "number")) return;

  const max = Math.max(...values);

  if (max <= 0) return;

  const bars = [];

  data.rows.forEach(row => {
    const line = document.createElement("div");
    line.className = "bar-row";

    const label = document.createElement("div");
    label.className = "bar-label";
    label.textContent = row[0];

    const track = document.createElement("div");
    track.className = "bar-track";

    const bar = document.createElement("div");
    bar.className = "bar";
    track.appendChild(bar);
    bars.push([bar, row[1] / max * 100]);

    const value = document.createElement("div");
    value.className = "bar-value";
    value.textContent = formatValue(row[1]);

    line.append(label, track, value);
    box.appendChild(line);
  });

  setTimeout(() => bars.forEach(([bar, percent]) => bar.style.width = percent + "%"), 50);
}

async function copySql() {
  try {
    await navigator.clipboard.writeText(currentSql);
    setStatus("SQL copied ✓", "ok");
  } catch (error) {
    setStatus("Could not copy. Open the SQL section and copy it by hand.", "error");
  }
}