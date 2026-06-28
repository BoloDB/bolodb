from pymongo import MongoClient


def test_db():
    client = MongoClient("mongodb://localhost:27017")
    db = client["bolodb"]
    history = db["query_history"]
    docs = list(history.find())
    print("Docs:", docs)


if __name__ == "__main__":
    test_db()
