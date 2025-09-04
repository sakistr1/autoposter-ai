import random

def generate_mock_media_url(post_type: str) -> str:
    """
    Επιστρέφει ένα mock URL ανάλογα με τον τύπο του post (image, carousel, video).
    """
    if post_type == "image":
        return f"https://via.placeholder.com/600x600.png?text=Post+{random.randint(100,999)}"
    elif post_type == "carousel":
        return f"https://via.placeholder.com/600x400.png?text=Carousel+{random.randint(100,999)}"
    elif post_type == "video":
        return "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"
    else:
        raise ValueError("Μη υποστηριζόμενος τύπος post.")
