# backend/generator.py

def generate_post_mock(product, post_type):
    """
    Mock δημιουργία διαφημιστικού περιεχομένου.
    Επιστρέφει λίστα από media URLs ανάλογα με τον τύπο.
    """
    base_url = "https://via.placeholder.com/600x600?text=" + product.name.replace(" ", "+")
    
    if post_type == "image":
        return [base_url]
    elif post_type == "carousel":
        return [base_url + f"+{i}" for i in range(1, 4)]
    elif post_type == "video":
        return [base_url.replace("600x600", "1280x720") + "+Video"]
    else:
        return [base_url]
