from __future__ import annotations

import argparse
import datetime as dt
import json
import queue
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import argostranslate.package as argos_package
    import argostranslate.translate as argos_translate
except ImportError:
    argos_package = None
    argos_translate = None

try:
    import sounddevice as sd
    import vosk
except ImportError:
    sd = None
    vosk = None


@dataclass
class SubtitleLine:
    timestamp: str
    original: str
    translated: str


class MeetingInterpreter:
    def __init__(
        self,
        source_lang: str,
        target_lang: str,
        output_path: Path,
        display_limit: int,
        translator: Any,
    ) -> None:
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.output_path = output_path
        self.display_limit = display_limit
        self.translator = translator
        self.history: list[SubtitleLine] = []

    def add_line(self, text: str) -> SubtitleLine | None:
        cleaned = text.strip()
        if not cleaned:
            return None

        translated = self.translator.translate(cleaned)
        line = SubtitleLine(
            timestamp=dt.datetime.now().strftime("%H:%M:%S"),
            original=cleaned,
            translated=translated,
        )
        self.history.append(line)
        self._append_to_file(line)
        self._render_last_lines()
        return line

    def _append_to_file(self, line: SubtitleLine) -> None:
        with self.output_path.open("a", encoding="utf-8") as f:
            f.write(
                f"[{line.timestamp}] ORG: {line.original}\n"
                f"[{line.timestamp}] TRN: {line.translated}\n\n"
            )

    def _render_last_lines(self) -> None:
        print("\n" + "=" * 72)
        print("Live Script")
        print("=" * 72)
        for item in self.history[-self.display_limit :]:
            print(f"[{item.timestamp}] ORG: {item.original}")
            print(f"[{item.timestamp}] TRN: {item.translated}")
            print("-" * 72)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Online meeting interpreter. "
            "Translate utterances and show script-style subtitles."
        )
    )
    parser.add_argument("--source", default="ja", help="Source language code (default: ja)")
    parser.add_argument("--target", default="en", help="Target language code (default: en)")
    parser.add_argument(
        "--mode",
        choices=["manual", "mic"],
        default="manual",
        help="Input mode: manual text or microphone",
    )
    parser.add_argument(
        "--output",
        default="meeting_script.txt",
        help="Output script file path",
    )
    parser.add_argument(
        "--display-limit",
        type=int,
        default=8,
        help="How many recent subtitle entries to show",
    )
    parser.add_argument(
        "--argos-model-file",
        default="",
        help="Path to local .argosmodel file to install before start",
    )
    parser.add_argument(
        "--vosk-model",
        default="",
        help="Path to local Vosk model directory for mic mode",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Microphone sample rate for Vosk",
    )
    return parser.parse_args(argv)


def install_argos_model_if_requested(model_file: str) -> None:
    if not model_file:
        return
    if argos_package is None:
        raise RuntimeError("argostranslate is not installed.")

    model_path = Path(model_file)
    if not model_path.exists():
        raise FileNotFoundError(f"Argos model not found: {model_path}")

    argos_package.install_from_path(str(model_path))
    print(f"Installed Argos model: {model_path}")


def build_argos_translation(source_lang: str, target_lang: str) -> Any:
    if argos_translate is None:
        raise RuntimeError("argostranslate is not installed.")

    installed_languages = argos_translate.get_installed_languages()
    from_lang = next((lang for lang in installed_languages if lang.code == source_lang), None)
    to_lang = next((lang for lang in installed_languages if lang.code == target_lang), None)

    if from_lang is None or to_lang is None:
        raise RuntimeError(
            "Required Argos language model is not installed. "
            "Install a local .argosmodel file with --argos-model-file first."
        )

    try:
        return from_lang.get_translation(to_lang)
    except Exception as ex:
        raise RuntimeError(
            f"No installed translation pair for {source_lang}->{target_lang}."
        ) from ex


def run_manual_mode(app: MeetingInterpreter) -> None:
    print("Manual mode started. Enter one utterance per line.")
    print("Type /exit to stop.")
    while True:
        try:
            text = input("You> ").strip()
        except EOFError:
            break

        if text.lower() in {"/exit", "exit", "quit"}:
            break

        try:
            app.add_line(text)
        except Exception as ex:
            print(f"Translation error: {ex}")


def run_mic_mode(app: MeetingInterpreter, vosk_model: str, sample_rate: int) -> None:
    if sd is None or vosk is None:
        print("sounddevice/vosk is not installed. Install requirements first.")
        return
    if not vosk_model:
        print("Mic mode requires --vosk-model path.")
        return

    model_path = Path(vosk_model)
    if not model_path.exists():
        print(f"Vosk model not found: {model_path}")
        return

    model = vosk.Model(str(model_path))
    recognizer = vosk.KaldiRecognizer(model, sample_rate)
    audio_queue: queue.Queue[bytes] = queue.Queue()

    def audio_callback(indata: bytes, frames: int, time_info: dict, status: Any) -> None:
        del frames, time_info
        if status:
            print(status, file=sys.stderr)
        audio_queue.put(bytes(indata))

    print("Mic mode started. Press Ctrl+C to stop.")

    try:
        with sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=audio_callback,
        ):
            while True:
                data = audio_queue.get()
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        app.add_line(text)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as ex:
        print(f"Mic mode error: {ex}")


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    output_path = Path(args.output)

    install_argos_model_if_requested(args.argos_model_file)
    translation = build_argos_translation(args.source, args.target)

    app = MeetingInterpreter(
        source_lang=args.source,
        target_lang=args.target,
        output_path=output_path,
        display_limit=max(1, args.display_limit),
        translator=translation,
    )

    print(
        "Starting interpreter "
        f"({args.source} -> {args.target}), mode={args.mode}, output={output_path}"
    )

    if args.mode == "manual":
        run_manual_mode(app)
    else:
        run_mic_mode(app, args.vosk_model, args.sample_rate)

    print(f"Saved script to: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
