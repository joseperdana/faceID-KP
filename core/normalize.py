"""Normalisasi identitas jemaat — satu-satunya tempat aturan format ditegakkan.

Dipakai di batas sistem (saat data masuk lewat registrasi) supaya format kanonik
dijamin mesin, bukan bergantung pada ketikan petugas counter. Portal dan Lark
Base hanya bisa ditautkan lewat nomor HP, jadi normalisasinya harus identik di
kedua arah — itu sebabnya fungsinya dikumpulkan di sini, bukan disebar di tiap
pemanggil.
"""
import re

# Nomor Indonesia: 9-13 digit setelah kode negara dibuang (08xx… / +628xx…).
# Rentang ini diambil dari data nyata: 250 baris portal ada di 11-13 digit
# termasuk nol depan, dan 308 baris Lark ada di 9-12 digit tanpa nol depan.
MIN_SUBSCRIBER_DIGITS = 9
MAX_SUBSCRIBER_DIGITS = 13


def normalize_name(full_name: str) -> str:
    """Rapikan nama untuk disimpan: spasi tunggal, tanpa spasi di ujung."""
    return re.sub(r"\s+", " ", (full_name or "")).strip()


def name_key(full_name: str) -> str:
    """Kunci pembanding nama untuk deteksi duplikat.

    Huruf kecil semua, tanda baca dibuang, spasi dirapatkan. Dipakai supaya
    "Yohanes  Perdana" dan "yohanes perdana" dikenali sebagai orang yang sama —
    pencocokan huruf-per-huruf sebelumnya bisa dilewati hanya dengan spasi ganda.
    """
    s = (full_name or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def subscriber_digits(phone: str) -> str:
    """Inti nomor tanpa kode negara maupun nol depan: '85747479647'.

    Inilah bentuk yang dipakai untuk mencocokkan portal dengan Lark, karena
    Lark pernah menyimpan kolom ini sebagai angka sehingga nol depannya hilang
    permanen. Sisa '.0' dari konversi tipe Number ke Text juga dibuang di sini.
    """
    raw = str(phone or "").strip()
    raw = re.sub(r"\.0+$", "", raw)          # sisa konversi Number -> Text di Lark
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    if digits.startswith("62") and len(digits) >= 12:
        digits = digits[2:]
    return digits.lstrip("0")


def to_e164(phone: str) -> str:
    """Bentuk kanonik untuk disimpan di portal: '+6285747479647'.

    Mengembalikan string kosong kalau nomornya tidak masuk akal — nomor tak
    terbaca lebih baik dibiarkan kosong daripada disimpan sebagai kunci gabung
    palsu yang nanti menautkan dua orang berbeda.
    """
    core = subscriber_digits(phone)
    if not (MIN_SUBSCRIBER_DIGITS <= len(core) <= MAX_SUBSCRIBER_DIGITS):
        return ""
    return f"+62{core}"


def is_plausible_phone(phone: str) -> bool:
    return bool(to_e164(phone))
