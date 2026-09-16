"""Isi lark_directory dari ekspor Lark Base, lalu tandai users.lark_status.

Masukan: berkas teks 'nama|nomor' per baris (hasil pembacaan Lark Base).
Jalankan SETELAH scripts/2026-09-17_lark_directory.sql diterapkan.

Setelah script ini jalan, sistem bisa membedakan sendiri orang yang sudah punya
profil Lark dari yang belum — tanpa petugas perlu bertanya apa pun di kiosk.
"""
import os, sys, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from database import supabase
from core.normalize import to_e164, normalize_name

ap = argparse.ArgumentParser()
ap.add_argument("source", help="berkas 'nama|nomor' hasil ekspor Lark")
ap.add_argument("--apply", action="store_true", help="tulis ke database")
args = ap.parse_args()

entries, skipped = {}, []
for line in open(args.source, encoding="utf-8"):
    if not line.strip():
        continue
    name, _, phone = line.rstrip("\n").partition("|")
    e164 = to_e164(phone)
    if not e164:
        skipped.append(name.strip())
        continue
    # Baris duplikat di Lark menunjuk orang yang sama; simpan nama terpanjang
    # karena versi singkat biasanya hasil pengisian terburu-buru.
    prev = entries.get(e164)
    clean = normalize_name(name)
    if not prev or len(clean) > len(prev):
        entries[e164] = clean

rows = [{"phone_e164": k, "full_name": v} for k, v in entries.items()]
print(f"{len(rows)} nomor unik dari Lark | {len(skipped)} baris dilewati (nomor tak terbaca)")
for n in skipped:
    print(f"  dilewati: {n!r}")

users = supabase.table("users").select("id, full_name, phone_e164, lark_status") \
    .eq("is_deleted", False).execute().data
linked = [u for u in users if u.get("phone_e164") in entries]
pending = [u for u in users if u.get("phone_e164") not in entries]
print(f"\nportal: {len(linked)} sudah punya profil Lark | {len(pending)} belum")

if not args.apply:
    print("\n[simulasi] jalankan ulang dengan --apply untuk menulis.")
    sys.exit(0)

for i in range(0, len(rows), 200):
    supabase.table("lark_directory").upsert(rows[i:i + 200]).execute()
print(f"[selesai] lark_directory terisi {len(rows)} baris.")

for u in linked:
    if u.get("lark_status") != "linked":
        supabase.table("users").update({"lark_status": "linked"}).eq("id", u["id"]).execute()
for u in pending:
    if u.get("lark_status") != "pending":
        supabase.table("users").update({"lark_status": "pending"}).eq("id", u["id"]).execute()
print(f"[selesai] lark_status: {len(linked)} linked, {len(pending)} pending.")
