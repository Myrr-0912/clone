const state = {
  cloneId: null,
  chatMode: "text",
  savedVoiceSampleNames: [],
  recordedVoiceFiles: [],
  recorder: null,
  recordedChunks: [],
  recordingStream: null,
  voiceStatusPollTimer: null,
};

const text = {
  fillRequired: "\u8bf7\u8865\u5168\u540d\u79f0\u548c\u804a\u5929\u6587\u672c\u3002",
  training: "\u6b63\u5728\u8bad\u7ec3\u753b\u50cf\u5e76\u4fdd\u5b58\u672c\u5730\u6587\u4ef6...",
  trainFailed: "\u8bad\u7ec3\u5931\u8d25",
  trained: "\u8bad\u7ec3\u5b8c\u6210\uff0c\u514b\u9686 ID\uff1a",
  cloneIdRequired: "\u8bf7\u8f93\u5165\u5df2\u6709\u514b\u9686 ID\u3002",
  cloneLoading: "\u6b63\u5728\u52a0\u8f7d\u5df2\u6709\u514b\u9686...",
  cloneLoadFailed: "\u52a0\u8f7d\u514b\u9686\u5931\u8d25",
  cloneLoaded: "\u5df2\u52a0\u8f7d\u514b\u9686 ID\uff1a",
  replyFailed: "\u56de\u590d\u5931\u8d25",
  speechFailed: "\u8bed\u97f3\u751f\u6210\u5931\u8d25",
  speechReady: "\u8bed\u97f3\u5df2\u751f\u6210",
  speechPlayBlocked: "\u6d4f\u89c8\u5668\u963b\u6b62\u4e86\u81ea\u52a8\u64ad\u653e\uff0c\u8bf7\u70b9\u51fb\u64ad\u653e\u5668\u3002",
  voiceTraining: "\u6b63\u5728\u8bad\u7ec3\u97f3\u8272...",
  voiceTrainingFailed: "\u97f3\u8272\u8bad\u7ec3\u5931\u8d25",
  voiceSamplesUploading: "\u6b63\u5728\u4fdd\u5b58\u8bed\u97f3\u6837\u672c...",
  voiceSamplesUploaded: "\u8bed\u97f3\u6837\u672c\u5df2\u4fdd\u5b58",
  voiceSamplesUploadFailed: "\u8bed\u97f3\u6837\u672c\u4fdd\u5b58\u5931\u8d25",
  voiceStatusRefreshing: "\u6b63\u5728\u5237\u65b0\u97f3\u8272\u72b6\u6001...",
  voiceStatusRefreshFailed: "\u97f3\u8272\u72b6\u6001\u5237\u65b0\u5931\u8d25",
  noVoiceSampleSelected: "\u8bf7\u5148\u9009\u62e9\u6216\u5f55\u5236\u8bed\u97f3\u6837\u672c",
  notExtracted: "\u672a\u63d0\u53d6\u5230",
  notConnected: "\u672a\u63d0\u4f9b\u8bed\u97f3\u6837\u672c",
  samplesWaiting: "\u5c1a\u672a\u9009\u62e9\u8bed\u97f3\u6837\u672c",
  samplesSelected: "\u5df2\u9009\u62e9",
  trainingWaiting: "\u7b49\u5f85\u4e0a\u4f20",
  voiceReadFailed: "\u65e0\u6cd5\u8bfb\u53d6\u58f0\u97f3\u6587\u4ef6",
  assetReadFailed: "\u65e0\u6cd5\u8bfb\u53d6\u672c\u5730\u6587\u4ef6",
  chatReadFailed: "\u65e0\u6cd5\u8bfb\u53d6\u804a\u5929\u6587\u672c\u6587\u4ef6",
  chatFileHeader: "\u6765\u81ea\u6587\u4ef6",
  recordStart: "\u5f55\u5236\u8bed\u97f3\u6837\u672c",
  recordStop: "\u505c\u6b62\u5f55\u5236",
  recording: "\u6b63\u5728\u5f55\u5236...",
  recordingIdle: "\u9ea6\u514b\u98ce\u672a\u5f00\u59cb",
  recordingSaved: "\u5df2\u6dfb\u52a0\u5f55\u97f3\u6837\u672c\uff1a",
  recordingUnsupported: "\u5f53\u524d\u6d4f\u89c8\u5668\u4e0d\u652f\u6301\u5f55\u97f3\uff0c\u8bf7\u6539\u4e3a\u4e0a\u4f20\u97f3\u9891\u6587\u4ef6\u3002",
  recordingDenied: "\u65e0\u6cd5\u6253\u5f00\u9ea6\u514b\u98ce\uff0c\u8bf7\u68c0\u67e5\u6d4f\u89c8\u5668\u6388\u6743\u3002",
  recordingFailed: "\u5f55\u97f3\u5931\u8d25\uff0c\u8bf7\u91cd\u8bd5\u6216\u4e0a\u4f20\u97f3\u9891\u6587\u4ef6\u3002",
};

