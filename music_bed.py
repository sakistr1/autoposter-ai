# music_bed.py
import json, random
from pathlib import Path
from typing import Tuple
from moviepy.editor import AudioFileClip, CompositeAudioClip
from moviepy.audio.fx.all import audio_loop

def project_root() -> Path:
    here = Path(__file__).resolve().parent
    # Βρες τον φάκελο που έχει το "static/music/mixkit"
    for p in (here, *here.parents):
        if (p / "static" / "music" / "mixkit").exists():
            return p
    return here

BASE = project_root()
MUSIC_DIR = BASE / "static" / "music" / "mixkit"
CATALOG = MUSIC_DIR / "music_catalog.json"

def _load_catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))

def _pick_track(bucket: str) -> Path:
    data = _load_catalog()
    opts = [r for r in data if r["category"] == bucket]
    if not opts:
        opts = [r for r in data if r["category"] == "ambient"]
    if not opts:
        raise RuntimeError("No tracks found in catalog.")
    fn = random.choice(opts)["filename"]
    p = MUSIC_DIR / bucket / fn
    return p if p.exists() else (MUSIC_DIR / "ambient" / fn)

def make_bed(bucket: str, target_range: Tuple[int, int] = (15, 30), gain_db: float = -6.0):
    src = _pick_track(bucket)
    clip = AudioFileClip(str(src))
    dur = float(clip.duration or 0)
    length = max(min(target_range[1], int(dur) if dur > 0 else target_range[1]), target_range[0])
    start_max = max(0.0, dur - length)
    start = 0.0 if start_max <= 0 else random.uniform(0, start_max)
    bed = clip.subclip(start, start + length).audio_fadein(0.5).audio_fadeout(0.5)
    bed = bed.volumex(10 ** (gain_db / 20.0))  # -6 dB default
    return bed

def set_music_bed(video_clip, bucket: str):
    secs = int(min(30, max(10, video_clip.duration)))  # 10–30s
    bed = make_bed(bucket, target_range=(secs, secs))
    bed = audio_loop(bed, duration=video_clip.duration)
    return video_clip.set_audio(CompositeAudioClip([bed]))
