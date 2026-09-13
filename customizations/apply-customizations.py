#!/usr/bin/env python3
"""Apply BookLore Reader customizations to a clean pinned upstream checkout.

This intentionally uses guarded source transforms. If an upstream BookLore release
changes one of the anchors we depend on, the build stops instead of silently
shipping a half-patched UI.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply-customizations.py /path/to/booklore-source")

ROOT = Path(sys.argv[1]).resolve()
UI = ROOT / "booklore-ui"


def path(rel: str) -> Path:
    p = ROOT / rel
    if not p.exists():
        raise SystemExit(f"Required upstream file missing: {p}")
    return p


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Upstream changed: could not find {label}")
    return text.replace(old, new, 1)


def append_once(text: str, marker: str, block: str) -> str:
    return text if marker in text else text.rstrip() + "\n\n" + block.strip() + "\n"


# ---------------------------------------------------------------------------
# Frontend package metadata
# ---------------------------------------------------------------------------
pkg_file = path("booklore-ui/package.json")
pkg = json.loads(pkg_file.read_text())
pkg.setdefault("dependencies", {})["jszip"] = "^3.10.2"
pkg["dependencies"]["piper-tts-web"] = "^1.1.2"
pkg_file.write_text(json.dumps(pkg, indent=2) + "\n")

(UI / "src/piper-tts-web.d.ts").write_text(
    "declare module 'piper-tts-web' {\n"
    "  export const PiperWebEngine: any;\n"
    "}\n"
)

# ---------------------------------------------------------------------------
# Low-memory production build defaults for the 2 GB deployment target.
# ---------------------------------------------------------------------------
dockerfile = path("Dockerfile")
docker_src = dockerfile.read_text()
docker_src = replace_once(
    docker_src,
    "RUN npm run build --configuration=production",
    'ENV NG_BUILD_MAX_WORKERS=1\nENV NODE_OPTIONS="--max-old-space-size=1536"\nRUN npm run build -- --configuration=production',
    "Angular production build command",
)
docker_src = replace_once(
    docker_src,
    "RUN gradle clean build -x test --no-daemon --parallel",
    "RUN gradle clean build -x test --no-daemon --max-workers=1",
    "Gradle production build command",
)
dockerfile.write_text(docker_src)

# ---------------------------------------------------------------------------
# Selection popup: add Read Aloud action
# ---------------------------------------------------------------------------
popup_ts_file = path("booklore-ui/src/app/features/readers/ebook-reader/shared/selection-popup.component.ts")
popup_ts = popup_ts_file.read_text()
popup_ts = replace_once(
    popup_ts,
    "type: 'select' | 'annotate' | 'delete' | 'dismiss' | 'preview' | 'search' | 'note';",
    "type: 'select' | 'annotate' | 'delete' | 'dismiss' | 'preview' | 'search' | 'note' | 'read-aloud';",
    "TextSelectionAction type union",
)
popup_ts = replace_once(
    popup_ts,
    "  onNote(): void {\n    this.action.emit({type: 'note'});",
    "  onReadAloud(): void {\n"
    "    this.action.emit({type: 'read-aloud'});\n"
    "    this.showAnnotationOptions = false;\n"
    "    this.hasPreview = false;\n"
    "  }\n\n"
    "  onNote(): void {\n    this.action.emit({type: 'note'});",
    "selection popup onNote()",
)
popup_ts_file.write_text(popup_ts)

popup_html_file = path("booklore-ui/src/app/features/readers/ebook-reader/shared/selection-popup.component.html")
popup_html = popup_html_file.read_text()
if '(click)="onReadAloud()"' not in popup_html:
    popup_html, count = re.subn(
        r'(?P<indent>[ \t]*)<div class="divider"></div>\s*'
        r'(?P=indent)<div class="annotation-container">',
        lambda match: (
            f'{match.group("indent")}<div class="divider"></div>\n'
            f'{match.group("indent")}<button class="action-btn" (click)="onReadAloud()" title="Read aloud">\n'
            f'{match.group("indent")}  <app-reader-icon name="play" [size]="16"></app-reader-icon>\n'
            f'{match.group("indent")}</button>\n\n'
            f'{match.group("indent")}<div class="divider"></div>\n'
            f'{match.group("indent")}<div class="annotation-container">'
        ),
        popup_html,
        count=1,
    )
    if count != 1:
        raise SystemExit("Upstream changed: could not find annotation container in selection popup")
popup_html_file.write_text(popup_html)

# ---------------------------------------------------------------------------
# Reader event service: mobile tap-to-start TTS anchor picking.
# ---------------------------------------------------------------------------
event_file = path("booklore-ui/src/app/features/readers/ebook-reader/core/event.service.ts")
event_src = event_file.read_text()
event_src = replace_once(
    event_src,
    "  type: 'load' | 'relocate' | 'error' | 'middle-single-tap' | 'draw-annotation' | 'show-annotation' | 'text-selected' | 'toggle-fullscreen' | 'toggle-shortcuts-help' | 'escape-pressed' | 'go-first-section' | 'go-last-section' | 'toggle-toc' | 'toggle-search' | 'toggle-notes';",
    "  type: 'load' | 'relocate' | 'error' | 'middle-single-tap' | 'draw-annotation' | 'show-annotation' | 'text-selected' | 'tts-anchor-picked' | 'toggle-fullscreen' | 'toggle-shortcuts-help' | 'escape-pressed' | 'go-first-section' | 'go-last-section' | 'toggle-toc' | 'toggle-search' | 'toggle-notes';",
    "ViewEvent type union for TTS tap anchor",
)
event_src = replace_once(
    event_src,
    "  private lastTouchTime = 0;",
    "  private lastTouchTime = 0;\n  private ttsTapAnchorArmed = false;",
    "event-service lastTouchTime state",
)
event_src = replace_once(
    event_src,
    "  emit(event: ViewEvent): void {\n    this.eventSubject.next(event);\n  }",
    "  emit(event: ViewEvent): void {\n"
    "    this.eventSubject.next(event);\n"
    "  }\n\n"
    "  armTtsTapAnchor(): void {\n"
    "    this.ttsTapAnchorArmed = true;\n"
    "  }\n\n"
    "  cancelTtsTapAnchor(): void {\n"
    "    this.ttsTapAnchorArmed = false;\n"
    "  }",
    "event-service emit()",
)
event_src = replace_once(
    event_src,
    "    doc.addEventListener('click', (event: MouseEvent) => {\n"
    "      // Ignore synthesized mouse events that follow touch events",
    "    doc.addEventListener('click', (event: MouseEvent) => {\n"
    "      if (this.ttsTapAnchorArmed) {\n"
    "        event.preventDefault();\n"
    "        event.stopPropagation();\n"
    "        this.pickTtsAnchorFromPoint(doc, event.clientX, event.clientY);\n"
    "        return;\n"
    "      }\n\n"
    "      // Ignore synthesized mouse events that follow touch events",
    "iframe click handler for TTS tap anchor",
)
event_src = replace_once(
    event_src,
    "    this.lastTouchTime = touchEndTime;\n\n"
    "    const selection = doc.defaultView?.getSelection();",
    "    this.lastTouchTime = touchEndTime;\n\n"
    "    if (this.ttsTapAnchorArmed && event.changedTouches.length === 1) {\n"
    "      const touch = event.changedTouches[0];\n"
    "      event.preventDefault();\n"
    "      event.stopPropagation();\n"
    "      this.isTextSelectionInProgress = false;\n"
    "      this.pickTtsAnchorFromPoint(doc, touch.clientX, touch.clientY);\n"
    "      return;\n"
    "    }\n\n"
    "    const selection = doc.defaultView?.getSelection();",
    "touchend TTS tap anchor handler",
)
anchor_pick_methods = r'''
  private pickTtsAnchorFromPoint(doc: Document, clientX: number, clientY: number): void {
    const anyDoc = doc as any;
    let range: Range | null = null;

    if (typeof anyDoc.caretRangeFromPoint === 'function') {
      range = anyDoc.caretRangeFromPoint(clientX, clientY) as Range | null;
    } else if (typeof anyDoc.caretPositionFromPoint === 'function') {
      const position = anyDoc.caretPositionFromPoint(clientX, clientY);
      if (position?.offsetNode) {
        range = doc.createRange();
        try {
          range.setStart(position.offsetNode, position.offset);
          range.collapse(true);
        } catch {
          range = null;
        }
      }
    }

    if (!range) return;

    const contents = this.viewCallbacks?.getContents();
    if (!contents?.length) return;
    const content = contents.find(item => item.doc === doc) ?? contents[0];
    const cfi = this.viewCallbacks?.getCFI(content.index, range);
    if (!cfi) return;

    this.ttsTapAnchorArmed = false;
    this.eventSubject.next({
      type: 'tts-anchor-picked',
      detail: {text: '', cfi, range, index: content.index}
    });
  }
'''
if "private pickTtsAnchorFromPoint(" not in event_src:
    marker = "  private handleSelectionEnd(doc: Document): void {\n"
    if marker not in event_src:
        raise SystemExit("Upstream changed: event-service handleSelectionEnd() not found")
    event_src = event_src.replace(marker, anchor_pick_methods + "\n" + marker, 1)
event_file.write_text(event_src)

# ---------------------------------------------------------------------------
# Foliate view manager: create sentence-aware chunks, each with its own CFI.
# ---------------------------------------------------------------------------
view_file = path("booklore-ui/src/app/features/readers/ebook-reader/core/view-manager.service.ts")
view = view_file.read_text()
view_methods = r'''
  getTtsChunksFromSelectionStart(
    selection: TextSelection,
    maxChars = 650
  ): Array<{text: string; cfi: string; index: number}> {
    const sourceRange = selection?.range;
    const doc = sourceRange?.startContainer?.ownerDocument;
    if (!sourceRange || !doc?.body) return [];

    return this.buildTtsChunks(
      selection.index,
      doc,
      sourceRange.startContainer,
      sourceRange.startOffset,
      maxChars
    );
  }

  getTtsChunksFromCurrentSection(
    maxChars = 650
  ): Array<{text: string; cfi: string; index: number}> {
    const renderer = this.getRenderer();
    const contents = renderer?.getContents?.() ?? [];
    if (!contents.length) return [];

    const {index, doc} = contents[0];
    if (!doc?.body) return [];
    return this.buildTtsChunks(index, doc, null, 0, maxChars);
  }

  getSectionCount(): number {
    return this.view?.book?.sections?.length
      ?? this.view?.book?.spine?.length
      ?? 0;
  }


  armTtsTapAnchor(): void {
    this.eventService.armTtsTapAnchor();
  }

  cancelTtsTapAnchor(): void {
    this.eventService.cancelTtsTapAnchor();
  }

  private buildTtsChunks(
    index: number,
    doc: Document,
    startContainer: Node | null,
    startOffset: number,
    maxChars: number
  ): Array<{text: string; cfi: string; index: number}> {
    const chunks: Array<{text: string; cfi: string; index: number}> = [];
    const pieces: Array<{text: string; node: Text; offset: number}> = [];
    const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);

    let waitingForAnchor = !!startContainer;
    let node: Node | null;

    while ((node = walker.nextNode())) {
      if (node.nodeType !== Node.TEXT_NODE) continue;
      const textNode = node as Text;
      const parent = textNode.parentElement;
      if (!parent) continue;

      const tag = parent.tagName.toLowerCase();
      if (['script', 'style', 'noscript'].includes(tag)) continue;
      const style = doc.defaultView?.getComputedStyle(parent);
      if (style?.display === 'none' || style?.visibility === 'hidden') continue;

      let nodeStart = 0;
      if (waitingForAnchor) {
        if (textNode === startContainer) {
          nodeStart = Math.min(startOffset, textNode.data.length);
          waitingForAnchor = false;
        } else {
          try {
            const r = doc.createRange();
            r.selectNodeContents(textNode);
            const anchor = doc.createRange();
            anchor.setStart(startContainer!, startOffset);
            anchor.collapse(true);
            if (anchor.compareBoundaryPoints(Range.START_TO_START, r) >= 0) continue;
            waitingForAnchor = false;
          } catch {
            continue;
          }
        }
      }

      const raw = textNode.data.slice(nodeStart);
      if (!raw.trim()) continue;

      const pattern = /[^.!?]+(?:[.!?]+["'’”)\]]*)?(?:\s+|$)/g;
      let match: RegExpExecArray | null;
      let found = false;
      while ((match = pattern.exec(raw)) !== null) {
        const rawPiece = match[0];
        const leading = rawPiece.search(/\S/);
        if (leading < 0) continue;
        const spoken = rawPiece.replace(/\s+/g, ' ').trim();
        if (!spoken) continue;
        pieces.push({text: spoken, node: textNode, offset: nodeStart + match.index + leading});
        found = true;
      }
      if (!found) {
        const leading = raw.search(/\S/);
        if (leading >= 0) {
          pieces.push({text: raw.replace(/\s+/g, ' ').trim(), node: textNode, offset: nodeStart + leading});
        }
      }
    }

    let text = '';
    let anchorNode: Text | null = null;
    let anchorOffset = 0;

    const flush = () => {
      const spoken = text.trim();
      if (!spoken || !anchorNode) return;
      try {
        const range = doc.createRange();
        range.setStart(anchorNode, anchorOffset);
        range.collapse(true);
        const cfi = this.view?.getCFI(index, range);
        if (cfi) chunks.push({text: spoken, cfi, index});
      } catch (error) {
        console.warn('Could not create TTS chunk CFI:', error);
      }
      text = '';
      anchorNode = null;
      anchorOffset = 0;
    };

    for (const piece of pieces) {
      const nextLength = text.length + (text ? 1 : 0) + piece.text.length;
      if (text && nextLength > maxChars) flush();
      if (!anchorNode) {
        anchorNode = piece.node;
        anchorOffset = piece.offset;
      }
      text += (text ? ' ' : '') + piece.text;
      if (text.length >= maxChars) flush();
    }
    flush();
    return chunks;
  }
'''
if "getTtsChunksFromSelectionStart(" not in view:
    marker = "  getSelection(): TextSelection | null {\n"
    if marker not in view:
        raise SystemExit("Upstream changed: view-manager getSelection() not found")
    view = view.replace(marker, view_methods + "\n" + marker, 1)
view_file.write_text(view)

# ---------------------------------------------------------------------------
# Ebook reader: queue, CFI tracking, server Piper, browser Piper, controls.
# ---------------------------------------------------------------------------
reader_ts_file = path("booklore-ui/src/app/features/readers/ebook-reader/ebook-reader.component.ts")
reader = reader_ts_file.read_text()
reader = replace_once(
    reader,
    "import {Observable, of, Subject, throwError} from 'rxjs';",
    "import {firstValueFrom, Observable, of, Subject, throwError} from 'rxjs';",
    "rxjs import",
)

state_anchor = "  showShortcutsHelp = false;\n"
tts_state = r'''

  ttsState: 'idle' | 'loading' | 'playing' | 'paused' | 'error' = 'idle';
  ttsError = '';
  ttsIsGenerating = false;
  ttsTapToStartArmed = false;
  private ttsAnchorSelection: any = null;
  private ttsAudio: HTMLAudioElement | null = null;
  private ttsObjectUrl: string | null = null;
  private ttsAbortController: AbortController | null = null;
  private ttsSessionId = 0;
  private ttsSectionIndex = -1;
  private ttsPendingChunks: Array<{text: string; cfi: string; index: number}> = [];
  private ttsAudioQueue: Array<{chunk: {text: string; cfi: string; index: number}; url: string}> = [];
  private ttsGenerationPromise: Promise<void> | null = null;

  private ttsSentenceSilence = 0.40;
  private ttsChunkChars = 650;
  private ttsPrefetchChunks = 1;
  private ttsSpeechSpeed = 1.0;
  private ttsLocalMode = false;
  private readonly ttsSettingsKey = 'bookloreReaderTtsSettings';
  private ttsBrowserEngine: any = null;
  private readonly ttsBrowserVoice = 'en_US-libritts_r-medium';
  private readonly ttsBrowserSpeaker = 0;
'''
if "private ttsAudioQueue:" not in reader:
    if state_anchor not in reader:
        raise SystemExit("Upstream changed: reader state anchor not found")
    reader = reader.replace(state_anchor, state_anchor + tts_state, 1)

reader = replace_once(
    reader,
    "          case 'text-selected':\n            this.selectionService.handleTextSelected(event.detail, event.popupPosition);",
    "          case 'text-selected':\n"
    "            this.ttsAnchorSelection = event.detail;\n"
    "            this.selectionService.handleTextSelected(event.detail, event.popupPosition);",
    "text-selected handler",
)
reader = replace_once(
    reader,
    "          case 'text-selected':\n"
    "            this.ttsAnchorSelection = event.detail;\n"
    "            this.selectionService.handleTextSelected(event.detail, event.popupPosition);\n"
    "            break;",
    "          case 'text-selected':\n"
    "            this.ttsAnchorSelection = event.detail;\n"
    "            this.selectionService.handleTextSelected(event.detail, event.popupPosition);\n"
    "            break;\n"
    "          case 'tts-anchor-picked':\n"
    "            this.ttsTapToStartArmed = false;\n"
    "            this.ttsAnchorSelection = event.detail;\n"
    "            void this.readAloud();\n"
    "            break;",
    "TTS tap anchor event handler",
)
reader = replace_once(
    reader,
    "  handleSelectionAction(action: TextSelectionAction): void {\n"
    "    if (action.type === 'note') {\n"
    "      this.noteService.openNewNoteDialog();\n"
    "    } else {\n"
    "      this.selectionService.handleAction(action);\n"
    "    }\n"
    "  }",
    "  handleSelectionAction(action: TextSelectionAction): void {\n"
    "    if (action.type === 'read-aloud') {\n"
    "      void this.readAloud();\n"
    "      this.selectionService.handleAction({type: 'dismiss'});\n"
    "    } else if (action.type === 'note') {\n"
    "      this.noteService.openNewNoteDialog();\n"
    "    } else {\n"
    "      this.selectionService.handleAction(action);\n"
    "    }\n"
    "  }",
    "handleSelectionAction()",
)

methods = r'''
  toggleTtsTapToStart(): void {
    if (this.ttsTapToStartArmed) {
      this.ttsTapToStartArmed = false;
      this.viewManager.cancelTtsTapAnchor();
      return;
    }

    if (this.ttsState !== 'idle' && this.ttsState !== 'error') {
      this.stopTts();
    }
    this.ttsError = '';
    this.selectionService.handleAction({type: 'dismiss'});
    this.viewManager.clearSelection();
    this.ttsTapToStartArmed = true;
    this.viewManager.armTtsTapAnchor();
  }

  private loadReaderTtsSettings(): void {
    try {
      const saved = JSON.parse(localStorage.getItem(this.ttsSettingsKey) || 'null');
      if (!saved) return;
      const clamp = (v: unknown, min: number, max: number, fallback: number) => {
        const n = Number(v);
        return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : fallback;
      };
      this.ttsSentenceSilence = clamp(saved.sentenceSilence, 0, 1.5, 0.40);
      this.ttsChunkChars = Math.round(clamp(saved.chunkChars, 250, 2000, 650));
      this.ttsPrefetchChunks = Math.round(clamp(saved.prefetchChunks, 1, 3, 1));
      this.ttsSpeechSpeed = clamp(saved.speechSpeed, 0.6, 1.6, 1.0);
      this.ttsLocalMode = Boolean(saved.localMode);
    } catch (error) {
      console.warn('Could not load reader TTS settings:', error);
    }
  }

  @HostListener('window:booklore-tts-settings-changed')
  onReaderTtsSettingsChanged(): void {
    if (this.ttsState === 'idle' || this.ttsState === 'error') {
      this.loadReaderTtsSettings();
    }
  }

  async readAloud(): Promise<void> {
    this.loadReaderTtsSettings();
    this.stopTts();
    this.ttsError = '';

    if (!this.ttsAnchorSelection?.range) {
      this.ttsState = 'error';
      this.ttsError = 'Select text where you want reading to begin.';
      return;
    }

    const chunks = this.viewManager.getTtsChunksFromSelectionStart(this.ttsAnchorSelection, this.ttsChunkChars);
    if (!chunks.length) {
      this.ttsState = 'error';
      this.ttsError = 'No readable text was found after that position.';
      return;
    }

    const sessionId = this.ttsSessionId;
    this.ttsSectionIndex = this.ttsAnchorSelection.index;
    this.ttsPendingChunks = chunks;
    this.ttsState = 'loading';

    try {
      await this.prefetchTtsQueue(sessionId, 1);
      if (sessionId === this.ttsSessionId) await this.playNextTtsChunk(sessionId);
    } catch (error) {
      if (sessionId !== this.ttsSessionId) return;
      this.ttsIsGenerating = false;
      this.ttsState = 'error';
      this.ttsError = error instanceof Error ? error.message : 'Text-to-speech failed.';
    }
  }

  async toggleTtsPause(): Promise<void> {
    if (!this.ttsAudio) return;
    if (this.ttsAudio.paused) {
      await this.ttsAudio.play();
      this.ttsState = 'playing';
    } else {
      this.ttsAudio.pause();
      this.ttsState = 'paused';
    }
  }

  stopTts(): void {
    this.ttsTapToStartArmed = false;
    this.viewManager.cancelTtsTapAnchor();
    this.ttsSessionId += 1;
    this.ttsAbortController?.abort();
    this.ttsAbortController = null;
    this.ttsAudio?.pause();
    this.cleanupTtsAudio();
    for (const item of this.ttsAudioQueue) URL.revokeObjectURL(item.url);
    this.ttsAudioQueue = [];
    this.ttsPendingChunks = [];
    this.ttsGenerationPromise = null;
    this.ttsIsGenerating = false;
    this.ttsSectionIndex = -1;
    this.ttsError = '';
    this.ttsState = 'idle';
  }

  private async prefetchTtsQueue(sessionId: number, targetSize = 1): Promise<void> {
    if (sessionId !== this.ttsSessionId) return;
    if (this.ttsGenerationPromise) {
      await this.ttsGenerationPromise;
      return;
    }

    this.ttsGenerationPromise = (async () => {
      this.ttsIsGenerating = true;
      while (
        sessionId === this.ttsSessionId &&
        this.ttsAudioQueue.length < targetSize &&
        this.ttsPendingChunks.length > 0
      ) {
        const chunk = this.ttsPendingChunks.shift()!;
        const item = await this.synthesizeTtsChunk(chunk, sessionId);
        if (item && sessionId === this.ttsSessionId) this.ttsAudioQueue.push(item);
        else if (item) URL.revokeObjectURL(item.url);
      }
    })();

    try {
      await this.ttsGenerationPromise;
    } finally {
      if (sessionId === this.ttsSessionId) {
        this.ttsGenerationPromise = null;
        this.ttsIsGenerating = false;
      }
    }
  }

  private async synthesizeTtsChunk(
    chunk: {text: string; cfi: string; index: number},
    sessionId: number
  ): Promise<{chunk: {text: string; cfi: string; index: number}; url: string} | null> {
    if (sessionId !== this.ttsSessionId) return null;

    if (this.ttsLocalMode) {
      const blob = await this.synthesizeBrowserTts(chunk.text, sessionId);
      if (!blob || sessionId !== this.ttsSessionId) return null;
      return {chunk, url: URL.createObjectURL(blob)};
    }

    const controller = new AbortController();
    this.ttsAbortController = controller;
    try {
      const response = await fetch('/tts/synthesize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          text: chunk.text,
          speaker_id: 0,
          sentence_silence: this.ttsSentenceSilence,
          length_scale: 1 / this.ttsSpeechSpeed
        }),
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`TTS returned HTTP ${response.status}`);
      const blob = await response.blob();
      if (controller.signal.aborted || sessionId !== this.ttsSessionId) return null;
      return {chunk, url: URL.createObjectURL(blob)};
    } finally {
      if (this.ttsAbortController === controller) this.ttsAbortController = null;
    }
  }

  private async getBrowserPiperEngine(): Promise<any> {
    if (this.ttsBrowserEngine) return this.ttsBrowserEngine;
    const piper: any = await import('piper-tts-web');
    this.ttsBrowserEngine = new piper.PiperWebEngine();
    return this.ttsBrowserEngine;
  }

  private splitBrowserTtsSentences(text: string): string[] {
    const matches = text.match(/[^.!?]+(?:[.!?]+["'’”)\]]*)?(?:\s+|$)/g);
    return (matches ?? [text]).map(v => v.replace(/\s+/g, ' ').trim()).filter(Boolean);
  }

  private async synthesizeBrowserTts(text: string, sessionId: number): Promise<Blob | null> {
    const engine = await this.getBrowserPiperEngine();
    if (sessionId !== this.ttsSessionId) return null;
    const wavs: Blob[] = [];
    for (const sentence of this.splitBrowserTtsSentences(text)) {
      if (sessionId !== this.ttsSessionId) return null;
      const response = await engine.generate(sentence, this.ttsBrowserVoice, this.ttsBrowserSpeaker);
      if (!(response?.file instanceof Blob)) throw new Error('Browser Piper did not return WAV audio.');
      wavs.push(response.file);
    }
    return this.mergeBrowserPiperWavs(wavs, this.ttsSentenceSilence);
  }

  private async mergeBrowserPiperWavs(wavs: Blob[], pauseSeconds: number): Promise<Blob> {
    if (!wavs.length) throw new Error('Browser Piper generated no audio.');
    const buffers = await Promise.all(wavs.map(w => w.arrayBuffer()));
    const views = buffers.map(b => new DataView(b));
    const sampleRate = views[0].getUint32(24, true);
    const channels = views[0].getUint16(22, true);
    const bits = views[0].getUint16(34, true);
    if (channels !== 1 || bits !== 16) throw new Error('Unsupported browser Piper WAV format.');

    const parts = buffers.map(b => new Int16Array(b.slice(44)));
    const silence = Math.max(0, Math.round(sampleRate * Math.max(0, pauseSeconds)));
    const total = parts.reduce((sum, p) => sum + p.length, 0) + silence * Math.max(0, parts.length - 1);
    const pcm = new Int16Array(total);
    let offset = 0;
    parts.forEach((part, i) => {
      pcm.set(part, offset);
      offset += part.length;
      if (i < parts.length - 1) offset += silence;
    });

    const buffer = new ArrayBuffer(44 + pcm.byteLength);
    const out = new DataView(buffer);
    out.setUint32(0, 0x46464952, true);
    out.setUint32(4, buffer.byteLength - 8, true);
    out.setUint32(8, 0x45564157, true);
    out.setUint32(12, 0x20746d66, true);
    out.setUint32(16, 16, true);
    out.setUint16(20, 1, true);
    out.setUint16(22, 1, true);
    out.setUint32(24, sampleRate, true);
    out.setUint32(28, sampleRate * 2, true);
    out.setUint16(32, 2, true);
    out.setUint16(34, 16, true);
    out.setUint32(36, 0x61746164, true);
    out.setUint32(40, pcm.byteLength, true);
    new Int16Array(buffer, 44).set(pcm);
    return new Blob([buffer], {type: 'audio/wav'});
  }

  private async playNextTtsChunk(sessionId: number): Promise<void> {
    if (sessionId !== this.ttsSessionId) return;
    try {
      if (!this.ttsAudioQueue.length && !this.ttsPendingChunks.length) {
        const moved = await this.loadNextTtsSection(sessionId);
        if (!moved) {
          this.finishTtsPlayback();
          return;
        }
      }
      if (!this.ttsAudioQueue.length) {
        this.ttsState = 'loading';
        await this.prefetchTtsQueue(sessionId, 1);
      }
      const item = this.ttsAudioQueue.shift();
      if (!item || sessionId !== this.ttsSessionId) return;

      await firstValueFrom(this.viewManager.goTo(item.chunk.cfi));
      if (sessionId !== this.ttsSessionId) {
        URL.revokeObjectURL(item.url);
        return;
      }

      this.cleanupTtsAudio();
      this.ttsObjectUrl = item.url;
      const audio = new Audio(item.url);
      if (this.ttsLocalMode) {
        audio.playbackRate = this.ttsSpeechSpeed;
        (audio as any).preservesPitch = true;
      }
      this.ttsAudio = audio;
      audio.onended = () => {
        if (sessionId !== this.ttsSessionId) return;
        this.cleanupTtsAudio();
        void this.playNextTtsChunk(sessionId);
      };
      audio.onerror = () => {
        if (sessionId !== this.ttsSessionId) return;
        this.ttsState = 'error';
        this.ttsError = 'Generated audio could not be played.';
        this.cleanupTtsAudio();
      };
      await audio.play();
      this.ttsState = 'playing';
      void this.prefetchTtsQueue(sessionId, this.ttsPrefetchChunks).catch(error => {
        if (sessionId === this.ttsSessionId) console.error('TTS prefetch failed:', error);
      });
    } catch (error) {
      if (sessionId !== this.ttsSessionId) return;
      this.ttsState = 'error';
      this.ttsError = error instanceof Error ? error.message : 'Text-to-speech failed.';
      this.cleanupTtsAudio();
    }
  }

  private async loadNextTtsSection(sessionId: number): Promise<boolean> {
    const sectionCount = this.viewManager.getSectionCount();
    let next = this.ttsSectionIndex + 1;
    while (sessionId === this.ttsSessionId && next < sectionCount) {
      this.ttsState = 'loading';
      await firstValueFrom(this.viewManager.goToSection(next));
      await new Promise(resolve => setTimeout(resolve, 60));
      if (sessionId !== this.ttsSessionId) return false;
      const chunks = this.viewManager.getTtsChunksFromCurrentSection(this.ttsChunkChars);
      this.ttsSectionIndex = next;
      if (chunks.length) {
        this.ttsPendingChunks = chunks;
        return true;
      }
      next += 1;
    }
    return false;
  }

  private finishTtsPlayback(): void {
    this.cleanupTtsAudio();
    for (const item of this.ttsAudioQueue) URL.revokeObjectURL(item.url);
    this.ttsAudioQueue = [];
    this.ttsPendingChunks = [];
    this.ttsGenerationPromise = null;
    this.ttsIsGenerating = false;
    this.ttsSectionIndex = -1;
    this.ttsState = 'idle';
  }

  private cleanupTtsAudio(): void {
    if (this.ttsAudio) {
      this.ttsAudio.onended = null;
      this.ttsAudio.onerror = null;
      this.ttsAudio = null;
    }
    if (this.ttsObjectUrl) {
      URL.revokeObjectURL(this.ttsObjectUrl);
      this.ttsObjectUrl = null;
    }
  }
'''
if "async readAloud(): Promise<void>" not in reader:
    marker = "  onNoteSave(result: NoteDialogResult): void {\n"
    if marker not in reader:
        raise SystemExit("Upstream changed: onNoteSave() anchor not found")
    reader = reader.replace(marker, methods + "\n" + marker, 1)

# Teardown before normal reader destruction.
reader = replace_once(
    reader,
    "  ngOnDestroy(): void {\n    this.destroy$.next();",
    "  ngOnDestroy(): void {\n"
    "    this.stopTts();\n"
    "    this.ttsBrowserEngine?.destroy?.();\n"
    "    this.ttsBrowserEngine = null;\n"
    "    this.destroy$.next();",
    "reader ngOnDestroy()",
)
reader_ts_file.write_text(reader)

reader_html_file = path("booklore-ui/src/app/features/readers/ebook-reader/ebook-reader.component.html")
reader_html = reader_html_file.read_text()
controls = r'''
  @if (ttsState === 'idle' || ttsState === 'error') {
    <div class="tts-mobile-start-control"
         [class.tts-header-visible]="headerVisible"
         (click)="$event.stopPropagation()">
      <button class="tts-mobile-start-button" type="button"
              [class.tts-mobile-start-armed]="ttsTapToStartArmed"
              (click)="toggleTtsTapToStart()"
              [attr.title]="ttsTapToStartArmed ? 'Cancel tap-to-start' : 'Read from here'"
              [attr.aria-label]="ttsTapToStartArmed ? 'Cancel choosing reading start' : 'Choose where reading starts'">
        <span class="tts-mobile-start-icon">{{ ttsTapToStartArmed ? '✕' : '▶' }}</span>
        <span>{{ ttsTapToStartArmed ? 'Tap text…' : 'Read from here' }}</span>
      </button>
    </div>
  }

  @if (ttsState === 'loading' || ttsState === 'playing' || ttsState === 'paused' || ttsIsGenerating) {
    <div class="tts-reader-controls"
         [class.tts-header-visible]="headerVisible"
         (click)="$event.stopPropagation()">
      @if (ttsState === 'playing' || ttsState === 'paused') {
        <button class="tts-button tts-button-primary" type="button"
                (click)="toggleTtsPause()"
                [attr.title]="ttsState === 'paused' ? 'Resume' : 'Pause'"
                [attr.aria-label]="ttsState === 'paused' ? 'Resume reading' : 'Pause reading'">
          <span class="tts-transport-icon">{{ ttsState === 'paused' ? '▶' : '⏸' }}</span>
        </button>
      }
      <button class="tts-button" type="button" (click)="stopTts()" title="Stop" aria-label="Stop reading">
        <span class="tts-transport-icon">■</span>
      </button>
      @if (ttsIsGenerating || ttsState === 'loading') {
        <div class="tts-loading-indicator" title="Generating audio" aria-label="Generating audio">
          <span class="tts-loading-spinner"></span>
        </div>
      }
    </div>
  }
'''
if "tts-reader-controls" not in reader_html:
    marker = "  <app-reader-navbar\n"
    if marker not in reader_html:
        raise SystemExit("Upstream changed: reader navbar anchor not found")
    reader_html = reader_html.replace(marker, controls + "\n" + marker, 1)
reader_html_file.write_text(reader_html)

reader_scss_file = path("booklore-ui/src/app/features/readers/ebook-reader/ebook-reader.component.scss")
reader_scss = reader_scss_file.read_text()
reader_css = r'''
/* BookLore Reader custom TTS controls */
.tts-mobile-start-control {
  display: none;
  position: fixed;
  top: .65rem;
  right: .65rem;
  z-index: 13050;
  transition: top .25s ease-out;
}
.tts-mobile-start-control.tts-header-visible { top: calc(36px + .65rem); }
.tts-mobile-start-button {
  min-height: 2.65rem;
  padding: 0 .85rem;
  border: 1px solid rgba(255,255,255,.22);
  border-radius: .7rem;
  background: rgba(24,24,27,.88);
  color: #fff;
  display: inline-flex;
  align-items: center;
  gap: .5rem;
  font: 600 .86rem/1 system-ui, sans-serif;
  box-shadow: 0 4px 18px rgba(0,0,0,.25);
  backdrop-filter: blur(8px);
  touch-action: manipulation;
}
.tts-mobile-start-button.tts-mobile-start-armed {
  background: #fff;
  color: #18181b;
}
.tts-mobile-start-icon { font: 700 .9rem/1 system-ui, sans-serif; }
@media (hover: none) and (pointer: coarse) {
  .tts-mobile-start-control { display: flex; }
}

.tts-reader-controls {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 13050;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.45rem;
  padding: 0.4rem;
  border-radius: 0.75rem;
  background: rgba(24, 24, 27, 0.82);
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(8px);
  transition: top 0.25s ease-out;
}
.tts-reader-controls.tts-header-visible { top: calc(36px + 1rem); }
.tts-button, .tts-loading-indicator {
  width: 2.65rem;
  height: 2.65rem;
  min-width: 2.65rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.tts-button {
  padding: 0;
  border: 1px solid rgba(255,255,255,.22);
  border-radius: .55rem;
  background: transparent;
  color: #fff;
  cursor: pointer;
}
.tts-button:hover { background: rgba(255,255,255,.12); }
.tts-button-primary { background: #fff; color: #18181b; }
.tts-transport-icon { font: 700 1.15rem/1 system-ui, sans-serif; }
.tts-loading-spinner {
  width: 1.15rem;
  height: 1.15rem;
  border: 2px solid rgba(255,255,255,.32);
  border-top-color: #fff;
  border-radius: 50%;
  animation: tts-spin .75s linear infinite;
}
@keyframes tts-spin { to { transform: rotate(360deg); } }
@media (max-width: 640px) {
  .tts-mobile-start-control { display: flex; }
  .tts-reader-controls { top: .65rem; right: .65rem; }
  .tts-reader-controls.tts-header-visible { top: calc(36px + .65rem); }
}
'''
reader_scss = append_once(reader_scss, "BookLore Reader custom TTS controls", reader_css)
reader_scss_file.write_text(reader_scss)

# ---------------------------------------------------------------------------
# Full Reader settings tab. Saved per browser/device on slider release/change.
# ---------------------------------------------------------------------------
settings_ts_file = path("booklore-ui/src/app/features/readers/ebook-reader/dialogs/settings-dialog.component.ts")
settings_ts = settings_ts_file.read_text()
settings_ts = replace_once(
    settings_ts,
    "activeTab: 'theme' | 'typography' | 'layout' = 'theme';",
    "activeTab: 'theme' | 'typography' | 'layout' | 'reader' = 'theme';",
    "settings activeTab union",
)
settings_state = r'''
  ttsSentenceSilence = 0.40;
  ttsChunkChars = 650;
  ttsPrefetchChunks = 1;
  ttsSpeechSpeed = 1.0;
  ttsLocalMode = false;
  private readonly ttsSettingsKey = 'bookloreReaderTtsSettings';
'''
if "ttsSentenceSilence = 0.40" not in settings_ts:
    settings_ts = replace_once(
        settings_ts,
        "  selectedAnnotationColor: string = '#FFFF00';\n",
        "  selectedAnnotationColor: string = '#FFFF00';\n" + settings_state,
        "settings selectedAnnotationColor",
    )
settings_ts = replace_once(
    settings_ts,
    "    this.selectedAnnotationColor = this.getSelectedAnnotationColor();\n  }",
    "    this.selectedAnnotationColor = this.getSelectedAnnotationColor();\n"
    "    this.loadTtsSettings();\n"
    "  }",
    "settings ngOnInit",
)
settings_methods = r'''
  private loadTtsSettings(): void {
    try {
      const saved = JSON.parse(localStorage.getItem(this.ttsSettingsKey) || 'null');
      if (!saved) return;
      this.ttsSentenceSilence = Number(saved.sentenceSilence ?? 0.40);
      this.ttsChunkChars = Number(saved.chunkChars ?? 650);
      this.ttsPrefetchChunks = Number(saved.prefetchChunks ?? 1);
      this.ttsSpeechSpeed = Number(saved.speechSpeed ?? 1.0);
      this.ttsLocalMode = Boolean(saved.localMode);
    } catch (error) {
      console.warn('Could not load TTS settings:', error);
    }
  }

  private saveTtsSettings(): void {
    const settings = {
      sentenceSilence: Math.min(1.5, Math.max(0, this.ttsSentenceSilence)),
      chunkChars: Math.round(Math.min(2000, Math.max(250, this.ttsChunkChars))),
      prefetchChunks: Math.round(Math.min(3, Math.max(1, this.ttsPrefetchChunks))),
      speechSpeed: Math.min(1.6, Math.max(0.6, this.ttsSpeechSpeed)),
      localMode: this.ttsLocalMode
    };
    localStorage.setItem(this.ttsSettingsKey, JSON.stringify(settings));
    window.dispatchEvent(new CustomEvent('booklore-tts-settings-changed', {detail: settings}));
  }

  commitTtsSettings(): void { this.saveTtsSettings(); }
  toggleTtsLocalMode(): void { this.ttsLocalMode = !this.ttsLocalMode; this.saveTtsSettings(); }
  resetTtsSettings(): void {
    this.ttsSentenceSilence = 0.40;
    this.ttsChunkChars = 650;
    this.ttsPrefetchChunks = 1;
    this.ttsSpeechSpeed = 1.0;
    this.ttsLocalMode = false;
    this.saveTtsSettings();
  }
'''
if "private loadTtsSettings(): void" not in settings_ts:
    marker = "  setAnnotationColor(color: string): void {\n"
    if marker not in settings_ts:
        raise SystemExit("Upstream changed: settings setAnnotationColor() not found")
    settings_ts = settings_ts.replace(marker, settings_methods + "\n" + marker, 1)
settings_ts_file.write_text(settings_ts)

settings_html_file = path("booklore-ui/src/app/features/readers/ebook-reader/dialogs/settings-dialog.component.html")
settings_html = settings_html_file.read_text()
if "activeTab === 'reader'" not in settings_html:
    settings_html = replace_once(
        settings_html,
        "        <button\n          class=\"tab\"\n          [class.active]=\"activeTab === 'layout'\"\n          (click)=\"activeTab = 'layout'\">\n          {{ t('layoutTab') }}\n        </button>",
        "        <button\n          class=\"tab\"\n          [class.active]=\"activeTab === 'layout'\"\n          (click)=\"activeTab = 'layout'\">\n          {{ t('layoutTab') }}\n        </button>\n"
        "        <button class=\"tab\" [class.active]=\"activeTab === 'reader'\" (click)=\"activeTab = 'reader'\">Reader</button>",
        "layout tab",
    )
    panel = r'''
      @if (activeTab === 'reader') {
        <div class="tab-content">
          <div class="section-header">Text to speech</div>
          <div class="control"><label>Sentence pause</label><div class="control-right tts-range-control">
            <input type="range" min="0" max="1.5" step="0.05" [(ngModel)]="ttsSentenceSilence" (change)="commitTtsSettings()" />
            <span class="value">{{ ttsSentenceSilence | number:'1.2-2' }} s</span>
          </div></div>
          <div class="tts-setting-hint">Saved when the slider is released. Applies to the next TTS session.</div>

          <div class="control"><label>Chunk size</label><div class="control-right tts-range-control">
            <input type="range" min="250" max="2000" step="50" [(ngModel)]="ttsChunkChars" (change)="commitTtsSettings()" />
            <span class="value">{{ ttsChunkChars }} chars</span>
          </div></div>

          <div class="control"><label>Queue ahead</label><div class="control-right tts-range-control">
            <input type="range" min="1" max="3" step="1" [(ngModel)]="ttsPrefetchChunks" (change)="commitTtsSettings()" />
            <span class="value">{{ ttsPrefetchChunks }}</span>
          </div></div>

          <div class="control"><label>Speech speed</label><div class="control-right tts-range-control">
            <input type="range" min="0.6" max="1.6" step="0.05" [(ngModel)]="ttsSpeechSpeed" (change)="commitTtsSettings()" />
            <span class="value">{{ ttsSpeechSpeed | number:'1.2-2' }}×</span>
          </div></div>

          <div class="section-header">Generation location</div>
          <div class="toggle-control">
            <div class="tts-toggle-copy"><span>Local mode</span><small>Run Piper directly in this browser using WebAssembly/ONNX. No local server or container is required.</small></div>
            <button class="switch" [class.active]="ttsLocalMode" (click)="toggleTtsLocalMode()"><span class="slider"></span></button>
          </div>
          @if (ttsLocalMode) {
            <div class="tts-browser-local-info"><strong>Browser Piper</strong><span>en_US-libritts_r-medium · speaker 0 / 3922</span><small>The model is downloaded by the browser; the book text stays on the reading device during synthesis.</small></div>
          }
          <div class="tts-settings-actions"><button type="button" class="tts-reset-button" (click)="resetTtsSettings()">Reset TTS settings</button></div>
        </div>
      }
'''
    marker = "    </div>\n  </div>\n</div>\n</ng-container>"
    if marker not in settings_html:
        raise SystemExit("Upstream changed: settings dialog closing anchor not found")
    settings_html = settings_html.replace(marker, panel + marker, 1)
settings_html_file.write_text(settings_html)

# ngModel is needed for the Reader sliders.
settings_ts = settings_ts_file.read_text()
if "FormsModule" not in settings_ts:
    settings_ts = settings_ts.replace(
        "import {DecimalPipe, DOCUMENT} from '@angular/common';",
        "import {DecimalPipe, DOCUMENT} from '@angular/common';\nimport {FormsModule} from '@angular/forms';",
        1,
    )
    settings_ts = settings_ts.replace("imports: [DecimalPipe, TranslocoDirective]", "imports: [DecimalPipe, TranslocoDirective, FormsModule]", 1)
    settings_ts_file.write_text(settings_ts)

settings_scss_file = path("booklore-ui/src/app/features/readers/ebook-reader/dialogs/settings-dialog.component.scss")
settings_scss = settings_scss_file.read_text()
settings_css = r'''
/* Custom Reader/TTS settings */
.tts-range-control { flex: 1; max-width: 260px; }
.tts-setting-hint { color: $text-muted; font-size: 11px; line-height: 1.45; margin: -8px 0 18px; }
.tts-toggle-copy { display: flex; flex-direction: column; gap: 3px; max-width: 78%; }
.tts-toggle-copy small { color: $text-muted; font-size: 11px; line-height: 1.35; }
.tts-browser-local-info { margin-top: 10px; padding: 10px 12px; border: 1px solid $border-color; border-radius: 8px; background: rgba(255,255,255,.04); display: flex; flex-direction: column; gap: 4px; }
.tts-browser-local-info strong { color: $text-primary; font-size: 13px; }
.tts-browser-local-info span { color: $text-secondary; font-size: 12px; }
.tts-browser-local-info small { color: $text-muted; font-size: 11px; line-height: 1.4; }
.tts-settings-actions { margin-top: 24px; display: flex; justify-content: flex-end; }
.tts-reset-button { border: 1px solid $border-color; background: rgba(255,255,255,.04); color: $text-secondary; border-radius: 7px; padding: 8px 12px; cursor: pointer; }
@media (max-width: 600px) { .tabs { overflow-x: auto; justify-content: flex-start; } .tab { min-width: 76px; padding-left: 12px; padding-right: 12px; } }
'''
settings_scss = append_once(settings_scss, "Custom Reader/TTS settings", settings_css)
settings_scss_file.write_text(settings_scss)

# ---------------------------------------------------------------------------
# Paste raw text -> EPUB -> DIRECT library upload (not BookDrop).
# ---------------------------------------------------------------------------
feature = UI / "src/app/features/text-to-epub"
feature.mkdir(parents=True, exist_ok=True)

text_epub_ts = r'''import {Component, DestroyRef, inject} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {HttpClient, HttpEventType, HttpRequest} from '@angular/common/http';
import {MessageService} from 'primeng/api';
import {Select} from 'primeng/select';
import {ProgressBar} from 'primeng/progressbar';
import {Router} from '@angular/router';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import JSZip from 'jszip';
import {v4 as uuidv4} from 'uuid';
import {LibraryService} from '../book/service/library.service';
import {Library, LibraryPath} from '../book/model/library.model';
import {API_CONFIG} from '../../core/config/api-config';

@Component({selector: 'app-text-to-epub', standalone: true, imports: [FormsModule, Select, ProgressBar], templateUrl: './text-to-epub.component.html', styleUrl: './text-to-epub.component.scss'})
export class TextToEpubComponent {
  private readonly libraryService = inject(LibraryService);
  private readonly http = inject(HttpClient);
  private readonly messages = inject(MessageService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  libraries: Library[] = [];
  private _selectedLibrary: Library | null = null;
  private _selectedPath: LibraryPath | null = null;
  title = `Pasted Text — ${new Date().toLocaleString()}`;
  author = '';
  rawText = '';
  saving = false;
  progress = 0;
  phase = '';
  lastSavedLibraryId: number | null = null;
  private readonly destinationKey = 'booklorePasteToEpubDestination';

  constructor() {
    this.libraryService.libraryState$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(state => {
      this.libraries = state?.libraries ?? [];
      this.restoreDestination();
    });
  }
  get selectedLibrary() { return this._selectedLibrary; }
  set selectedLibrary(v: Library | null) { this._selectedLibrary = v; this._selectedPath = v?.paths?.[0] ?? null; this.saveDestination(); }
  get selectedPath() { return this._selectedPath; }
  set selectedPath(v: LibraryPath | null) { this._selectedPath = v; this.saveDestination(); }
  get characterCount() { return this.rawText.length; }
  get wordCount() { const t = this.rawText.trim(); return t ? t.split(/\s+/).length : 0; }
  get canSave() { return !!(!this.saving && this.rawText.trim() && this.title.trim() && this.selectedLibrary?.id != null && this.selectedPath?.id != null); }

  async saveToLibrary(): Promise<void> {
    if (!this.canSave) return;
    this.saving = true; this.progress = 0; this.phase = 'Building EPUB…'; this.lastSavedLibraryId = null;
    try {
      const blob = await this.buildEpub(this.title.trim(), this.author.trim(), this.rawText);
      const filename = `${this.safeFilename(this.title.trim())}.epub`;
      const file = new File([blob], filename, {type: 'application/epub+zip'});
      const form = new FormData();
      form.append('file', file, filename);
      const libraryId = this.selectedLibrary!.id!;
      const pathId = this.selectedPath!.id!;
      const url = `${API_CONFIG.BASE_URL}/api/v1/files/upload?libraryId=${encodeURIComponent(String(libraryId))}&pathId=${encodeURIComponent(String(pathId))}`;
      const request = new HttpRequest('POST', url, form, {reportProgress: true});
      this.phase = 'Uploading directly to library…';
      await new Promise<void>((resolve, reject) => this.http.request(request).subscribe({
        next: event => {
          if (event.type === HttpEventType.UploadProgress && event.total) this.progress = Math.round(event.loaded / event.total * 100);
          if (event.type === HttpEventType.Response) { this.progress = 100; resolve(); }
        }, error: reject
      }));
      this.lastSavedLibraryId = libraryId;
      this.phase = 'Added to library';
      this.messages.add({severity: 'success', summary: 'EPUB added', detail: `"${this.title.trim()}" was uploaded directly to ${this.selectedLibrary!.name}.`, life: 5000});
    } catch (error: any) {
      this.phase = '';
      this.messages.add({severity: 'error', summary: 'Could not add EPUB', detail: error?.error?.message || error?.message || 'Upload failed.', life: 7000});
    } finally { this.saving = false; }
  }

  openSavedLibrary(): void { if (this.lastSavedLibraryId != null) void this.router.navigate(['/library', this.lastSavedLibraryId, 'books']); }
  clearText(): void { if (!this.saving) { this.rawText = ''; this.author = ''; this.title = `Pasted Text — ${new Date().toLocaleString()}`; this.phase = ''; this.lastSavedLibraryId = null; } }

  private restoreDestination(): void {
    if (!this.libraries.length) return;
    try {
      const saved = JSON.parse(localStorage.getItem(this.destinationKey) || 'null');
      const library = this.libraries.find(l => l.id === saved?.libraryId);
      const p = library?.paths?.find(x => x.id === saved?.pathId);
      if (library && p) { this._selectedLibrary = library; this._selectedPath = p; return; }
    } catch {}
    if (this.libraries.length === 1) { this._selectedLibrary = this.libraries[0]; this._selectedPath = this.libraries[0].paths?.[0] ?? null; }
  }
  private saveDestination(): void {
    if (this._selectedLibrary?.id == null || this._selectedPath?.id == null) return;
    localStorage.setItem(this.destinationKey, JSON.stringify({libraryId: this._selectedLibrary.id, pathId: this._selectedPath.id}));
  }
  private safeFilename(v: string): string { return v.replace(/[\/\\:*?"<>|]/g, '-').replace(/\s+/g, ' ').trim().replace(/[. ]+$/g, '') || 'Pasted Text'; }
  private escape(v: string): string { return v.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  private xml(v: string): string { return this.escape(v).replace(/"/g,'&quot;').replace(/'/g,'&apos;'); }

  private split(text: string, limit = 40000): string[][] {
    const paragraphs = text.replace(/\r\n?/g,'\n').trim().split(/\n\s*\n/g).map(x => x.trim()).filter(Boolean);
    const sections: string[][] = []; let current: string[] = []; let count = 0;
    for (let paragraph of paragraphs) {
      while (paragraph.length > limit) {
        let cut = paragraph.lastIndexOf(' ', limit); if (cut < limit * .65) cut = limit;
        const part = paragraph.slice(0, cut).trim();
        if (current.length) { sections.push(current); current = []; count = 0; }
        sections.push([part]); paragraph = paragraph.slice(cut).trim();
      }
      const extra = paragraph.length + (current.length ? 2 : 0);
      if (current.length && count + extra > limit) { sections.push(current); current = []; count = 0; }
      if (paragraph) { current.push(paragraph); count += extra; }
    }
    if (current.length) sections.push(current);
    return sections;
  }

  private async buildEpub(title: string, author: string, text: string): Promise<Blob> {
    const zip = new JSZip(); const uuid = uuidv4(); const sections = this.split(text); const modified = new Date().toISOString().replace(/\.\d{3}Z$/,'Z');
    zip.file('mimetype','application/epub+zip',{compression:'STORE'});
    zip.file('META-INF/container.xml','<?xml version="1.0" encoding="UTF-8"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>');
    zip.file('OEBPS/styles.css','body{font-family:Georgia,"Times New Roman",serif;line-height:1.58;margin:5%}h1{line-height:1.2}.byline{opacity:.72;margin-bottom:2em}p{margin:0 0 1em}');
    const manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>','<item id="css" href="styles.css" media-type="text/css"/>'];
    const spine: string[] = []; const nav: string[] = [];
    sections.forEach((section, i) => {
      const n=i+1, id=`s${n}`, href=`text/section-${String(n).padStart(3,'0')}.xhtml`, label=sections.length===1?title:`Part ${n}`;
      manifest.push(`<item id="${id}" href="${href}" media-type="application/xhtml+xml"/>`); spine.push(`<itemref idref="${id}"/>`); nav.push(`<li><a href="${href}">${this.xml(label)}</a></li>`);
      const heading=i===0?`<h1>${this.escape(title)}</h1>${author?`<p class="byline">${this.escape(author)}</p>`:''}`:'';
      const body=section.map(p=>`<p>${this.escape(p).replace(/\n/g,'<br/>')}</p>`).join('\n');
      zip.file(`OEBPS/${href}`,`<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head><meta charset="UTF-8"/><title>${this.xml(label)}</title><link rel="stylesheet" type="text/css" href="../styles.css"/></head><body>${heading}${body}</body></html>`);
    });
    zip.file('OEBPS/nav.xhtml',`<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><meta charset="UTF-8"/><title>Contents</title></head><body><nav epub:type="toc"><h1>Contents</h1><ol>${nav.join('')}</ol></nav></body></html>`);
    zip.file('OEBPS/content.opf',`<?xml version="1.0" encoding="UTF-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="book-id">urn:uuid:${uuid}</dc:identifier><dc:title>${this.xml(title)}</dc:title>${author?`<dc:creator>${this.xml(author)}</dc:creator>`:''}<dc:language>und</dc:language><meta property="dcterms:modified">${modified}</meta></metadata><manifest>${manifest.join('')}</manifest><spine>${spine.join('')}</spine></package>`);
    return zip.generateAsync({type:'blob',mimeType:'application/epub+zip',compression:'DEFLATE',compressionOptions:{level:6}}, m => this.progress=Math.round(m.percent));
  }
}
'''
(feature / "text-to-epub.component.ts").write_text(text_epub_ts)
(feature / "text-to-epub.component.html").write_text(r'''<div class="paste-epub-page"><div class="paste-epub-shell">
  <header><h1>Paste text to EPUB</h1><p>Paste anything you want to read or listen to, then add it directly to a BookLore library.</p></header>
  <section class="card destination"><label>Library<p-select [options]="libraries" optionLabel="name" [(ngModel)]="selectedLibrary" placeholder="Select library" appendTo="body" /></label><label>Folder<p-select [options]="selectedLibrary?.paths || []" optionLabel="path" [(ngModel)]="selectedPath" placeholder="Select folder" appendTo="body" /></label></section>
  <section class="card editor"><div class="metadata"><label>Title<input [(ngModel)]="title" /></label><label>Author <small>optional</small><input [(ngModel)]="author" /></label></div><label>Raw text<textarea [(ngModel)]="rawText" spellcheck="true" placeholder="Paste text here…"></textarea></label>
  <div class="footer"><div>{{ characterCount.toLocaleString() }} characters · {{ wordCount.toLocaleString() }} words</div><div class="actions"><button class="secondary" (click)="clearText()">Clear</button><button class="primary" [disabled]="!canSave" (click)="saveToLibrary()">{{ saving ? 'Working…' : 'Save to Library' }}</button></div></div>
  @if (phase) { <div class="status"><span>{{ phase }}</span>@if (saving) { <p-progressbar [value]="progress" [showValue]="false" /> }@if (!saving && lastSavedLibraryId !== null) { <button class="secondary" (click)="openSavedLibrary()">Open Library</button> }</div> }
  </section><p class="note">This path bypasses BookDrop review: the generated EPUB is uploaded directly to the selected library/path.</p>
</div></div>''')
(feature / "text-to-epub.component.scss").write_text(r'''.paste-epub-page{min-height:calc(100vh - 4rem);padding:2rem;color:var(--text-color)}.paste-epub-shell{width:min(1100px,100%);margin:0 auto}header{margin-bottom:1.2rem}header h1{margin:0}header p{color:var(--text-color-secondary)}.card{background:var(--surface-card);border:1px solid var(--surface-border);border-radius:.9rem;padding:1.1rem;margin-bottom:1rem}.destination,.metadata{display:grid;grid-template-columns:1fr 1fr;gap:.85rem}label{display:flex;flex-direction:column;gap:.4rem;font-weight:600}input,textarea{width:100%;box-sizing:border-box;border:1px solid var(--surface-border);border-radius:.65rem;background:var(--surface-ground);color:var(--text-color);font:inherit;padding:.7rem}textarea{min-height:55vh;resize:vertical;line-height:1.5}.metadata{margin-bottom:.9rem}.footer{display:flex;justify-content:space-between;gap:1rem;margin-top:.9rem;color:var(--text-color-secondary)}.actions{display:flex;gap:.6rem}button{border:0;border-radius:.6rem;padding:.65rem .9rem;font:inherit;font-weight:650;cursor:pointer}.primary{background:var(--primary-color);color:white}.secondary{border:1px solid var(--surface-border);background:var(--surface-ground);color:var(--text-color)}.status{margin-top:1rem;display:grid;gap:.6rem}.note{text-align:center;color:var(--text-color-secondary);font-size:.8rem}@media(max-width:760px){.paste-epub-page{padding:1rem .75rem}.destination,.metadata{grid-template-columns:1fr}.footer{flex-direction:column}}''')

routes_file = path("booklore-ui/src/app/app.routes.ts")
routes = routes_file.read_text()
if "path: 'text-to-epub'" not in routes:
    marker = "      {path: 'notebook', loadComponent: () => import('./features/notebook/components/notebook/notebook.component').then(m => m.NotebookComponent), canActivate: [AuthGuard]},\n"
    route = "      {path: 'text-to-epub', loadComponent: () => import('./features/text-to-epub/text-to-epub.component').then(m => m.TextToEpubComponent), canActivate: [AuthGuard]},\n"
    if marker not in routes:
        raise SystemExit("Upstream changed: notebook route anchor not found")
    routes = routes.replace(marker, marker + route, 1)
routes_file.write_text(routes)

top_html_file = path("booklore-ui/src/app/shared/layout/component/layout-topbar/app.topbar.component.html")
top_html = top_html_file.read_text()
heart = re.compile(r'\s*<li class="topbar-item-relative heart-button topbar-item".*?</li>', re.S)
if "navigateToTextImporter()" not in top_html:
    replacement = '''\n        <li><button type="button" class="topbar-item" (click)="navigateToTextImporter()" pTooltip="Paste text to EPUB" tooltipPosition="bottom"><i class="pi pi-file-edit topbar-icon"></i></button></li>'''
    top_html, n = heart.subn(lambda _: replacement, top_html, count=1)
    if n != 1:
        raise SystemExit("Upstream changed: support heart not found")
    mobile = re.compile(r'<li>\s*<button\s*class="mobile-menu-item"\s*\(click\)="openGithubSupportDialog\(\); mobileMenu\.hide\(\)"\s*>.*?</button>\s*</li>', re.S)
    mobile_repl = '''<li><button class="mobile-menu-item" (click)="navigateToTextImporter(); mobileMenu.hide()"><i class="pi pi-file-edit topbar-icon"></i>Paste text to EPUB</button></li>'''
    top_html, n = mobile.subn(lambda _: mobile_repl, top_html, count=1)
    if n != 1:
        raise SystemExit("Upstream changed: mobile support item not found")
top_html_file.write_text(top_html)

top_ts_file = path("booklore-ui/src/app/shared/layout/component/layout-topbar/app.topbar.component.ts")
top_ts = top_ts_file.read_text()
if "navigateToTextImporter()" not in top_ts:
    top_ts = replace_once(top_ts, "  navigateToSettings() {\n    this.router.navigate(['/settings']);\n  }", "  navigateToSettings() {\n    this.router.navigate(['/settings']);\n  }\n\n  navigateToTextImporter() {\n    this.router.navigate(['/text-to-epub']);\n  }", "topbar navigateToSettings()")
top_ts_file.write_text(top_ts)

print("BookLore Reader customizations applied successfully.")
