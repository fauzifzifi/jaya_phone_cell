from pymongo import MongoClient

from config import Config

client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[Config.DB_NAME]


def cek_koneksi():
    """Uji koneksi ke MongoDB dengan perintah ping."""
    try:
        client.admin.command("ping")
        print("Koneksi MongoDB berhasil!")
        return True
    except Exception as error:
        print("Koneksi MongoDB gagal:", error)
        return False


def siapkan_indeks():
    """Buat indeks yang dibutuhkan aplikasi. Aman dipanggil berulang kali."""
    db["produk_smartphone"].create_index("sku", unique=True)
    db["produk_smartphone"].create_index([("merek", 1), ("harga_idr", 1)])
    db["users"].create_index("email", unique=True)
    db["pesanan"].create_index("nomor_pesanan", unique=True)
    db["pesanan"].create_index([("user_id", 1), ("tanggal", -1)])