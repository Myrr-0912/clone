# Voice Recording Samples

The browser UI supports two local voice-sample inputs:

- Upload one or more existing audio files with the voice file picker.
- Record a microphone sample in the browser with `MediaRecorder`.

Recorded samples are converted into local audio files and submitted in the same
`voiceFiles` payload as uploaded files when the clone is created. The backend
saves all samples under `data/clones/{clone_id}/voice/`, then `POST
/api/clones/{clone_id}/voice/train` can hand those paths to the configured voice
training backend.

If multiple samples share the same original filename, the backend keeps every
sample by assigning suffixes such as `sample-2.wav` instead of overwriting an
earlier file.

After a clone exists, the same picker and recorder can add more samples without
recreating the clone. The UI calls `POST /api/clones/{clone_id}/voice/samples`
with a `voiceFiles` array, appends those files under the existing `voice/`
directory, resets the voice status to `samples_ready`, and enables another
training run.

If the browser is refreshed or the user returns later, paste the clone ID into
the existing-clone field and click the load button. The UI calls `GET
/api/clones/{clone_id}`, restores the profile, saved sample list, voice
training state, and re-enables text or voice chat plus additional sample upload.

The UI also exposes a status refresh action for existing clones. It calls
`GET /api/clones/{clone_id}/voice/status`, reads the persisted `status.json`,
optionally refreshes in-progress jobs through the configured external status
endpoint, and re-renders the sample list plus training status. This is useful
for external training backends that return `queued` or `running` before the
voice model is ready.

For asynchronous HTTP training backends, set `VOICE_TRAINING_STATUS_URL` or
`VOXCPM_TRAINING_STATUS_URL`. While the saved status is `queued` or `running`,
the main app POSTs this payload to the status URL:

```json
{
  "cloneId": "abc123",
  "voiceName": "Target",
  "jobId": "job-123",
  "modelId": ""
}
```

The status service should return a JSON object with fields such as `status`,
`message`, `modelId`, `jobId`, and optional `error`. The main app preserves the
uploaded sample list, updates `data/clones/{clone_id}/voice/status.json`, and
returns the refreshed status to the browser. If no status URL is configured,
refresh returns the last local snapshot.

When a training response or status refresh reports `queued` or `running`, the
browser automatically polls `GET /api/clones/{clone_id}/voice/status` every
three seconds until the status leaves that in-progress set. The manual refresh
button remains available for debugging or external workers with slower updates.

In voice chat mode, the emotion selector defaults to `auto`. The frontend then
uses the `emotion` returned by `POST /api/clones/{clone_id}/chat` when calling
`POST /api/clones/{clone_id}/speak`; choosing a concrete emotion overrides that
automatic value.

If the browser does not support microphone recording, or the user denies
permission, the UI keeps the upload path available and shows an explicit error
message.

Verification:

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
& "C:\Users\myrr\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```
