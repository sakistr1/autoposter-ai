import os
from pathlib import Path
from production_engine.utils.ffmpeg_helpers import poster_from_video, sprite_from_video

def test_single_frame_exports(tmp_path: Path):
    # Χρησιμοποιεί ένα μικρό demo mp4 που έχεις στο repo (ή φτιάξε ένα synthetic)
    sample = "static/demo/video_1s.mp4"
    if not Path(sample).exists():
        # φτιάξε 1s dummy βίντεο χωρίς ήχο
        out = tmp_path/"dummy.mp4"
        os.system(f'ffmpeg -f lavfi -i color=c=black:s=320x240:d=1 -r 25 -y "{out}" >/dev/null 2>&1')
        sample = str(out)

    poster = tmp_path/"poster.jpg"
    sheet  = tmp_path/"sheet.webp"

    poster_from_video(sample, poster)
    sprite_from_video(sample, sheet)

    assert poster.exists() and poster.stat().st_size > 0
    assert sheet.exists() and sheet.stat().st_size > 0