const form = document.querySelector("#clone-form");
const targetNameInput = document.querySelector("#target-name");
const cloneIdInput = document.querySelector("#clone-id-input");
const loadCloneButton = document.querySelector("#load-clone-button");
const chatFileInput = document.querySelector("#chat-file");
const chatTextInput = document.querySelector("#chat-text");
const voiceFileInput = document.querySelector("#voice-file");
const statusEl = document.querySelector("#status");
const sampleListEl = document.querySelector("#sample-list");
const trainingStateEl = document.querySelector("#training-state");
const voiceUploadButton = document.querySelector("#voice-upload-button");
const voiceTrainButton = document.querySelector("#voice-train-button");
const voiceRefreshButton = document.querySelector("#voice-refresh-button");
const recordVoiceButton = document.querySelector("#record-voice-button");
const recordingStateEl = document.querySelector("#recording-state");
const chatForm = document.querySelector("#chat-form");
const messageInput = document.querySelector("#message-input");
const messagesEl = document.querySelector("#messages");
const audioPlayback = document.querySelector("#audio-playback");
const voiceEmotion = document.querySelector("#voice-emotion");

document.querySelectorAll('input[name="chatMode"]').forEach((input) => {
  input.addEventListener("change", () => {
    state.chatMode = input.value;
    if (state.chatMode === "text") {
      clearSpeechPlayback();
    }
  });
});

chatFileInput.addEventListener("change", async () => {
  const files = Array.from(chatFileInput.files || []);
  if (!files.length) return;

  try {
    const contents = await Promise.all(
      files.map(async (file) => {
        const content = await readAsText(file);
        return `# ${text.chatFileHeader}: ${file.name}\n${content}`;
      })
    );
    chatTextInput.value = contents.join("\n\n");
  } catch (error) {
    setStatus(error.message, true);
  }
});

voiceFileInput.addEventListener("change", () => {
  renderPendingVoiceSamples();
});

