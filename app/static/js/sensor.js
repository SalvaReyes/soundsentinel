const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");
const statusText = document.getElementById("statusText");
const statusDetail = document.getElementById("statusDetail");
const deviceKeyInput = document.getElementById("deviceKey");
const intervalInput = document.getElementById("intervalSeconds");
const maxSizeInput = document.getElementById("maxSizeMb");
const chatIdInput = document.getElementById("chatId");
const chatLabelInput = document.getElementById("chatLabel");
const adminTokenInput = document.getElementById("adminToken");
const saveChatButton = document.getElementById("saveChatButton");
const chatStatus = document.getElementById("chatStatus");

let audioContext;
let mediaStream;
let processor;
let sourceNode;
let chunkTimer;
let samples = [];
let isRunning = false;

function setStatus(text, detail) {
  statusText.textContent = text;
  statusDetail.textContent = detail || "";
}

function setChatStatus(text) {
  chatStatus.textContent = text;
}

function clampInterval(value) {
  const parsed = Number(value || 5);
  if (Number.isNaN(parsed)) return 5;
  return Math.min(30, Math.max(2, parsed));
}

function toWavBlob(floatSamples, sampleRate) {
  const pcm16 = new Int16Array(floatSamples.length);
  for (let i = 0; i < floatSamples.length; i += 1) {
    const s = Math.max(-1, Math.min(1, floatSamples[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }

  const buffer = new ArrayBuffer(44 + pcm16.length * 2);
  const view = new DataView(buffer);

  function writeString(offset, text) {
    for (let i = 0; i < text.length; i += 1) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  }

  writeString(0, "RIFF");
  view.setUint32(4, 36 + pcm16.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, pcm16.length * 2, true);

  let offset = 44;
  for (let i = 0; i < pcm16.length; i += 1) {
    view.setInt16(offset, pcm16[i], true);
    offset += 2;
  }

  return new Blob([view], { type: "audio/wav" });
}

async function sendChunk(blob, deviceKey) {
  const form = new FormData();
  form.append("device_key", deviceKey);
  form.append("captured_at", new Date().toISOString());
  form.append("audio_file", blob, "chunk.wav");

  const response = await fetch("/api/v1/audio/ingestions", {
    method: "POST",
    body: form,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }

  return response.json();
}

async function registerChatId() {
  const chatId = chatIdInput.value.trim();
  const label = chatLabelInput.value.trim();
  const adminToken = adminTokenInput.value.trim();

  if (!chatId) {
    setChatStatus("Chat ID is required.");
    return;
  }

  if (!adminToken) {
    setChatStatus("Admin token is required.");
    return;
  }

  const form = new FormData();
  form.append("chat_id", chatId);
  form.append("label", label);
  form.append("admin_token", adminToken);

  try {
    setChatStatus("Saving chat ID...");
    const response = await fetch("/api/v1/notifications/telegram/recipients", {
      method: "POST",
      body: form,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }

    const payload = await response.json();
    setChatStatus(
      payload.created
        ? "Chat ID registered successfully."
        : "Chat ID updated successfully."
    );
  } catch (error) {
    setChatStatus(error.message || "Failed to register chat ID.");
  }
}

async function flushSamples() {
  if (!isRunning || samples.length === 0) {
    return;
  }

  const sampleRate = audioContext.sampleRate;
  const chunk = samples;
  samples = [];

  const blob = toWavBlob(chunk, sampleRate);
  const maxSizeBytes = Number(maxSizeInput.value || 2) * 1024 * 1024;

  if (blob.size > maxSizeBytes) {
    setStatus(
      "Chunk too large",
      `Chunk ${Math.round(blob.size / 1024)} KB is above the limit.`
    );
    return;
  }

  const deviceKey = deviceKeyInput.value.trim();
  if (!deviceKey) {
    setStatus("Missing device key", "Please set a device key before starting.");
    stopSensor();
    return;
  }

  try {
    setStatus("Sending", "Uploading audio chunk...");
    const result = await sendChunk(blob, deviceKey);
    setStatus(
      "Running",
      `Sent ${Math.round(blob.size / 1024)} KB · Alerts: ${result.alerts.length}`
    );
  } catch (error) {
    setStatus("Error", error.message || "Failed to send audio chunk.");
  }
}

async function startSensor() {
  if (isRunning) return;

  const intervalSeconds = clampInterval(intervalInput.value);
  intervalInput.value = intervalSeconds;

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (error) {
    setStatus("Mic denied", "Please allow microphone access.");
    return;
  }

  audioContext = new (window.AudioContext || window.webkitAudioContext)();
  sourceNode = audioContext.createMediaStreamSource(mediaStream);
  processor = audioContext.createScriptProcessor(4096, 1, 1);

  processor.onaudioprocess = (event) => {
    const input = event.inputBuffer.getChannelData(0);
    for (let i = 0; i < input.length; i += 1) {
      samples.push(input[i]);
    }
  };

  sourceNode.connect(processor);
  processor.connect(audioContext.destination);

  chunkTimer = setInterval(flushSamples, intervalSeconds * 1000);
  isRunning = true;
  startButton.disabled = true;
  stopButton.disabled = false;
  setStatus("Running", "Capturing audio and waiting for first upload...");
}

function stopSensor() {
  if (!isRunning) return;

  clearInterval(chunkTimer);
  chunkTimer = null;

  if (processor) {
    processor.disconnect();
    processor.onaudioprocess = null;
  }

  if (sourceNode) {
    sourceNode.disconnect();
  }

  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
  }

  if (audioContext) {
    audioContext.close();
  }

  samples = [];
  isRunning = false;
  startButton.disabled = false;
  stopButton.disabled = true;
  setStatus("Idle", "Sensor stopped.");
}

startButton.addEventListener("click", () => {
  startSensor();
});

stopButton.addEventListener("click", () => {
  stopSensor();
});

saveChatButton.addEventListener("click", () => {
  registerChatId();
});
