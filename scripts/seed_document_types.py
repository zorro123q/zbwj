import os

from app import create_app
from app.seed import seed_document_types

if __name__ == "__main__":
    env = os.getenv("FLASK_ENV", "development")
    app = create_app(env)
    with app.app_context():
        seed_document_types()
        print("seed_document_types: done")
