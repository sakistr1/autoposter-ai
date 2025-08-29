import uuid

def render_video_preview(template_id: int, payload: dict) -> dict:
    """
    Dummy renderer για βίντεο.
    Επιστρέφει ψεύτικο URL σε preview MP4.
    """
    preview_id = str(uuid.uuid4())
    return {
        "preview_id": preview_id,
        "urls": [f"/static/mock_previews/{preview_id}.mp4"]
    }
