"""Mengisi data awal: 8 produk (satu per merek), 1 admin, dan 1 pelanggan."""
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from database.connection import cek_koneksi, db, siapkan_indeks

PRODUK = [
    ("SAM-A55-128", "Samsung", "Galaxy A55 5G", "Android", 8, 128, "Awesome Navy", 5500000, 10),
    ("VIVO-Y100-256", "Vivo", "Y100", "Android", 8, 256, "Pacific Blue", 4499000, 8),
    ("OPPO-RENO11-256", "Oppo", "Reno11", "Android", 8, 256, "Wave Green", 6499000, 6),
    ("INF-NOTE40-256", "Infinix", "Note 40", "Android", 8, 256, "Titan Gold", 2899000, 15),
    ("RDM-NOTE13-128", "Redmi", "Note 13", "Android", 8, 128, "Midnight Black", 2999000, 20),
    ("RLM-12-256", "Realme", "12 Pro", "Android", 8, 256, "Submarine Blue", 5299000, 7),
    ("HUA-NOVA12-256", "Huawei", "Nova 12", "HarmonyOS", 8, 256, "Black", 5799000, 5),
    ("APL-IP15-128", "iPhone", "iPhone 15", "iOS", 6, 128, "Blue", 13999000, 3),
]

if not cek_koneksi():
    raise SystemExit("MongoDB belum berjalan. Jalankan MongoDB lalu ulangi.")

siapkan_indeks()

for sku, merek, model, os_, ram, rom, warna, harga, stok in PRODUK:
    db["produk_smartphone"].update_one(
        {"sku": sku},
        {"$setOnInsert": {
            "merek": merek, "model": model, "os": os_,
            "ram_gb": ram, "rom_gb": rom, "warna": warna,
            "harga_idr": harga, "stok": stok, "garansi_bulan": 12, "aktif": True,
        }},
        upsert=True,
    )

# Akun contoh untuk belajar. Jangan dipakai di lingkungan nyata.
AKUN = [
    ("Admin Jaya Phone", "admin@jayaphone.test", "Admin12345", "admin"),
    ("Pelanggan Contoh", "budi@jayaphone.test", "Budi12345", "pelanggan"),
]
for nama, email, password, role in AKUN:
    db["users"].update_one(
        {"email": email},
        {"$setOnInsert": {
            "nama": nama, "role": role,
            "password_hash": generate_password_hash(password),
            "dibuat": datetime.now(timezone.utc),
        }},
        upsert=True,
    )

print("Produk :", db["produk_smartphone"].count_documents({}))
print("Users  :", db["users"].count_documents({}))
print("Seed selesai.")