# Architecture

## Build path

```text
GitHub repository
      |
      | config/upstream.env
      v
fetch pinned BookLore source
      |
      v
customizations/apply-customizations.py
      |
      +--> reader TTS / UI / settings
      +--> Paste-to-EPUB
      +--> frontend dependencies
      |
      v
BookLore upstream Dockerfile
      |
      v
custom BookLore image
```

The build tree is generated under `.build/` and intentionally ignored by Git.

## Runtime stack

```text
Internet
   |
   v
Caddy :80/:443
   |
   +----------------------> BookLore :6060
   |
   +-- /tts/* -----------> Piper :5000
                              |
                              +-> en_US-libritts_r-medium

BookLore -----------------> MariaDB
   |
   +-> /books
   +-> /bookdrop
   +-> /app/data
```

Only Caddy publishes host ports.

## Reader TTS

### Starting position

A text selection is used only as a positional anchor. Reading starts at the first character of the selection and continues forward.

### Chunk queue

The current EPUB section is converted to sentence-aware chunks (default approximately 650 characters). Each chunk stores:

- text
- EPUB section index
- CFI for the chunk's first character

The first chunk is generated before playback; subsequent chunks are generated ahead according to the queue setting.

Before a chunk begins playing, BookLore navigates to that chunk's CFI. BookLore's normal relocation/progress mechanism therefore persists a resume point near the audio position and keeps the visible page near what is being spoken.

### Server mode

```text
Browser -> /tts/synthesize -> Caddy -> Piper HTTP server -> WAV
```

The Piper HTTP server image is patched so `sentence_silence` may be sent per request and silence is generated as complete 16-bit samples. The latter avoids the odd-byte corruption/static issue.

### Local mode

```text
BookLore page -> piper-tts-web -> ONNX/WASM -> WAV in browser
```

No Piper daemon/container is required on the reader's computer. `piper-tts-web` downloads/loads the voice model in the browser. The selected voice is `en_US-libritts_r-medium`, speaker `0` (LibriTTS label 3922).

Local mode does not send the selected book text to the server-side Piper endpoint for synthesis.

## Reader settings

Settings are device/browser-local under:

```text
localStorage["bookloreReaderTtsSettings"]
```

Sliders commit on `change` (release), not every `input` event. Local-mode/reset toggles commit immediately. Active playback keeps its existing settings until the next TTS session.

## Paste-to-EPUB

The browser creates a standards-oriented EPUB ZIP with JSZip, splitting very large text into internal XHTML sections. It then uploads the generated file using BookLore's direct upload contract:

```text
POST /api/v1/files/upload?libraryId=<id>&pathId=<id>
Content-Type: multipart/form-data
file=<epub>
```

**Do not put `libraryId` or `pathId` in the multipart form body.** That earlier implementation produced the confusing BookDrop/review/duplicate state. Paste-to-EPUB is intended to bypass BookDrop completely.

BookDrop remains BookLore's separate watched-folder staging/review workflow for files that need review/finalization.

## State and secrets

Deployment code lives in `/opt/booklore-reader` by default. Stateful data lives in `/srv/booklore-reader`, and `.env` lives only in the repository checkout on the server and is `.gitignore`d.
