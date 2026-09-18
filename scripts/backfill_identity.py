"""Isi kolom phone_e164 / name_key / lark_status untuk baris yang sudah ada.

Jalankan SETELAH scripts/2026-09-17_add_identity_columns.sql diterapkan.
Aman diulang: hanya menulis baris yang nilainya berubah.
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from database import supabase
from core.normalize import normalize_name, name_key, to_e164

ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true", help="tulis ke database (tanpa ini hanya simulasi)")
args = ap.parse_args()

rows = supabase.table("users").select("id, full_name, phone_number, phone_e164, name_key").execute().data
changes, unreadable, collisions = [], [], {}

for r in rows:
    clean = normalize_name(r["full_name"])
    key = name_key(r["full_name"])
    e164 = to_e164(r.get("phone_number"))
    if not e164:
        unreadable.append((r["id"], r["full_name"], r.get("phone_number")))
    collisions.setdefault(key, []).append(r["full_name"])
    patch = {}
    if clean != r["full_name"]:
        patch["full_name"] = clean
    if r.get("name_key") != key:
        patch["name_key"] = key
    if (r.get("phone_e164") or "") != e164:
        patch["phone_e164"] = e164 or None
    if patch:
        changes.append((r["id"], patch))

dupes = {k: v for k, v in collisions.items() if len(v) > 1}
print(f"{len(rows)} baris | {len(changes)} perlu diperbarui | {len(unreadable)} nomor tak terbaca")
if unreadable:
    print("\nNomor tak terbaca (dibiarkan kosong, bukan ditebak):")
    for i, n, p in unreadable:
        print(f"  #{i} {n!r}: {p!r}")
if dupes:
    print("\nNama bentrok setelah normalisasi (perlu diputuskan manusia):")
    for k, v in dupes.items():
        print(f"  {k!r}: {v}")

if not args.apply:
    print("\n[simulasi] jalankan ulang dengan --apply untuk menulis.")
else:
    for uid, patch in changes:
        supabase.table("users").update(patch).eq("id", uid).execute()
    print(f"\n[selesai] {len(changes)} baris diperbarui.")
