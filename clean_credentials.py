import sqlite3

# Ρύθμισε το path στη βάση σου
DATABASE_PATH = "database.db"  # ή το σωστό path της βάσης σου

# Email χρήστη που θέλεις να διορθώσεις τα credentials
USER_EMAIL = "demo3@test.com"

def clean_credentials(db_path, user_email):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Πάρε τα παλιά credentials
    cursor.execute("SELECT consumer_key, consumer_secret, woocommerce_url FROM users WHERE email=?", (user_email,))
    row = cursor.fetchone()
    if not row:
        print(f"User with email {user_email} not found.")
        return
    consumer_key, consumer_secret, woocommerce_url = row
    print("Before cleaning:")
    print("consumer_key:", consumer_key)
    print("consumer_secret:", consumer_secret)
    print("woocommerce_url:", woocommerce_url)

    # Καθάρισμα - strip και αφαίρεση ανεπιθύμητων strings (π.χ. "secret")
    if consumer_key:
        consumer_key = consumer_key.strip()
    if consumer_secret:
        consumer_secret = consumer_secret.strip()
        # Αν υπάρχει το string "secret" μέσα, το αφαιρούμε
        consumer_secret = consumer_secret.replace("secret", "").strip()
    if woocommerce_url:
        woocommerce_url = woocommerce_url.strip()

    # Ενημέρωση στη βάση
    cursor.execute("""
        UPDATE users
        SET consumer_key=?, consumer_secret=?, woocommerce_url=?
        WHERE email=?
    """, (consumer_key, consumer_secret, woocommerce_url, user_email))
    conn.commit()
    print("Credentials cleaned and updated.")

    # Έλεγχος μετά
    cursor.execute("SELECT consumer_key, consumer_secret, woocommerce_url FROM users WHERE email=?", (user_email,))
    row = cursor.fetchone()
    print("After cleaning:")
    print("consumer_key:", row[0])
    print("consumer_secret:", row[1])
    print("woocommerce_url:", row[2])

    conn.close()

if __name__ == "__main__":
    clean_credentials(DATABASE_PATH, USER_EMAIL)
