from pathlib import Path
from moviepy.editor import ColorClip
from music_bed import set_music_bed

out = Path("out_test_bed.mp4")
clip = ColorClip(size=(720, 1280), color=(20, 20, 20), duration=12)  # 12s κάθετο
final = set_music_bed(clip, bucket="ig_tiktok")  # άλλαξε bucket για FB/LinkedIn/ambient
final.write_videofile(str(out), fps=30, audio_codec="aac", audio_bitrate="192k")
