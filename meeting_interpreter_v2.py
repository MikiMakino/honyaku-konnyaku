from __future__ import annotations

import argparse
import datetime as dt
import queue
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from faster_whisper import WhisperModel

try:
    import sounddevice as sd
except OSError:
    sd = None
from transformers import MarianMTModel, MarianTokenizer

# Supported language pairs and their Helsinki OPUS-MT model names
_TRANSLATION_MODELS: dict[tuple[str, str], str] = {
    ("ja", "en"): "Helsinki-NLP/opus-mt-tc-big-ja-en",
    ("en", "ja"): "Helsinki-NLP/opus-mt-tc-big-en-ja",
}


@dataclass
class SubtitleLine:
    timestamp: str
    direction: str
    original: str
    translated: str


class TranslationEngine:
    def __init__(self) -> None:
        self._tokenizers: dict[tuple[str, str], MarianTokenizer] = {}
        self._models: dict[tuple[str, str], MarianMTModel] = {}
        for pair, model_name in _TRANSLATION_MODELS.items():
            print(f"  Loading {pair[0]}→{pair[1]} model ({model_name})...")
            self._tokenizers[pair] = MarianTokenizer.from_pretrained(model_name)
            self._models[pair] = MarianMTModel.from_pretrained(model_name)
        print("Translation models ready.")

    def translate(self, text: str, src: str, tgt: str) -> str:
        pair = (src, tgt)
        if pair not in self._models:
            return f"[no model for {src}→{tgt}] {text}"
        tokenizer = self._tokenizers[pair]
        model = self._models[pair]
        inputs = tokenizer(
            [text],
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )
        outputs = model.generate(**inputs)
        return tokenizer.decode(outputs[0], skip_special_tokens=True)

    def gloss(self, text: str, src: str, tgt: str) -> str:
        """Translate word by word and join with ' / ' (en→ja only)."""
        import re
        words = re.findall(r"[A-Za-z']+|[0-9]+(?:\.[0-9]+)?|[^\w\s]", text)
        glosses = []
        for word in words:
            if re.match(r"[A-Za-z]", word):
                glosses.append(self.translate(word, src, tgt))
            else:
                glosses.append(word)
        return " / ".join(glosses)


class MeetingInterpreter:
    def __init__(
        self,
        output_path: Path,
        whisper_model_size: str = "small",
        display_limit: int = 8,
        gloss_mode: bool = False,
    ) -> None:
        self.output_path = output_path
        self.display_limit = display_limit
        self.gloss_mode = gloss_mode
        self.history: list[SubtitleLine] = []
        self._lock = threading.Lock()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Loading Whisper model ({whisper_model_size})...")
        self.whisper = WhisperModel(whisper_model_size, device="cpu", compute_type="int8")
        print("Loading translation models...")
        self.translation = TranslationEngine()
        print("\nAll models loaded. Ready.\n")

    def process_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> None:
        timestamp = dt.datetime.now().strftime("%H:%M:%S")

        segments, info = self.whisper.transcribe(
            audio,
            beam_size=1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )

        # Show indicator immediately so the user knows processing has started
        print(f"[{timestamp}] ORG: 🎤 ...", end="", flush=True)

        # Print each segment as Whisper decodes it
        parts: list[str] = []
        for seg in segments:
            part = seg.text.strip()
            if part:
                parts.append(part)
                print(f"\r[{timestamp}] ORG: {' '.join(parts)}", end="", flush=True)

        text = " ".join(parts).strip()
        if not text:
            return

        print()  # End the ORG line

        detected = info.language
        src = detected if detected in ("ja", "en") else "en"
        tgt = "ja" if src == "en" else "en"

        # Show placeholder while translating, then overwrite with result
        print(f"[{timestamp}] TRN: ...", end="", flush=True)
        if self.gloss_mode and src == "en" and tgt == "ja":
            translated = self.translation.gloss(text, src, tgt)
        else:
            translated = self.translation.translate(text, src, tgt)
        print(f"\r[{timestamp}] TRN: {translated}")
        print("-" * 72)

        line = SubtitleLine(
            timestamp=timestamp,
            direction=f"{src}→{tgt}",
            original=text,
            translated=translated,
        )
        with self._lock:
            self.history.append(line)
            self._save(line)

    def _save(self, line: SubtitleLine) -> None:
        with self.output_path.open("a", encoding="utf-8") as f:
            f.write(
                f"[{line.timestamp}] {line.direction}\n"
                f"  ORG: {line.original}\n"
                f"  TRN: {line.translated}\n\n"
            )

    def _render(self) -> None:
        print("\n" + "=" * 72)
        for item in self.history[-self.display_limit :]:
            print(f"[{item.timestamp}] {item.direction}")
            print(f"  ORG: {item.original}")
            print(f"  TRN: {item.translated}")
            print("-" * 72)


