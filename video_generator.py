# video_generator.py

from moviepy.editor import *
from gtts import gTTS
import requests
from BytesIO
import os

def generate_post_video(image_url, caption, output_path='static/post_video.mp4'):
    # Κατέβασε εικόνα
    response = requests.get(image_url)
    image = ImageClip(BytesIO(response.content)).set_duration(8).resize(height=720)

    # Δημιούργησε φωνή με gTTS
    tts = gTTS(caption, lang='el')
    os.makedirs("static", exist_ok=True)
    audio_path = "static/voice.mp3"
    tts.save(audio_path)
    audio = AudioFileClip(audio_path)

    # Δημιούργησε κείμενο (πάνω στην εικόνα)
    txt_clip = TextClip(caption, fontsize=32, color='white', bg_color='black', size=image.size, method='caption')
    txt_clip = txt_clip.set_duration(8).set_position(('center', 'bottom')).margin(bottom=20)

    # Συνδύασε
    final = CompositeVideoClip([image, txt_clip]).set_audio(audio)

    # Αποθήκευση βίντεο
    final.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')

    return output_path
