import pytest


def test_db():
    try:
        from pymongo import MongoClient
        from pymongo.errors import ServerSelectionTimeoutError
    except Exception:
        pytest.skip("pymongo is not available")

    client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=200)
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError:
        pytest.skip("MongoDB is not available")
    db = client["bolodb"]
    history = db["query_history"]
    docs = list(history.find())
    print("Docs:", docs)


if __name__ == "__main__":
    test_db()
