import httpx
import asyncio

BASE = "http://localhost:8000"

user_data = {
    "email": "test@example.com",
    "password": "test123"
}

headers = {"Content-Type": "application/json"}

async def test_api():
    async with httpx.AsyncClient() as client:
        # REGISTER
        r = await client.post(f"{BASE}/auth/register", json=user_data)
        print("Register status:", r.status_code)
        print("Register raw response:", r.text)
        try:
            print("Register JSON:", r.json())
        except Exception as e:
            print("Register JSON decode error:", e)

        # LOGIN
        r = await client.post(f"{BASE}/auth/login", data=user_data)
        print("\nLogin status:", r.status_code)
        print("Login raw response:", r.text)
        try:
            token = r.json()["access_token"]
            print("Login JSON:", r.json())
        except Exception as e:
            print("Login JSON decode error:", e)
            return

        auth_headers = {**headers, "Authorization": f"Bearer {token}"}

        # CREATE PRODUCT
        product_data = {
            "title": "Test Product",
            "description": "Description of product",
            "price": 9.99,
            "image_url": "https://example.com/image.jpg"
        }

        r = await client.post(f"{BASE}/products", json=product_data, headers=auth_headers)
        print("\nCreate product status:", r.status_code)
        print("Create product raw response:", r.text)
        try:
            product = r.json()
            print("Create product JSON:", product)
        except Exception as e:
            print("Create product JSON decode error:", e)
            return

        # CREATE POST
        post_data = {
            "content": "This is a test post.",
            "product_id": product["id"]
        }

        r = await client.post(f"{BASE}/posts", json=post_data, headers=auth_headers)
        print("\nCreate post status:", r.status_code)
        print("Create post raw response:", r.text)
        try:
            print("Create post JSON:", r.json())
        except Exception as e:
            print("Create post JSON decode error:", e)

if __name__ == "__main__":
    asyncio.run(test_api())
