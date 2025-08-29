from database import engine
from models import user, product, post
from database import Base

Base.metadata.create_all(bind=engine)
print("✅ Database created")
