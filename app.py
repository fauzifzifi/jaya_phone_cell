import logging
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from flask import Flask, g, jsonify, request
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash

from auth import buat_token, login_wajib, role_wajib
from config import Config
from database.connection import cek_koneksi, db, siapkan_indeks
from validators import (
    STATUS_PESANAN,
    validasi_item_pesanan,
    validasi_produk,
    validasi_registrasi,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("jaya_phone_cell")

app = Flask(__name__)

produk = db["produk_smartphone"]
users = db["users"]
pesanan = db["pesanan"]


# ---------------------------------------------------------------- bantuan
def serialisasi(data):
    """Ubah ObjectId dan datetime menjadi string agar bisa dikirim sebagai JSON."""
    if isinstance(data, list):
        return [serialisasi(item) for item in data]
    if isinstance(data, dict):
        return {kunci: serialisasi(nilai) for kunci, nilai in data.items()}
    if isinstance(data, ObjectId):
        return str(data)
    if isinstance(data, datetime):
        return data.isoformat()
    return data


def pesan(teks, kode, **tambahan):
    return jsonify({"pesan": teks, **tambahan}), kode


# ---------------------------------------------------------------- penanganan error
@app.errorhandler(404)
def tidak_ditemukan(_):
    return pesan("Endpoint tidak ditemukan", 404)


@app.errorhandler(405)
def metode_salah(_):
    return pesan("Metode HTTP tidak diizinkan untuk endpoint ini", 405)


@app.errorhandler(PyMongoError)
def kesalahan_database(error):
    log.error("Kesalahan database: %s", error)   # detail hanya di log server
    return pesan("Layanan database sedang bermasalah, coba lagi nanti", 503)


@app.errorhandler(Exception)
def kesalahan_tak_terduga(error):
    log.exception("Kesalahan tak terduga: %s", error)
    return pesan("Terjadi kesalahan pada server", 500)


# ---------------------------------------------------------------- umum
@app.route("/", methods=["GET"])
def home():
    return jsonify({"pesan": "API Jaya Phone Cell aktif", "status": "success"})


# ---------------------------------------------------------------- autentikasi
@app.route("/api/auth/register", methods=["POST"])
def registrasi():
    data, error = validasi_registrasi(request.get_json(silent=True))
    if error:
        return pesan(error, 400)
    try:
        hasil = users.insert_one({
            "nama": data["nama"],
            "email": data["email"],
            "password_hash": generate_password_hash(data["password"]),
            "role": "pelanggan",          # registrasi publik selalu pelanggan
            "dibuat": datetime.now(timezone.utc),
        })
    except DuplicateKeyError:
        return pesan("Email sudah terdaftar", 409)
    return pesan("Registrasi berhasil", 201, id=str(hasil.inserted_id))


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return pesan("Body harus berupa JSON object", 400)
    email, password = data.get("email"), data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return pesan("Email dan password wajib diisi", 400)

    user = users.find_one({"email": email.strip().lower()})
    # pesan sengaja sama agar penyerang tidak tahu email mana yang terdaftar
    if not user or not check_password_hash(user["password_hash"], password):
        return pesan("Email atau password salah", 401)
    return jsonify({"token": buat_token(user), "role": user["role"], "pesan": "Login berhasil"}), 200


# ---------------------------------------------------------------- produk
@app.route("/api/produk", methods=["GET"])
def tampil_produk():
    try:
        halaman = int(request.args.get("page", 1))
        batas = int(request.args.get("limit", 10))
        harga_min = request.args.get("harga_min")
        harga_maks = request.args.get("harga_maks")
        harga_min = int(harga_min) if harga_min is not None else None
        harga_maks = int(harga_maks) if harga_maks is not None else None
    except ValueError:
        return pesan("page, limit, harga_min, dan harga_maks harus berupa angka", 400)
    if halaman < 1 or not 1 <= batas <= 50:
        return pesan("page minimal 1 dan limit antara 1 sampai 50", 400)

    filter_ = {"aktif": True}
    if request.args.get("merek"):
        filter_["merek"] = request.args["merek"]
    if harga_min is not None or harga_maks is not None:
        filter_["harga_idr"] = {}
        if harga_min is not None:
            filter_["harga_idr"]["$gte"] = harga_min
        if harga_maks is not None:
            filter_["harga_idr"]["$lte"] = harga_maks

    total = produk.count_documents(filter_)
    data = list(produk.find(filter_).sort("_id", 1).skip((halaman - 1) * batas).limit(batas))
    return jsonify({"data": serialisasi(data), "halaman": halaman, "limit": batas, "total": total}), 200


@app.route("/api/produk/<id>", methods=["GET"])
def detail_produk(id):
    if not ObjectId.is_valid(id):
        return pesan("ID produk tidak valid", 400)
    data = produk.find_one({"_id": ObjectId(id), "aktif": True})
    if not data:
        return pesan("Produk tidak ditemukan", 404)
    return jsonify(serialisasi(data)), 200


@app.route("/api/produk", methods=["POST"])
@login_wajib
@role_wajib("admin")
def tambah_produk():
    data, error = validasi_produk(request.get_json(silent=True), lengkap=True)
    if error:
        return pesan(error, 400)
    try:
        hasil = produk.insert_one(data)
    except DuplicateKeyError:
        return pesan("SKU sudah terdaftar", 409)
    return pesan("Produk berhasil ditambahkan", 201, id=str(hasil.inserted_id))


@app.route("/api/produk/<id>", methods=["PUT"])
@login_wajib
@role_wajib("admin")
def ubah_produk(id):
    if not ObjectId.is_valid(id):
        return pesan("ID produk tidak valid", 400)
    data, error = validasi_produk(request.get_json(silent=True), lengkap=False)
    if error:
        return pesan(error, 400)
    hasil = produk.update_one({"_id": ObjectId(id)}, {"$set": data})
    if hasil.matched_count == 0:
        return pesan("Produk tidak ditemukan", 404)
    return pesan("Produk berhasil diperbarui", 200)


@app.route("/api/produk/<id>", methods=["DELETE"])
@login_wajib
@role_wajib("admin")
def hapus_produk(id):
    if not ObjectId.is_valid(id):
        return pesan("ID produk tidak valid", 400)
    hasil = produk.delete_one({"_id": ObjectId(id)})
    if hasil.deleted_count == 0:
        return pesan("Produk tidak ditemukan", 404)
    return pesan("Produk berhasil dihapus", 200)


# ---------------------------------------------------------------- pesanan
def kembalikan_stok(daftar):
    """daftar berisi pasangan (sku, jumlah) yang stoknya harus dikembalikan."""
    for sku, jumlah in daftar:
        produk.update_one({"sku": sku}, {"$inc": {"stok": jumlah}})


@app.route("/api/pesanan", methods=["POST"])
@login_wajib
@role_wajib("pelanggan")
def buat_pesanan():
    item_pesanan, error = validasi_item_pesanan(request.get_json(silent=True))
    if error:
        return pesan(error, 400)

    sudah_dikurangi = []   # (sku, jumlah) yang berhasil, untuk jaga-jaga dibatalkan
    rincian = []
    for sku, jumlah in item_pesanan.items():
        # Satu operasi atomik: cek stok, kurangi stok, dan ambil data produk
        # (nama + harga saat itu) untuk snapshot pesanan.
        sebelum = produk.find_one_and_update(
            {"sku": sku, "aktif": True, "stok": {"$gte": jumlah}},
            {"$inc": {"stok": -jumlah}},
            return_document=ReturnDocument.BEFORE,
        )
        if sebelum is None:
            kembalikan_stok(sudah_dikurangi)
            return pesan(f"Stok tidak mencukupi atau produk tidak ditemukan: {sku}", 409)
        sudah_dikurangi.append((sku, jumlah))
        rincian.append({
            "sku": sku,
            "nama_produk": f"{sebelum['merek']} {sebelum['model']}",
            "harga": sebelum["harga_idr"],
            "jumlah": jumlah,
            "subtotal": sebelum["harga_idr"] * jumlah,
        })

    sekarang = datetime.now(timezone.utc)
    dokumen = {
        "nomor_pesanan": f"ORD-{sekarang:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}",
        "user_id": g.user_id,
        "tanggal": sekarang,
        "items": rincian,
        "total_harga": sum(item["subtotal"] for item in rincian),
        "status": "DIPROSES",
    }
    try:
        hasil = pesanan.insert_one(dokumen)
    except PyMongoError:
        kembalikan_stok(sudah_dikurangi)   # pesanan gagal disimpan, stok dikembalikan
        raise
    return pesan("Pesanan berhasil dibuat", 201,
                 id=str(hasil.inserted_id),
                 nomor_pesanan=dokumen["nomor_pesanan"],
                 total_harga=dokumen["total_harga"])


@app.route("/api/pesanan", methods=["GET"])
@login_wajib
def daftar_pesanan():
    filter_ = {} if g.role == "admin" else {"user_id": g.user_id}
    data = list(pesanan.find(filter_).sort("tanggal", -1).limit(100))
    return jsonify(serialisasi(data)), 200


@app.route("/api/pesanan/<id>", methods=["GET"])
@login_wajib
def detail_pesanan(id):
    if not ObjectId.is_valid(id):
        return pesan("ID pesanan tidak valid", 400)
    data = pesanan.find_one({"_id": ObjectId(id)})
    if not data:
        return pesan("Pesanan tidak ditemukan", 404)
    if g.role != "admin" and data["user_id"] != g.user_id:
        return pesan("Anda tidak berhak melihat pesanan ini", 403)
    return jsonify(serialisasi(data)), 200


@app.route("/api/pesanan/<id>/status", methods=["PATCH"])
@login_wajib
@role_wajib("admin")
def ubah_status_pesanan(id):
    if not ObjectId.is_valid(id):
        return pesan("ID pesanan tidak valid", 400)
    data = request.get_json(silent=True)
    status_baru = data.get("status") if isinstance(data, dict) else None
    if status_baru not in STATUS_PESANAN:
        return pesan("status harus salah satu dari: " + ", ".join(STATUS_PESANAN), 400)

    # Hanya pesanan yang belum final (DIPROSES atau DIKIRIM) yang boleh diubah.
    # Syarat ini ada di filter, jadi pembatalan tidak mungkin mengembalikan stok dua kali.
    lama = pesanan.find_one_and_update(
        {"_id": ObjectId(id), "status": {"$in": ["DIPROSES", "DIKIRIM"]}},
        {"$set": {"status": status_baru}},
        return_document=ReturnDocument.BEFORE,
    )
    if lama is None:
        if pesanan.count_documents({"_id": ObjectId(id)}) == 0:
            return pesan("Pesanan tidak ditemukan", 404)
        return pesan("Status pesanan sudah final dan tidak dapat diubah", 409)

    if status_baru == "DIBATALKAN":
        kembalikan_stok([(item["sku"], item["jumlah"]) for item in lama["items"]])
    return pesan("Status pesanan diperbarui menjadi " + status_baru, 200)


# ---------------------------------------------------------------- jalankan
if __name__ == "__main__":
    if cek_koneksi():
        siapkan_indeks()
        app.run(debug=Config.DEBUG)