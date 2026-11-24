"""Validasi input. Setiap fungsi mengembalikan (data_bersih, pesan_error)."""

TEKS_PRODUK = ["merek", "model", "os", "warna"]
ANGKA_PRODUK = {          # nama field: nilai minimum
    "ram_gb": 1,
    "rom_gb": 1,
    "harga_idr": 1,
    "stok": 0,
    "garansi_bulan": 0,
}
STATUS_PESANAN = ["DIPROSES", "DIKIRIM", "SELESAI", "DIBATALKAN"]


def _bilangan_bulat(nilai):
    # bool adalah subclass int di Python, jadi True/False harus ditolak
    return isinstance(nilai, int) and not isinstance(nilai, bool)


def validasi_produk(data, lengkap=True):
    """lengkap=True untuk POST (semua field wajib), False untuk PUT (sebagian)."""
    if not isinstance(data, dict):
        return None, "Body harus berupa JSON object"

    boleh = set(TEKS_PRODUK) | set(ANGKA_PRODUK) | {"aktif"}
    if lengkap:
        boleh.add("sku")
    elif "sku" in data:
        return None, "SKU tidak dapat diubah"

    asing = set(data) - boleh
    if asing:
        return None, "Field tidak dikenal: " + ", ".join(sorted(asing))

    bersih = {}
    if lengkap:
        sku = data.get("sku")
        if not isinstance(sku, str) or not sku.strip():
            return None, "SKU wajib diisi"
        bersih["sku"] = sku.strip()

    for nama in TEKS_PRODUK:
        if nama in data:
            if not isinstance(data[nama], str) or not data[nama].strip():
                return None, f"{nama} harus berupa teks yang tidak kosong"
            bersih[nama] = data[nama].strip()
        elif lengkap:
            return None, f"{nama} wajib diisi"

    for nama, minimum in ANGKA_PRODUK.items():
        if nama in data:
            if not _bilangan_bulat(data[nama]) or data[nama] < minimum:
                return None, f"{nama} harus bilangan bulat >= {minimum}"
            bersih[nama] = data[nama]
        elif lengkap:
            return None, f"{nama} wajib diisi"

    if "aktif" in data:
        if not isinstance(data["aktif"], bool):
            return None, "aktif harus true atau false"
        bersih["aktif"] = data["aktif"]
    elif lengkap:
        bersih["aktif"] = True

    if not bersih:
        return None, "Tidak ada field yang diubah"
    return bersih, None


def validasi_registrasi(data):
    if not isinstance(data, dict):
        return None, "Body harus berupa JSON object"
    nama, email, password = data.get("nama"), data.get("email"), data.get("password")
    if not isinstance(nama, str) or not nama.strip():
        return None, "Nama wajib diisi"
    if not isinstance(email, str) or "@" not in email or "." not in email.split("@")[-1]:
        return None, "Email tidak valid"
    if not isinstance(password, str) or len(password) < 8:
        return None, "Password minimal 8 karakter"
    return {"nama": nama.strip(), "email": email.strip().lower(), "password": password}, None


def validasi_item_pesanan(data):
    """Mengembalikan dict {sku: jumlah}. SKU yang sama otomatis digabung."""
    if not isinstance(data, dict):
        return None, "Body harus berupa JSON object"
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return None, "items harus berupa daftar yang tidak kosong"
    if len(items) > 20:
        return None, "Maksimal 20 item per pesanan"

    gabungan = {}
    for item in items:
        if not isinstance(item, dict):
            return None, "Setiap item harus berupa object"
        sku, jumlah = item.get("sku"), item.get("jumlah")
        if not isinstance(sku, str) or not sku.strip():
            return None, "SKU wajib diisi"
        if not _bilangan_bulat(jumlah) or jumlah <= 0:
            return None, "Jumlah harus bilangan bulat positif"
        sku = sku.strip()
        gabungan[sku] = gabungan.get(sku, 0) + jumlah
    return gabungan, None