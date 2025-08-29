import uuid

def render_image_preview(template_id: int, payload: dict) -> dict:
    """
    Dummy renderer για εικόνες.
    Επιστρέφει ψεύτικο URL σε preview PNG.
    """
    preview_id = str(uuid.uuid4())
    return {
        "preview_id": preview_id,
        "urls": [f"/static/mock_previews/{preview_id}.png"]
    }
