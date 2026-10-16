"""VoxScribe from the command line: transcribe audio and video files with the
same local engine the app uses, so scripts and other programs can call it.
Nothing leaves the PC.

    venv\\Scripts\\python.exe cli.py meeting.mp3
    venv\\Scripts\\python.exe cli.py talk.mp4 --format srt --output captions
    venv\\Scripts\\python.exe cli.py interview.m4a --language auto --translate

Text goes to stdout unless --output names a folder; files are written next
to each other there and an existing file is never replaced ("name (2).srt").
Plain text and .srt are free, like in the app. .vtt and .md, and the three
most accurate models, need Pro, the same as in the app.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core import batch, captions, transcript_export
from core import license as voxscribe_license
from core import settings as voxscribe_settings
from core.cleanup import clean_transcript
from core.replacements import apply_replacements
from core.srt import format_srt

FREE_FORMATS = ("txt", "srt")
PRO_FORMATS = ("vtt", "md")
MODEL_CHOICES = [size for size, _ in voxscribe_settings.AVAILABLE_MODEL_SIZES]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voxscribe",
        description="Transcribe audio and video files on this PC with VoxScribe's engine.",
    )
    parser.add_argument("files", nargs="+", help="audio or video files, or folders of them")
    parser.add_argument(
        "-f",
        "--format",
        choices=FREE_FORMATS + PRO_FORMATS,
        default="txt",
        help="txt (default) or srt; vtt and md need Pro",
    )
    parser.add_argument(
        "-o", "--output", help="folder to save files in, instead of printing the text"
    )
    parser.add_argument(
        "-m",
        "--model",
        choices=MODEL_CHOICES,
        help="speech model (default: the one picked in VoxScribe's Settings)",
    )
    parser.add_argument(
        "-l",
        "--language",
        default="en",
        help='spoken language code such as en, de or ar, or "auto" to detect it',
    )
    parser.add_argument(
        "--translate", action="store_true", help="write English, whatever the spoken language"
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="plain text exactly as heard: no filler cleanup and no word replacements",
    )
    return parser


def check_allowed(fmt: str, model: str, translate: bool, is_pro: bool) -> str | None:
    """Why this run is not allowed, or None when it is."""
    if fmt in PRO_FORMATS and not is_pro:
        return f".{fmt} output needs VoxScribe Pro. Plain text and .srt are free."
    if model in voxscribe_settings.PRO_MODEL_SIZES and not is_pro:
        return f'The "{model}" model needs VoxScribe Pro. tiny, base and small are free.'
    if translate and model in voxscribe_settings.NO_TRANSLATE_MODEL_SIZES:
        return f'The "{model}" model cannot translate. Pick another model with --model.'
    return None


def render(fmt: str, detailed: list, title: str, *, raw: bool = False) -> str:
    """The output for one file from the engine's detailed segments."""
    segments = [(start, end, text) for start, end, text, _words in detailed]
    if fmt == "txt":
        text = " ".join(t.strip() for _s, _e, t in segments if t.strip())
        if not raw:
            text = apply_replacements(clean_transcript(text))
        return text + "\n" if text else ""
    if fmt == "md":
        return transcript_export.format_markdown(segments, title)
    cards = captions.split_segments_timed(detailed)
    return format_srt(cards) if fmt == "srt" else transcript_export.format_vtt(cards)


def output_path(folder: Path, source: str, fmt: str) -> Path:
    """Where to save `source`'s output in `folder` without replacing a file."""
    base = batch.unused_base(str(folder / Path(source).name), [f".{fmt}"])
    return base.with_name(base.name + f".{fmt}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # A Windows console defaults to a code page that cannot print every name.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    model = args.model or voxscribe_settings.get_model_size()
    problem = check_allowed(args.format, model, args.translate, voxscribe_license.is_pro())
    if problem:
        print(problem, file=sys.stderr)
        return 2

    files = batch.collect_media(args.files)
    if not files:
        print("No audio or video files found.", file=sys.stderr)
        return 2
    folder = Path(args.output) if args.output else None
    if folder:
        folder.mkdir(parents=True, exist_ok=True)

    # Imported here so --help and argument errors answer at once.
    from core.transcribe import load_transcriber

    print(f"Loading the {model} model...", file=sys.stderr)
    transcriber = load_transcriber(model)
    language = None if args.language.lower() == "auto" else args.language
    task = "translate" if args.translate else "transcribe"

    failed = 0
    for index, source in enumerate(files, 1):
        print(f"[{index}/{len(files)}] {source}", file=sys.stderr)
        try:
            detailed = transcriber.transcribe_file_detailed(
                source,
                language=language,
                task=task,
                word_timestamps=args.format in ("srt", "vtt"),
            )
        except Exception as exc:  # noqa: BLE001 -- report and go on with the rest
            print(f"  failed: {exc}", file=sys.stderr)
            failed += 1
            continue
        result = render(args.format, detailed, Path(source).stem, raw=args.raw)
        if folder:
            target = output_path(folder, source, args.format)
            target.write_text(result, encoding="utf-8")
            print(f"  saved {target}", file=sys.stderr)
        else:
            if len(files) > 1:
                sys.stdout.write(f"==> {source} <==\n")
            sys.stdout.write(result)
            sys.stdout.flush()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
