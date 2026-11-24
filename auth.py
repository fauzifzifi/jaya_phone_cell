from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import g, jsonify, request

from config import Config


def buat_token(user):
    payload = {
        "sub": str(user["_id"]),
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=Config.TOKEN_JAM),
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")


def login_wajib(fungsi):
    """Endpoint hanya bisa diakses jika header Authorization: Bearer <token> valid."""
    @wraps(fungsi)
    def pembungkus(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"pesan": "Token tidak ada, silakan login"}), 401
        try:
            payload = jwt.decode(header[7:], Config.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"pesan": "Token kedaluwarsa, silakan login lagi"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"pesan": "Token tidak valid"}), 401
        g.user_id = payload["sub"]
        g.role = payload["role"]
        return fungsi(*args, **kwargs)
    return pembungkus


def role_wajib(*role_diizinkan):
    """Dipakai di bawah @login_wajib. Menolak (403) role yang tidak diizinkan."""
    def dekorator(fungsi):
        @wraps(fungsi)
        def pembungkus(*args, **kwargs):
            if g.role not in role_diizinkan:
                return jsonify({"pesan": "Anda tidak berhak mengakses endpoint ini"}), 403
            return fungsi(*args, **kwargs)
        return pembungkus
    return dekorator