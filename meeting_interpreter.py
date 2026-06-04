from __future__ import annotations

import argparse
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from deep_translator import GoogleTranslator

try:
    import speech_recognition as sr
except ImportError:
    sr = None


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
    ) -> None:
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.output_path = output_path
        self.display_limit = display_limit
        self.translator = GoogleTranslator(source=source_lang, target=target_lang)
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
        "--phrase-seconds",
        type=int,
        default=7,
        help="Phrase capture length for mic mode",
    )
    return parser.parse_args(argv)


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


def run_mic_mode(app: MeetingInterpreter, phrase_seconds: int, source_lang: str) -> None:
    if sr is None:
        print("speech_recognition is not installed. Install requirements first.")
        return

    recognizer = sr.Recognizer()
    print("Mic mode started. Press Ctrl+C to stop.")

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        while True:
            try:
                audio = recognizer.listen(source, phrase_time_limit=phrase_seconds)
                text = recognizer.recognize_google(audio, language=source_lang)
                app.add_line(text)
            except KeyboardInterrupt:
                print("\nStopped by user.")
                break
            except sr.UnknownValueError:
                print("Could not recognize speech.")
            except sr.RequestError as ex:
                print(f"Speech recognition error: {ex}")
            except Exception as ex:
                print(f"Unexpected error: {ex}")


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    output_path = Path(args.output)

    app = MeetingInterpreter(
        source_lang=args.source,
        target_lang=args.target,
        output_path=output_path,
        display_limit=max(1, args.display_limit),
    )

    print(
        "Starting interpreter "
        f"({args.source} -> {args.target}), mode={args.mode}, output={output_path}"
    )

    if args.mode == "manual":
        run_manual_mode(app)
    else:
        run_mic_mode(app, args.phrase_seconds, args.source)

    print(f"Saved script to: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
