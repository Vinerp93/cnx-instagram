#!/usr/bin/env python3
"""Listen to the audio of a video/audio file: transcription + basic audio metrics.

Usage:
  python3 listen.py <file-or-folder> [...] [--model small] [--lang pt] [--out DIR]

For each input it prints a Markdown report (duration, loudness, silences,
timestamped transcript) and, with --out, writes <name>.transcricao.md and .srt.
Requires ffmpeg/ffprobe and `pip install faster-whisper`.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MEDIA = {".mp4", ".mov", ".m4a", ".mp3", ".wav", ".aac", ".ogg", ".webm", ".mkv"}


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def has_audio(path):
    r = run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
             "stream=codec_name", "-of", "csv=p=0", str(path)])
    return bool(r.stdout.strip())


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def loudness(path):
    """Integrated loudness (LUFS) and true peak via ffmpeg loudnorm."""
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
             "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        return None
    d = json.loads(m.group(0))
    return {"lufs": float(d["input_i"]), "true_peak": float(d["input_tp"])}


def silences(path, noise="-35dB", min_len=0.6):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
             "-af", f"silencedetect=noise={noise}:d={min_len}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(starts, ends + [None] * (len(starts) - len(ends))))


def ts(sec, srt=False):
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if srt:
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    return f"{int(m):02d}:{s:04.1f}"


def collect(inputs):
    files = []
    for p in map(Path, inputs):
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in MEDIA)
        elif p.exists():
            files.append(p)
        else:
            print(f"[aviso] não encontrado: {p}", file=sys.stderr)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--model", default="small", help="tiny|base|small|medium|large-v3")
    ap.add_argument("--lang", default="pt")
    ap.add_argument("--out", help="folder to write .transcricao.md and .srt")
    ap.add_argument("--no-transcript", action="store_true", help="metrics only")
    a = ap.parse_args()

    files = collect(a.inputs)
    if not files:
        sys.exit("Nenhum arquivo de mídia encontrado.")

    model = None
    if not a.no_transcript:
        from faster_whisper import WhisperModel
        model = WhisperModel(a.model, device="cpu", compute_type="int8")

    for f in files:
        label = f.parent.name if f.stem == "video" else f.stem
        lines = [f"## {label}", f"`{f}`", ""]
        if not has_audio(f):
            lines.append("**Sem trilha de áudio.**")
            print("\n".join(lines) + "\n")
            continue

        dur = duration(f)
        ld = loudness(f)
        sil = silences(f)
        lines.append(f"- Duração: {dur:.1f}s")
        if ld:
            note = "ok para Reels (~-14 LUFS)" if -16 <= ld["lufs"] <= -12 else (
                "baixo" if ld["lufs"] < -16 else "alto")
            peak = f"pico {ld['true_peak']:.1f} dBTP" + (" ⚠ risco de clipping (> -1 dBTP)" if ld["true_peak"] > -1 else "")
            lines.append(f"- Volume: {ld['lufs']:.1f} LUFS ({note}), {peak}")
        if sil:
            lines.append("- Silêncios (>0,6s): " + ", ".join(
                f"{ts(s)}–{ts(e) if e else 'fim'}" for s, e in sil))
        else:
            lines.append("- Silêncios (>0,6s): nenhum")
        silent = sum((e if e else dur) - st for st, e in sil)
        if dur and silent / dur > 0.5:
            lines.append(f"- ⚠ {silent / dur:.0%} do vídeo está em silêncio (o LUFS só mede o trecho com som)")

        segs = []
        if model:
            # Decode with ffmpeg to 16 kHz mono float32 (avoids PyAV version issues).
            import numpy as np
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-vn", "-ac", "1",
                                  "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
            audio = np.frombuffer(raw, dtype=np.float32)
            it, info = model.transcribe(audio, language=a.lang, vad_filter=True)
            segs = list(it)
            words = sum(len(s.text.split()) for s in segs)
            speech = sum(s.end - s.start for s in segs)
            lines.append(f"- Fala: {speech:.1f}s, {words} palavras"
                         + (f", {words / speech * 60:.0f} palavras/min" if speech else ""))
            lines += ["", "### Transcrição"]
            lines += [f"[{ts(s.start)}] {s.text.strip()}" for s in segs] or ["(nenhuma fala detectada)"]

        report = "\n".join(lines)
        print(report + "\n")

        if a.out:
            out = Path(a.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{label}.transcricao.md").write_text(report + "\n", encoding="utf-8")
            if segs:
                srt = "\n".join(f"{i}\n{ts(s.start, True)} --> {ts(s.end, True)}\n{s.text.strip()}\n"
                                for i, s in enumerate(segs, 1))
                (out / f"{label}.srt").write_text(srt, encoding="utf-8")


if __name__ == "__main__":
    main()