recordVoiceButton.addEventListener("click", toggleVoiceRecording);
voiceUploadButton.addEventListener("click", uploadVoiceSamples);
voiceTrainButton.addEventListener("click", trainVoiceModel);
voiceRefreshButton.addEventListener("click", refreshVoiceStatus);
loadCloneButton.addEventListener("click", loadExistingClone);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const targetName = targetNameInput.value.trim();
  const chatText = chatTextInput.value.trim();

  if (!targetName || !chatText) {
    setStatus(text.fillRequired, true);
    return;
  }

  setStatus(text.training);
  setFormBusy(true);

  try {
    const voiceFiles = await readCombinedVoiceFiles();
    const response = await fetch("/api/clones", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        targetName,
        chatText,
        voiceFiles,
      }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || text.trainFailed);

    state.cloneId = body.clone.cloneId;
    renderProfile(body.clone);
    clearPendingVoiceSamples();
    enableChat();
    setStatus(`${text.trained}${state.cloneId}`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setFormBusy(false);
  }
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!state.cloneId || !message) return;

  appendMessage(message, "user");
  messageInput.value = "";

  try {
    const response = await fetch(`/api/clones/${state.cloneId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || text.replyFailed);
    const replyText = body.reply.text;
    appendMessage(replyText, "clone");
    if (state.chatMode === "voice") {
      await speakReply(replyText, body.reply.emotion);
    }
  } catch (error) {
    appendMessage(error.message, "clone");
  }
});

async function loadExistingClone() {
  const cloneId = cloneIdInput.value.trim();
  if (!cloneId) {
    setStatus(text.cloneIdRequired, true);
    return;
  }

  setStatus(text.cloneLoading);
  loadCloneButton.disabled = true;
  try {
    const response = await fetch(`/api/clones/${encodeURIComponent(cloneId)}`, {
      method: "GET",
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || text.cloneLoadFailed);

    state.cloneId = body.clone.cloneId;
    targetNameInput.value = body.clone.name || targetNameInput.value;
    renderProfile(body.clone);
    clearPendingVoiceSamples();
    enableChat();
    setStatus(`${text.cloneLoaded}${state.cloneId}`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    loadCloneButton.disabled = false;
  }
}

function renderProfile(clone) {
  document.querySelector("#catchphrases").textContent = clone.style.catchphrases.join("\u3001") || text.notExtracted;
  document.querySelector("#topics").textContent = clone.memory.keyTopics?.join("\u3001") || clone.memory.key_topics?.join("\u3001") || text.notExtracted;
  document.querySelector("#voice-status").textContent = clone.voice?.message || text.notConnected;
  const sampleNames = sampleNamesFromClone(clone);
  state.savedVoiceSampleNames = sampleNames;
  renderVoiceSamples(sampleNames, clone.voice?.status || text.trainingWaiting);
  scheduleVoiceStatusPoll(clone.voice?.status);
  syncVoiceSampleActions();
  document.querySelector("#source-stats").textContent = [
    `${clone.sourceStats.target_messages || 0} \u6761\u76ee\u6807\u6d88\u606f`,
    `${clone.sourceStats.voice_files || 0} \u4e2a\u8bed\u97f3`,
  ].join("\uff0c");
}

function enableChat() {
  clearSpeechPlayback();
  messagesEl.innerHTML = "";
  messageInput.disabled = false;
  chatForm.querySelector("button").disabled = false;
  messageInput.focus();
}

function appendMessage(textContent, role) {
  const bubble = document.createElement("p");
  bubble.className = `bubble ${role}`;
  bubble.textContent = textContent;
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function speakReply(replyText, replyEmotion) {
  const selectedEmotion = voiceEmotion.value === "auto" ? replyEmotion || "natural" : voiceEmotion.value;
  try {
    const response = await fetch(`/api/clones/${state.cloneId}/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: replyText,
        emotion: selectedEmotion,
      }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || text.speechFailed);
    const speech = body.speech;
    if (!speech.audioDataUrl) {
      appendMessage(speech.message || text.speechFailed, "system");
      setStatus(speech.message || text.speechFailed, speechStatusIsError(speech.status));
      return;
    }

    audioPlayback.hidden = false;
    audioPlayback.src = speech.audioDataUrl;
    setStatus(`${text.speechReady}: ${speech.backend}`);
    try {
      await audioPlayback.play();
    } catch {
      setStatus(text.speechPlayBlocked);
    }
  } catch (error) {
    appendMessage(error.message, "system");
    setStatus(error.message, true);
  }
}

function clearSpeechPlayback() {
  audioPlayback.pause();
  audioPlayback.removeAttribute("src");
  audioPlayback.load();
  audioPlayback.hidden = true;
}

