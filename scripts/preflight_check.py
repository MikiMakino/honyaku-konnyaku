from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight check for offline meeting interpreter models."
    )
    parser.add_argument("--source", default="ja", help="Source language code")
    parser.add_argument("--target", default="en", help="Target language code")
    parser.add_argument(
        "--argos-model-file",
        default="",
        help="Optional path to local .argosmodel file to validate",
    )
    parser.add_argument(
        "--vosk-model",
        default="",
        help="Optional path to Vosk model directory to validate",
    )
    return parser.parse_args()


def check_argos(args: argparse.Namespace) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True

    try:
        import argostranslate.translate as argos_translate
    except ImportError:
        return False, [
            "[NG] argostranslate is not installed.",
            "     Run: pip install argostranslate",
        ]

    installed_languages = argos_translate.get_installed_languages()
    installed_codes = sorted({lang.code for lang in installed_languages})

    from_lang = next((lang for lang in installed_languages if lang.code == args.source), None)
    to_lang = next((lang for lang in installed_languages if lang.code == args.target), None)

    if from_lang is None or to_lang is None:
        ok = False
        messages.append(
            "[NG] Argos language package missing for requested codes: "
            f"{args.source}->{args.target}"
        )
        if installed_codes:
            messages.append("     Installed language codes: " + ", ".join(installed_codes))
        else:
            messages.append("     Installed language codes: none")
    else:
        try:
            from_lang.get_translation(to_lang)
            messages.append(f"[OK] Argos translation pair is available: {args.source}->{args.target}")
        except Exception:
            ok = False
            messages.append(f"[NG] Argos translation pair is NOT available: {args.source}->{args.target}")
            messages.append("     Install a matching .argosmodel and run interpreter with --argos-model-file once.")

    if args.argos_model_file:
        model_path = Path(args.argos_model_file)
        if model_path.exists() and model_path.is_file() and model_path.suffix == ".argosmodel":
            messages.append(f"[OK] .argosmodel file path exists: {model_path}")
        else:
            ok = False
            messages.append(f"[NG] .argosmodel file path invalid: {model_path}")

    return ok, messages


def check_vosk(args: argparse.Namespace) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True

    try:
        import vosk  # noqa: F401
        import sounddevice  # noqa: F401
    except ImportError:
        ok = False
        messages.append("[NG] vosk and/or sounddevice is not installed.")
        messages.append("     Run: pip install vosk sounddevice")

    if args.vosk_model:
        model_dir = Path(args.vosk_model)
        if model_dir.exists() and model_dir.is_dir():
            messages.append(f"[OK] Vosk model directory exists: {model_dir}")
        else:
            ok = False
            messages.append(f"[NG] Vosk model directory invalid: {model_dir}")

    return ok, messages


def main() -> int:
    args = parse_args()

    if args.source == args.target:
        print("[NG] --source and --target must be different.")
        return 1

    argos_ok, argos_messages = check_argos(args)
    vosk_ok, vosk_messages = check_vosk(args)

    print("Preflight check result")
    print("=" * 40)
    for message in argos_messages:
        print(message)
    for message in vosk_messages:
        print(message)

    if argos_ok and vosk_ok:
        print("\nOverall: OK")
        return 0

    print("\nOverall: NG")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