def run_mic_mode(
    app: MeetingInterpreter,
    sample_rate: int = 16000,
    silence_threshold: float = 0.02,
    silence_seconds: float = 0.6,
    max_seconds: float = 30.0,
) -> None:
    audio_queue: queue.Queue[np.ndarray] = queue.Queue()
    block_seconds = 0.1
    block_size = int(sample_rate * block_seconds)

    def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            print(status, file=sys.stderr)
        audio_queue.put(indata.copy().flatten())

    silence_blocks = int(silence_seconds / block_seconds)
    max_blocks = int(max_seconds / block_seconds)

    speech_buffer: list[np.ndarray] = []
    silent_count = 0
    has_speech = False

    if sd is None:
        print("Error: sounddevice is not available on this system.")
        return

    print("Listening... Press Ctrl+C to stop.\n")

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=block_size,
            callback=callback,
        ):
            while True:
                try:
                    chunk = audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                energy = float(np.sqrt(np.mean(chunk**2)))
                is_speech = energy > silence_threshold

                if is_speech:
                    has_speech = True
                    silent_count = 0
                elif has_speech:
                    silent_count += 1

                speech_buffer.append(chunk)

                flush = (has_speech and silent_count >= silence_blocks) or len(
                    speech_buffer
                ) >= max_blocks

                if flush and has_speech:
                    audio = np.concatenate(speech_buffer)
                    speech_buffer = []
                    has_speech = False
                    silent_count = 0
                    threading.Thread(
                        target=app.process_audio,
                        args=(audio, sample_rate),
                        daemon=True,
                    ).start()
                elif not has_speech:
                    # Trim pre-speech buffer to keep only recent context
                    keep = max(1, int(0.5 / block_seconds))
                    speech_buffer = speech_buffer[-keep:]

    except KeyboardInterrupt:
        print("\nStopped.")
        if speech_buffer and has_speech:
            audio = np.concatenate(speech_buffer)
            app.process_audio(audio, sample_rate)


def run_manual_mode(app: MeetingInterpreter) -> None:
    print("Manual mode. Enter text, /exit to quit.\n")
    while True:
        try:
            text = input("You> ").strip()
        except EOFError:
            break
        if text.lower() in {"/exit", "exit", "quit"}:
            break
        if text:
            # For manual mode, detect language by trying to guess from content
            # Simple heuristic: if any character is CJK, treat as Japanese
            has_cjk = any("　" <= c <= "鿿" or "＀" <= c <= "￯" for c in text)
            src = "ja" if has_cjk else "en"
            tgt = "en" if src == "ja" else "ja"
            translated = app.translation.translate(text, src, tgt)
            import datetime as dt
            line = SubtitleLine(
                timestamp=dt.datetime.now().strftime("%H:%M:%S"),
                direction=f"{src}→{tgt}",
                original=text,
                translated=translated,
            )
            with app._lock:
                app.history.append(line)
                app._save(line)
                app._render()


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline meeting interpreter (ja↔en). faster-whisper + Helsinki OPUS-MT."
    )
    parser.add_argument(
        "--mode",
        choices=["mic", "manual"],
        default="mic",
        help="Input mode (default: mic)",
    )
    parser.add_argument(
        "--output",
        default="meeting_script.txt",
        help="Output file path (default: meeting_script.txt)",
    )
    parser.add_argument(
        "--whisper-model",
        default="small",
        choices=["tiny", "base", "small", "medium"],
        help="Whisper model size (default: small)",
    )
    parser.add_argument(
        "--display-limit",
        type=int,
        default=8,
        help="Number of recent lines to show (default: 8)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Microphone sample rate (default: 16000)",
    )
    parser.add_argument(
        "--silence-threshold",
        type=float,
        default=0.02,
        help="Energy threshold for silence detection (default: 0.02)",
    )
    parser.add_argument(
        "--gloss",
        action="store_true",
        help="Word-by-word gloss mode for en→ja (show word meanings in original order)",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)

    app = MeetingInterpreter(
        output_path=Path(args.output),
        whisper_model_size=args.whisper_model,
        display_limit=args.display_limit,
        gloss_mode=args.gloss,
    )

    if args.mode == "mic":
        run_mic_mode(
            app,
            sample_rate=args.sample_rate,
            silence_threshold=args.silence_threshold,
        )
    else:
        run_manual_mode(app)

    print(f"\nScript saved to: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