async function uploadVoiceSamples() {
  if (!state.cloneId) return;

  const pendingFiles = selectedVoiceFiles();
  if (!pendingFiles.length) {
    setStatus(text.noVoiceSampleSelected, true);
    return;
  }

  setStatus(text.voiceSamplesUploading);
  setVoiceActionsBusy(true);
  try {
    const voiceFiles = await readUploadFiles(pendingFiles, text.voiceReadFailed);
    const response = await fetch(`/api/clones/${state.cloneId}/voice/samples`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voiceFiles }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || text.voiceSamplesUploadFailed);
    renderProfile(body.clone);
    clearPendingVoiceSamples();
    setStatus(body.voice?.message || text.voiceSamplesUploaded, voiceStatusIsError(body.voice?.status));
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setVoiceActionsBusy(false);
  }
}

async function trainVoiceModel() {
  if (!state.cloneId) return;

  setStatus(text.voiceTraining);
  setVoiceActionsBusy(true);
  try {
    const response = await fetch(`/api/clones/${state.cloneId}/voice/train`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || text.voiceTrainingFailed);
    renderProfile(body.clone);
    setStatus(body.voice?.message || text.speechReady, voiceStatusIsError(body.voice?.status));
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setVoiceActionsBusy(false);
  }
}

async function refreshVoiceStatus() {
  if (!state.cloneId) return;

  setStatus(text.voiceStatusRefreshing);
  setVoiceActionsBusy(true);
  try {
    const response = await fetch(`/api/clones/${state.cloneId}/voice/status`, {
      method: "GET",
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || text.voiceStatusRefreshFailed);
    renderProfile(body.clone);
    setStatus(body.voice?.message || text.speechReady, voiceStatusIsError(body.voice?.status));
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setVoiceActionsBusy(false);
  }
}

async function toggleVoiceRecording() {
  if (state.recorder?.state === "recording") {
    state.recorder.stop();
    return;
  }

  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    recordingStateEl.textContent = text.recordingUnsupported;
    setStatus(text.recordingUnsupported, true);
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.recordingStream = stream;
    state.recordedChunks = [];
    state.recorder = new MediaRecorder(stream);
    state.recorder.addEventListener("dataavailable", (event) => {
      if (event.data?.size) {
        state.recordedChunks.push(event.data);
      }
    });
    state.recorder.addEventListener("stop", saveRecordedVoiceSample, { once: true });
    state.recorder.start();
    recordVoiceButton.textContent = text.recordStop;
    recordVoiceButton.classList.add("recording");
    recordingStateEl.textContent = text.recording;
  } catch {
    stopRecordingStream();
    recordingStateEl.textContent = text.recordingDenied;
    setStatus(text.recordingDenied, true);
  }
}

function saveRecordedVoiceSample() {
  try {
    if (!state.recordedChunks.length) {
      recordingStateEl.textContent = text.recordingFailed;
      setStatus(text.recordingFailed, true);
      return;
    }

    const mimeType = state.recordedChunks[0].type || "audio/webm";
    const extension = recordingExtension(mimeType);
    const filename = `recording-${new Date().toISOString().replace(/[:.]/g, "-")}.${extension}`;
    const blob = new Blob(state.recordedChunks, { type: mimeType });
    const file =
      typeof File === "function"
        ? new File([blob], filename, { type: mimeType })
        : Object.assign(blob, { name: filename });
    state.recordedVoiceFiles.push(file);
    recordingStateEl.textContent = `${text.recordingSaved}${filename}`;
    renderPendingVoiceSamples();
  } finally {
    stopRecordingStream();
  }
}

function stopRecordingStream() {
  state.recordingStream?.getTracks().forEach((track) => track.stop());
  state.recordingStream = null;
  state.recorder = null;
  state.recordedChunks = [];
  recordVoiceButton.textContent = text.recordStart;
  recordVoiceButton.classList.remove("recording");
}

