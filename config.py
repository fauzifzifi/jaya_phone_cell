import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    DB_NAME = os.getenv("DB_NAME", "db_jaya_phone_cell")
    SECRET_KEY = os.getenv("SECRET_KEY")
    TOKEN_JAM = int(os.getenv("TOKEN_JAM", "2"))
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"


if not Config.SECRET_KEY:
    raise RuntimeError("SECRET_KEY belum diisi di file .env")