function recordingExtension(mimeType) {
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("wav")) return "wav";
  if (mimeType.includes("mp4")) return "m4a";
  return "webm";
}

function sampleNamesFromClone(clone) {
  const names = clone.voice?.sample_filenames || clone.voice?.sampleFilenames || [];
  if (names.length) return names;
  return clone.voice?.sample_filename ? [clone.voice.sample_filename] : [];
}

function selectedVoiceFiles() {
  return [...Array.from(voiceFileInput.files || []), ...state.recordedVoiceFiles];
}

function clearPendingVoiceSamples() {
  voiceFileInput.value = "";
  state.recordedVoiceFiles = [];
  recordingStateEl.textContent = text.recordingIdle;
  syncVoiceSampleActions();
}

function syncVoiceSampleActions() {
  voiceUploadButton.disabled = !state.cloneId || !selectedVoiceFiles().length;
  voiceTrainButton.disabled = !state.cloneId || !state.savedVoiceSampleNames.length;
  voiceRefreshButton.disabled = !state.cloneId;
}

function setVoiceActionsBusy(isBusy) {
  if (isBusy) {
    voiceUploadButton.disabled = true;
    voiceTrainButton.disabled = true;
    voiceRefreshButton.disabled = true;
    return;
  }
  syncVoiceSampleActions();
}

function renderPendingVoiceSamples() {
  const files = selectedVoiceFiles();
  const label = files.length ? `${text.samplesSelected} ${files.length}` : text.trainingWaiting;
  renderVoiceSamples(files.map((file) => file.name), label);
  syncVoiceSampleActions();
}

function renderVoiceSamples(names, stateLabel) {
  const statusLabel = stateLabel || text.trainingWaiting;
  trainingStateEl.textContent = statusLabel;
  trainingStateEl.classList.toggle("ok", voiceStatusIsOk(statusLabel));
  trainingStateEl.classList.toggle("error", voiceStatusIsError(statusLabel));
  sampleListEl.innerHTML = "";
  const safeNames = names.filter(Boolean);
  if (!safeNames.length) {
    const item = document.createElement("li");
    item.textContent = text.samplesWaiting;
    sampleListEl.appendChild(item);
    return;
  }

  safeNames.forEach((name) => {
    const item = document.createElement("li");
    item.textContent = name;
    sampleListEl.appendChild(item);
  });
}

function voiceStatusIsOk(status) {
  return ["samples_ready", "ready"].includes(status);
}

function voiceStatusIsPending(status) {
  return ["queued", "running"].includes(status);
}

function voiceStatusIsError(status) {
  return ["error", "failed", "missing_samples", "pending_adapter", "pending_backend", "unavailable"].includes(status);
}

function speechStatusIsError(status) {
  return ["error", "failed"].includes(status);
}

function scheduleVoiceStatusPoll(status) {
  clearVoiceStatusPoll();
  if (!voiceStatusIsPending(status)) {
    return;
  }
  state.voiceStatusPollTimer = setTimeout(refreshVoiceStatus, 3000);
}

function clearVoiceStatusPoll() {
  if (!state.voiceStatusPollTimer) {
    return;
  }
  clearTimeout(state.voiceStatusPollTimer);
  state.voiceStatusPollTimer = null;
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#b33122" : "";
}

function setFormBusy(isBusy) {
  form.querySelector("button[type='submit']").disabled = isBusy;
}

function readCombinedVoiceFiles() {
  return readUploadFiles(selectedVoiceFiles(), text.voiceReadFailed);
}

function readUploadFiles(fileList, errorMessage = text.assetReadFailed) {
  return Promise.all(
    Array.from(fileList || []).map(async (file) => ({
      name: file.name,
      data: await readAsDataUrl(file, errorMessage),
    }))
  );
}

function readAsDataUrl(file, errorMessage) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(errorMessage));
    reader.readAsDataURL(file);
  });
}

function readAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(text.chatReadFailed));
    reader.readAsText(file, "utf-8");
  });
}
