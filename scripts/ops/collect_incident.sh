#!/usr/bin/env bash
# Mengumpulkan semua jejak yang masih tersisa di VPS untuk satu jendela waktu
# insiden, lalu membungkusnya jadi satu tar.gz yang bisa dianalisis di laptop.
#
# Pemakaian (di VPS, sebagai root lewat sudo):
#
#   sudo bash collect_incident.sh --since "2026-09-19 16:00" --until "2026-09-19 19:00"
#
# Waktu SELALU dibaca sebagai WIB (Asia/Jakarta), apa pun zona waktu server.
# Alasannya: yang kita ingat dari acara adalah jam dinding di gereja, bukan UTC.
# Semua keluaran (journal, dmesg, tabel per menit) juga ditulis dalam WIB.
#
# Skrip ini HANYA MEMBACA. Tidak me-restart layanan, tidak mengubah konfigurasi,
# tidak menghapus log. Yang ia tulis hanya folder hasil di /tmp (atau --out-dir).
# Aman dijalankan kapan saja, termasuk saat ibadah sedang berlangsung — tapi
# `vmstat 1 5` membuatnya berjalan minimal 5 detik.
#
# Rahasia tidak pernah ikut: .env tidak dibaca, properti Environment= milik unit
# tidak diambil, dan semua keluaran disaring — nilai di belakang nama yang
# mengandung KEY/TOKEN/SECRET/PASSWORD/DSN, kredensial di URL, dan token Bearer
# diganti [REDACTED]. Walau begitu hasilnya tetap berisi IP klien dan user_id:
# perlakukan tarball-nya sebagai data pribadi, jangan diunggah ke tempat publik.
#
# Kenapa ada Python di dalamnya: parsing log nginx yang dirotasi dan di-gzip,
# konversi zona waktu, dan persentil jauh lebih aman ditulis di Python daripada
# di awk (Ubuntu memakai mawk, yang tidak punya fungsi waktu gawk). python3
# selalu ada di server ini karena aplikasinya sendiri Python.
#
# Catatan produksi (19 Sep 2026): server nyata TIDAK sama dengan
# scripts/deploy_vps.sh — layanannya satu proses uvicorn, bukan gunicorn dua
# worker, dan direktorinya bukan /var/www. Karena itu skrip ini tidak
# mengasumsikan keduanya: ExecStart dan WorkingDirectory dibaca dari systemd,
# dan pola log gunicorn maupun uvicorn sama-sama dicari.

set -euo pipefail

SINCE=""
UNTIL=""
UNIT="faceid"
OUT_BASE="/tmp"
NGINX_LOG_DIR="/var/log/nginx"
INPUT_TZ="Asia/Jakarta"

usage() {
  cat <<'EOF'
Pemakaian:
  sudo bash collect_incident.sh --since "YYYY-MM-DD HH:MM" [--until "YYYY-MM-DD HH:MM"]
                                [--unit faceid] [--out-dir /tmp] [--nginx-log-dir /var/log/nginx]

  --since / --until   Batas jendela dalam WIB. --until bawaannya "sekarang".
                      Beri bantalan: kalau insiden terasa 17:00-17:45,
                      ambil 16:00-19:00 supaya kondisi sebelum dan sesudahnya ikut.
  --unit              Nama unit systemd aplikasi (bawaan: faceid).
  --out-dir           Tempat folder hasil dan tar.gz (bawaan: /tmp).
  --nginx-log-dir     Folder log nginx (bawaan: /var/log/nginx).
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --since) SINCE="${2:-}"; shift 2 ;;
    --until) UNTIL="${2:-}"; shift 2 ;;
    --unit) UNIT="${2:-}"; shift 2 ;;
    --out-dir) OUT_BASE="${2:-}"; shift 2 ;;
    --nginx-log-dir) NGINX_LOG_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumen tidak dikenal: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$SINCE" ]; then
  echo "--since wajib diisi." >&2
  usage >&2
  exit 2
fi

if [ "$(id -u)" -ne 0 ]; then
  # Tanpa root, journal sistem, dmesg, dan log nginx sebagian tidak terbaca —
  # hasilnya akan diam-diam bolong dan menyesatkan analisis.
  echo "Jalankan dengan sudo: sudo bash $0 --since ... --until ..." >&2
  exit 1
fi

for bin in python3 journalctl systemctl date tar; do
  if ! command -v "$bin" > /dev/null 2>&1; then
    echo "Perintah '$bin' tidak ditemukan, tidak bisa lanjut." >&2
    exit 1
  fi
done

if ! SINCE_EPOCH="$(TZ="$INPUT_TZ" date -d "$SINCE" +%s 2>/dev/null)"; then
  echo "Format --since tidak dikenali: '$SINCE' (contoh: \"2026-09-19 16:00\")" >&2
  exit 2
fi
if [ -n "$UNTIL" ]; then
  if ! UNTIL_EPOCH="$(TZ="$INPUT_TZ" date -d "$UNTIL" +%s 2>/dev/null)"; then
    echo "Format --until tidak dikenali: '$UNTIL'" >&2
    exit 2
  fi
else
  UNTIL_EPOCH="$(date +%s)"
fi
if [ "$UNTIL_EPOCH" -le "$SINCE_EPOCH" ]; then
  echo "--until harus sesudah --since." >&2
  exit 2
fi

SINCE_WIB="$(TZ="$INPUT_TZ" date -d "@$SINCE_EPOCH" '+%Y-%m-%d %H:%M')"
UNTIL_WIB="$(TZ="$INPUT_TZ" date -d "@$UNTIL_EPOCH" '+%Y-%m-%d %H:%M')"
NAME="kp-incident-$(TZ="$INPUT_TZ" date -d "@$SINCE_EPOCH" +%Y%m%d-%H%M)-diambil-$(TZ="$INPUT_TZ" date +%Y%m%d-%H%M%S)"
OUT="$OUT_BASE/$NAME"

# Hasilnya berisi IP dan user_id: hanya root yang boleh membaca selama dikumpulkan.
umask 077
mkdir -p "$OUT"
TOOLS="$(mktemp -d)"
trap 'rm -rf "$TOOLS"' EXIT

echo "Mengumpulkan jejak $SINCE_WIB s/d $UNTIL_WIB WIB ke $OUT"

# ---------------------------------------------------------------------------
# Penyaring rahasia. Dipasang di SETIAP keluaran sebelum menyentuh disk, jadi
# tidak ada momen di mana rahasia sempat tertulis lalu dihapus belakangan.
# ---------------------------------------------------------------------------
cat > "$TOOLS/redact.py" <<'PY'
import re
import sys

PATTERNS = [
    # https://user:pass@host atau https://publickey@o123.ingest.sentry.io
    (re.compile(r'(https?://)[^/@\s"\'\\]+@'), r'\1[REDACTED]@'),
    (re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+'), r'\1[REDACTED]'),
    # NAMA_KEY=nilai, "api_key": "nilai", token\":\"nilai (JSON di dalam JSON)
    (re.compile(
        r'(?i)([A-Za-z0-9_.-]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|DSN)[A-Za-z0-9_.-]*'
        r'[\\"\']*\s*[:=]\s*[\\"\']*)[^\s"\'\\,;&}]+'),
     r'\1[REDACTED]'),
]

for raw in sys.stdin.buffer:
    line = raw.decode("utf-8", errors="replace")
    for pattern, repl in PATTERNS:
        line = pattern.sub(repl, line)
    sys.stdout.write(line)
PY

redact() { python3 "$TOOLS/redact.py"; }

# run NAMA_FILE perintah...  — tulis perintah + keluarannya, tidak pernah
# menghentikan skrip kalau perintahnya gagal (dmesg kosong, nginx tidak ada, dll.).
run() {
  local name="$1"
  shift
  {
    echo "\$ $*"
    "$@" 2>&1 || echo "[perintah selesai dengan kode $?]"
  } | redact > "$OUT/$name"
}

# Baris pertama keluaran sebuah perintah, tanpa memicu pipefail saat head
# menutup pipa lebih dulu (SIGPIPE ke journalctl).
first_line() {
  { "$@" 2>/dev/null || true; } | head -n 1 || true
}

JSINCE="@$SINCE_EPOCH"
JUNTIL="@$UNTIL_EPOCH"

# --- 1. Identitas server dan layanan ----------------------------------------
{
  echo "Jendela (WIB)      : $SINCE_WIB s/d $UNTIL_WIB"
  echo "Jendela (epoch)    : $SINCE_EPOCH s/d $UNTIL_EPOCH"
  echo "Diambil (WIB)      : $(TZ="$INPUT_TZ" date '+%Y-%m-%d %H:%M:%S')"
  echo "Diambil (UTC)      : $(date -u '+%Y-%m-%d %H:%M:%S')"
  echo "Host               : $(hostname)"
  echo "Zona waktu server  : $(timedatectl show -p Timezone --value 2>/dev/null || date +%Z)"
  echo "Kernel             : $(uname -r)"
  echo "Boot terakhir      : $(uptime -s 2>/dev/null || echo '?')"
  echo "Unit               : $UNIT"
} | redact > "$OUT/00_info.txt"

run 01_boots.txt journalctl --list-boots --no-pager

# Hanya properti yang aman. SENGAJA tidak memakai `systemctl show` tanpa -p atau
# `systemctl cat`: keduanya ikut menampilkan Environment= yang bisa berisi rahasia.
run 02_service_props.txt systemctl show "$UNIT" --no-pager \
  -p Id,LoadState,ActiveState,SubState,Result,NRestarts,ActiveEnterTimestamp,ExecMainStartTimestamp,ExecMainPID,MemoryCurrent,MemoryPeak,MemoryMax,Restart,RestartUSec,WorkingDirectory,User,FragmentPath,DropInPaths
run 02_service_props_unix.txt systemctl show "$UNIT" --no-pager --timestamp=unix \
  -p NRestarts,ActiveEnterTimestamp,ExecMainStartTimestamp
# ExecStart menunjukkan server aplikasinya (uvicorn atau gunicorn, berapa worker).
run 02_service_execstart.txt systemctl show "$UNIT" --no-pager -p ExecStart

# --- 2. Retensi: apakah jendela ini masih tersimpan? --------------------------
{
  echo "\$ journalctl --disk-usage"
  journalctl --disk-usage 2>&1 || true
  echo
  if [ -d /var/log/journal ]; then
    echo "Journal persisten: YA (/var/log/journal ada — selamat dari reboot)"
  else
    echo "Journal persisten: TIDAK (/var/log/journal tidak ada — journal hilang setiap reboot)"
  fi
  echo
  echo "Entri journal tertua (semua unit):"
  first_line journalctl -q --no-pager -o short-iso
  echo
  echo "Entri journal tertua untuk unit $UNIT:"
  first_line env TZ="$INPUT_TZ" journalctl -q --no-pager -o short-iso -u "$UNIT"
  echo
  echo "\$ systemd-analyze cat-config systemd/journald.conf (baris aktif saja)"
  systemd-analyze cat-config systemd/journald.conf 2>/dev/null | grep -Ev '^\s*(#|$)' || true
  echo
  echo "\$ ls -la --time-style=full-iso $NGINX_LOG_DIR"
  ls -la --time-style=full-iso "$NGINX_LOG_DIR" 2>&1 || true
  echo
  echo "\$ cat /etc/logrotate.d/nginx"
  cat /etc/logrotate.d/nginx 2>&1 || true
} | redact > "$OUT/03_retention.txt"

# Epoch entri tertua, untuk dibandingkan dengan --since di ringkasan.
first_line journalctl -q --no-pager -o short-unix | awk '{print int($1)}' > "$OUT/03_journal_oldest_epoch.txt" || true
first_line journalctl -q --no-pager -o short-unix -u "$UNIT" | awk '{print int($1)}' > "$OUT/03_unit_oldest_epoch.txt" || true

# --- 3. Journal aplikasi di jendela -----------------------------------------
# `-u` ikut menyertakan pesan systemd tentang unit ini (Started/Stopped/
# Main process exited), jadi siklus hidup layanan ada di file yang sama.
TZ="$INPUT_TZ" journalctl -u "$UNIT" --since "$JSINCE" --until "$JUNTIL" \
  --no-pager -o short-iso-precise 2>&1 | redact > "$OUT/10_journal_${UNIT}.txt" || true
TZ="$INPUT_TZ" journalctl -u "$UNIT" --since "$JSINCE" --until "$JUNTIL" \
  --no-pager -o json 2>&1 | redact > "$OUT/10_journal_${UNIT}.json" || true

# Server aplikasi: pola gunicorn DAN uvicorn, karena produksi tidak selalu
# sama dengan skrip deploy di repo.
grep -iE 'worker timeout|booting worker|was sent (sigkill|sigterm|code)|perhaps out of memory|worker exiting|handling signal|shutting down|starting gunicorn|started server process|finished server process|waiting for application|application startup|uvicorn running|error while|child process' \
  "$OUT/10_journal_${UNIT}.txt" > "$OUT/11_server_process_lines.txt" || true
grep -E 'systemd\[1\]' "$OUT/10_journal_${UNIT}.txt" > "$OUT/12_service_lifecycle.txt" || true
# Kegagalan koneksi ke hulu (Supabase lewat httpx/HTTP2) — bahan H5.
grep -E 'RemoteProtocolError|ConnectionTerminated|ReadTimeout|WriteTimeout|ConnectTimeout|PoolTimeout|ConnectError|Exception in ASGI application|Traceback|MemoryError' \
  "$OUT/10_journal_${UNIT}.txt" > "$OUT/13_upstream_errors.txt" || true

# --- 4. Kernel: OOM killer ---------------------------------------------------
# SENGAJA _TRANSPORT=kernel, bukan `journalctl -k`: -k diam-diam membatasi ke
# boot saat ini, padahal server bisa saja sudah reboot sejak insiden.
TZ="$INPUT_TZ" journalctl _TRANSPORT=kernel --since "$JSINCE" --until "$JUNTIL" \
  --no-pager -o short-iso-precise 2>&1 | redact > "$OUT/20_kernel_window.txt" || true
grep -iE 'out of memory|oom-kill|oom_reaper|killed process|invoked oom-killer' \
  "$OUT/20_kernel_window.txt" > "$OUT/21_kernel_oom_window.txt" || true
# dmesg hanya berisi boot saat ini, tapi berguna kalau journal tidak persisten.
{ TZ="$INPUT_TZ" dmesg -T 2>&1 || true; } \
  | grep -iE 'out of memory|oom-kill|oom_reaper|killed process|invoked oom-killer' \
  | redact > "$OUT/22_dmesg_oom_boot_ini.txt" || true

# --- 5. Kondisi host SAAT INI (bukan saat insiden) ---------------------------
run 30_free.txt free -m
run 31_swapon.txt swapon --show
run 32_vmstat.txt vmstat 1 5
run 33_df.txt df -h
run 34_uptime.txt uptime
run 35_nproc.txt nproc
run 36_top_rss.txt ps -eo pid,user,rss,vsz,etime,comm --sort=-rss
{
  for f in memory cpu io; do
    echo "== /proc/pressure/$f"
    cat "/proc/pressure/$f" 2>&1 || true
  done
} > "$OUT/37_pressure.txt"

# --- 6. Nginx -----------------------------------------------------------------
if command -v nginx > /dev/null 2>&1; then
  run 40_nginx_t.txt nginx -t
  # Hanya direktif yang relevan dengan timeout dan format log, bukan seluruh
  # `nginx -T` (yang bisa memuat header Authorization atau path berkas rahasia).
  { nginx -T 2>/dev/null || true; } \
    | grep -nE '^# configuration file|proxy_(read|connect|send)_timeout|keepalive_timeout|client_max_body_size|limit_req|access_log|error_log|log_format|listen|server_name|proxy_pass' \
    | redact > "$OUT/41_nginx_directives.txt" || true
else
  echo "nginx tidak ditemukan" > "$OUT/40_nginx_t.txt"
fi

# --- 7. Analisis & ringkasan -------------------------------------------------
cat > "$TOOLS/analyze.py" <<'PY'
"""Parse log nginx (termasuk yang dirotasi/gzip) + hasil journal, tulis tabel
per menit dan SUMMARY.txt yang menjawab H1-H5."""
import glob
import gzip
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7))  # Indonesia tidak memakai DST
since, until = int(sys.argv[1]), int(sys.argv[2])
out, nginx_dir, unit = sys.argv[3], sys.argv[4], sys.argv[5]


def wib(ts):
    return datetime.fromtimestamp(ts, WIB).strftime("%Y-%m-%d %H:%M:%S")


def minute(ts):
    return datetime.fromtimestamp(ts, WIB).strftime("%Y-%m-%d %H:%M")


def read(name):
    try:
        with open(os.path.join(out, name), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def write(name, text):
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        f.write(text)


def open_any(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, encoding="utf-8", errors="replace")


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, math.ceil(q / 100.0 * len(s)) - 1))
    return s[k]


def int_or_none(text):
    text = text.strip().splitlines()[0] if text.strip() else ""
    try:
        return int(text)
    except ValueError:
        return None


MINUTES = []
m = since - since % 60
while m < until:
    MINUTES.append(minute(m))
    m += 60

# ---------------- nginx access -------------------------------------------
ACCESS_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<req>[^"]*)" (?P<status>\d{3}) \S+(?P<rest>.*)$')
RT_RE = re.compile(r'\brt=(?P<v>[\d.]+)')
URT_RE = re.compile(r'\burt="(?P<v>[^"]*)"')
UST_RE = re.compile(r'\bust="(?P<v>[^"]*)"')
DEV_RE = re.compile(r'\bdev="(?P<v>[^"]*)"')


def access_ts(s):
    return datetime.strptime(s, "%d/%b/%Y:%H:%M:%S %z").timestamp()


records = []
coverage_start = None
access_files = sorted(set(glob.glob(os.path.join(nginx_dir, "*access*.log*"))))
unparsed = 0
for path in access_files:
    try:
        mtime = os.path.getmtime(path)
        with open_any(path) as f:
            first = None
            for i, line in enumerate(f):
                mm = ACCESS_RE.match(line)
                if not mm:
                    if i > 50 and first is None:
                        break
                    continue
                try:
                    ts = access_ts(mm.group("time"))
                except ValueError:
                    continue
                if first is None:
                    first = ts
                    coverage_start = ts if coverage_start is None else min(coverage_start, ts)
                    # Berkas yang terakhir ditulis sebelum jendela tidak mungkin
                    # berisi baris di dalam jendela — cukup baris pertamanya.
                    if mtime < since:
                        break
                if since <= ts < until:
                    req = mm.group("req").split(" ")
                    rest = mm.group("rest")
                    rt = RT_RE.search(rest)
                    urt = URT_RE.search(rest)
                    ust = UST_RE.search(rest)
                    dev = DEV_RE.search(rest)
                    records.append({
                        "ts": ts,
                        "ip": mm.group("ip"),
                        "method": req[0] if req else "",
                        "path": (req[1] if len(req) > 1 else "").split("?")[0],
                        "status": mm.group("status"),
                        "rt": float(rt.group("v")) if rt else None,
                        "urt": urt.group("v") if urt else None,
                        "ust": ust.group("v") if ust else None,
                        "dev": dev.group("v") if dev else None,
                        "raw": line.rstrip("\n"),
                    })
    except (OSError, EOFError) as e:
        unparsed += 1
        sys.stderr.write("gagal membaca %s: %s\n" % (path, e))

records.sort(key=lambda r: r["ts"])
write("50_nginx_access_window.log", "".join(r["raw"] + "\n" for r in records))

WATCH = ["429", "499", "500", "502", "503", "504"]
per_min = defaultdict(Counter)
for r in records:
    c = per_min[minute(r["ts"])]
    c["total"] += 1
    c[r["status"][0] + "xx"] += 1
    if r["status"] in WATCH:
        c[r["status"]] += 1
cols = ["total", "2xx", "3xx", "4xx", "5xx"] + WATCH
lines = ["menit_wib\t" + "\t".join(cols)]
for mk in MINUTES:
    lines.append(mk + "\t" + "\t".join(str(per_min[mk][c]) for c in cols))
write("51_nginx_status_per_minute.tsv", "\n".join(lines) + "\n")

# Per menit untuk 504/499/500, lengkap dengan path yang paling sering kena.
bad = defaultdict(lambda: defaultdict(Counter))
for r in records:
    if r["status"] in ("504", "499", "500", "502", "503"):
        bad[r["status"]][minute(r["ts"])][r["method"] + " " + r["path"]] += 1
lines = []
for st in ("504", "499", "500", "502", "503"):
    if not bad[st]:
        continue
    lines.append("== %s per menit (WIB) — 3 path teratas" % st)
    for mk in sorted(bad[st]):
        top = ", ".join("%s x%d" % (p, n) for p, n in bad[st][mk].most_common(3))
        lines.append("%s  %4d  %s" % (mk, sum(bad[st][mk].values()), top))
    lines.append("")
write("52_nginx_errors_per_minute_paths.txt", "\n".join(lines) + "\n")

status_total = Counter(r["status"] for r in records)
api = [r for r in records if r["path"].startswith("/api/")]
ip_all = Counter(r["ip"] for r in records)
ip_api = Counter(r["ip"] for r in api)
ip_429 = Counter(r["ip"] for r in records if r["status"] == "429")
path_by_status = defaultdict(Counter)
for r in records:
    path_by_status[r["status"]][r["method"] + " " + r["path"]] += 1


def top_block(title, counter, n=15):
    rows = ["== " + title]
    total = sum(counter.values())
    for k, v in counter.most_common(n):
        rows.append("%6d  %5.1f%%  %s" % (v, 100.0 * v / total if total else 0, k))
    if not counter:
        rows.append("(kosong)")
    return "\n".join(rows) + "\n"


write("53_nginx_top.txt",
      top_block("Status (semua request)", status_total, 30) + "\n"
      + top_block("IP klien — semua request", ip_all) + "\n"
      + top_block("IP klien — request /api/", ip_api) + "\n"
      + top_block("IP klien — 429", ip_429) + "\n"
      + "".join(top_block("Path untuk status " + s, path_by_status[s], 10) + "\n"
                for s in sorted(path_by_status) if s[0] in "45")
      # Hanya terisi setelah format kp_timed terpasang (header X-KP-Device).
      + top_block("Perangkat (X-KP-Device) — request /api/ berstatus 4xx/5xx",
                  Counter(r["dev"] or "-" for r in api
                          if r["dev"] is not None and r["status"][0] in "45")))

timed = [r for r in records if r["rt"] is not None]
rt_lines = []
if timed:
    rt_lines.append("menit_wib\tn_recognize\tp50_s\tp95_s\tmax_s\tn_semua_api\tp95_semua_api_s")
    by_min_rec = defaultdict(list)
    by_min_api = defaultdict(list)
    for r in timed:
        if r["path"] == "/api/recognize":
            by_min_rec[minute(r["ts"])].append(r["rt"])
        if r["path"].startswith("/api/"):
            by_min_api[minute(r["ts"])].append(r["rt"])
    for mk in MINUTES:
        v, a = by_min_rec.get(mk, []), by_min_api.get(mk, [])
        fmt = lambda x: "-" if x is None else "%.3f" % x
        rt_lines.append("%s\t%d\t%s\t%s\t%s\t%d\t%s" % (
            mk, len(v), fmt(pct(v, 50)), fmt(pct(v, 95)), fmt(max(v) if v else None),
            len(a), fmt(pct(a, 95))))
    write("54_nginx_request_time_per_minute.tsv", "\n".join(rt_lines) + "\n")

# ---------------- nginx error log ----------------------------------------
ERR_RE = re.compile(r'^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\]')
err_lines = []
err_kinds = Counter()
KINDS = [
    ("upstream timed out", "upstream timed out"),
    ("connect() failed", "connect() failed (aplikasi tidak menerima koneksi)"),
    ("no live upstreams", "no live upstreams"),
    ("upstream prematurely closed", "upstream prematurely closed"),
    ("limiting requests", "limit_req nginx"),
    ("client intended to send too large body", "body terlalu besar"),
]
for path in sorted(glob.glob(os.path.join(nginx_dir, "*error*.log*"))):
    try:
        if os.path.getmtime(path) < since:
            continue
        with open_any(path) as f:
            for line in f:
                mm = ERR_RE.match(line)
                if not mm:
                    continue
                # Log error nginx memakai jam lokal server tanpa offset.
                ts = datetime.strptime(mm.group(1), "%Y/%m/%d %H:%M:%S").timestamp()
                if since <= ts < until:
                    err_lines.append((ts, line.rstrip("\n")))
                    for needle, label in KINDS:
                        if needle in line:
                            err_kinds[label] += 1
    except (OSError, EOFError) as e:
        sys.stderr.write("gagal membaca %s: %s\n" % (path, e))
err_lines.sort()
write("55_nginx_error_window.log", "".join(l + "\n" for _, l in err_lines))

# ---------------- journal aplikasi ---------------------------------------
jtext = read("10_journal_%s.txt" % unit)
jlines = [l for l in jtext.splitlines() if l and not l.startswith("-- ")]
JTS_RE = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})')
UVI_ACCESS_RE = re.compile(r'"(?P<method>[A-Z]+) (?P<path>\S+) HTTP/[\d.]+" (?P<status>\d{3})')
PATTERNS = [
    ("RemoteProtocolError", re.compile(r'RemoteProtocolError')),
    ("ConnectionTerminated", re.compile(r'ConnectionTerminated')),
    ("ReadTimeout", re.compile(r'ReadTimeout')),
    ("ConnectTimeout/ConnectError", re.compile(r'Connect(Timeout|Error)')),
    ("PoolTimeout", re.compile(r'PoolTimeout')),
    ("Exception in ASGI application", re.compile(r'Exception in ASGI application')),
    ("MemoryError", re.compile(r'MemoryError')),
    ("Worker timeout (gunicorn)", re.compile(r'(?i)worker timeout')),
    ("Booting worker (gunicorn)", re.compile(r'(?i)booting worker')),
    ("Started server process (uvicorn)", re.compile(r'Started server process')),
]
pat_per_min = defaultdict(Counter)
pat_total = Counter()
uvi_status = Counter()
uvi_per_min = defaultdict(Counter)
app_json = Counter()
rl_ip = Counter()
checkin_outcome = Counter()
recog_ms = []
app_errors = 0
for line in jlines:
    mt = JTS_RE.match(line)
    mk = mt.group(1).replace("T", " ")[:16] if mt else "?"
    for label, rx in PATTERNS:
        if rx.search(line):
            pat_total[label] += 1
            pat_per_min[mk][label] += 1
    ua = UVI_ACCESS_RE.search(line)
    if ua:
        uvi_status[ua.group("status")] += 1
        uvi_per_min[mk][ua.group("status")] += 1
    brace = line.find("{")
    if brace != -1:
        try:
            obj = json.loads(line[brace:])
        except ValueError:
            obj = None
        if isinstance(obj, dict) and "logger" in obj:
            app_json[obj.get("logger")] += 1
            if str(obj.get("level", "")).lower() in ("error", "critical"):
                app_errors += 1
            if obj.get("logger") == "kp.ratelimit":
                rl_ip[str(obj.get("client_ip"))] += 1
            if obj.get("logger") == "kp.checkin":
                checkin_outcome["%s/%s" % (obj.get("method"), obj.get("outcome"))] += 1
            if obj.get("logger") == "kp.request" and obj.get("route") == "/api/recognize":
                try:
                    recog_ms.append(float(obj.get("duration_ms")))
                except (TypeError, ValueError):
                    pass

lines = ["menit_wib\t" + "\t".join(l for l, _ in PATTERNS)]
for mk in sorted(pat_per_min):
    lines.append(mk + "\t" + "\t".join(str(pat_per_min[mk][l]) for l, _ in PATTERNS))
write("14_upstream_errors_per_minute.tsv", "\n".join(lines) + "\n")

if uvi_status:
    sts = sorted(uvi_status)
    lines = ["menit_wib\t" + "\t".join(sts)]
    for mk in MINUTES:
        lines.append(mk + "\t" + "\t".join(str(uvi_per_min[mk][s]) for s in sts))
    write("15_app_access_status_per_minute.tsv", "\n".join(lines) + "\n")

lifecycle = [l for l in read("12_service_lifecycle.txt").splitlines() if l.strip()]
kernel_oom = [l for l in read("21_kernel_oom_window.txt").splitlines() if l.strip()]
dmesg_oom = [l for l in read("22_dmesg_oom_boot_ini.txt").splitlines() if l.strip()]
execstart = read("02_service_execstart.txt")
props_unix = read("02_service_props_unix.txt")
journal_oldest = int_or_none(read("03_journal_oldest_epoch.txt"))
unit_oldest = int_or_none(read("03_unit_oldest_epoch.txt"))
retention_txt = read("03_retention.txt")


def prop(name):
    mm = re.search(r'^%s=(.*)$' % name, props_unix, re.M)
    return mm.group(1).strip() if mm else ""


active_enter = prop("ActiveEnterTimestamp")
active_enter_epoch = int(active_enter[1:]) if active_enter.startswith("@") and active_enter[1:].isdigit() else None

# ---------------- SUMMARY ------------------------------------------------
S = []
add = S.append
add("RINGKASAN INSIDEN")
add("=================")
add("Jendela : %s s/d %s WIB" % (wib(since), wib(until)))
add("Unit    : %s" % unit)
server = "tidak diketahui"
low = execstart.lower()
if "gunicorn" in low:
    wm = re.search(r'(?:-w|--workers)[ =](\d+)', execstart)
    server = "gunicorn, %s worker" % (wm.group(1) if wm else "?")
elif "uvicorn" in low:
    wm = re.search(r'--workers[ =](\d+)', execstart)
    server = "uvicorn, %s proses" % (wm.group(1) if wm else "1")
add("Server  : %s (dari ExecStart; lihat 02_service_execstart.txt)" % server)
add("")

add("RETENSI — apakah datanya masih ada?")
add("-----------------------------------")
warn = False
if "Journal persisten: TIDAK" in retention_txt:
    add("!!! PERINGATAN: journal TIDAK persisten. Semua log sebelum boot terakhir sudah hilang.")
    warn = True
if journal_oldest is None:
    add("!!! Entri journal tertua tidak terbaca.")
elif journal_oldest > since:
    add("!!! PERINGATAN KERAS: entri journal tertua %s WIB LEBIH BARU dari awal jendela." % wib(journal_oldest))
    add("!!! Sebagian atau seluruh log aplikasi untuk jendela ini SUDAH TERHAPUS.")
    warn = True
else:
    add("Journal tertua %s WIB — jendela masih tercakup." % wib(journal_oldest))
if unit_oldest is not None and unit_oldest > since:
    add("!!! Log unit %s baru mulai %s WIB — sebelum itu tidak ada." % (unit, wib(unit_oldest)))
    warn = True
if not jlines:
    add("!!! Tidak ada satu pun baris journal %s di jendela ini." % unit)
    warn = True
if coverage_start is None:
    add("!!! Tidak ada log akses nginx yang terbaca di %s." % nginx_dir)
    warn = True
elif coverage_start > since:
    add("!!! PERINGATAN KERAS: log akses nginx tertua %s WIB, sesudah awal jendela — sudah dirotasi habis." % wib(coverage_start))
    warn = True
else:
    add("Log akses nginx tertua %s WIB — jendela tercakup (%d baris di jendela)." % (wib(coverage_start), len(records)))
if not warn:
    add("Tidak ada tanda data hilang.")
add("")

add("H1 — Kehabisan memori (OOM / swap)")
add("----------------------------------")
add("OOM di kernel log dalam jendela : %d baris (21_kernel_oom_window.txt)" % len(kernel_oom))
add("OOM di dmesg boot ini (semua waktu): %d baris (22_dmesg_oom_boot_ini.txt)" % len(dmesg_oom))
for label in ("MemoryError", "Worker timeout (gunicorn)", "Booting worker (gunicorn)", "Started server process (uvicorn)"):
    add("%-33s: %d" % (label, pat_total[label]))
add("Siklus hidup layanan di jendela   : %d baris systemd (12_service_lifecycle.txt)" % len(lifecycle))
for l in lifecycle[:10]:
    add("    " + l)
if active_enter_epoch and active_enter_epoch > until:
    add("Catatan: layanan terakhir diaktifkan %s WIB, SESUDAH jendela (mis. karena deploy)." % wib(active_enter_epoch))
    add("         NRestarts=%s saat ini tidak menggambarkan kejadian di jendela." % (prop("NRestarts") or "?"))
if kernel_oom:
    add("=> Ada bukti OOM killer di jendela. H1 DIDUKUNG — cek proses apa yang dibunuh.")
elif journal_oldest is not None and journal_oldest <= since:
    add("=> Tidak ada jejak OOM killer di jendela. OOM keras kemungkinan TIDAK terjadi.")
    add("   Swap yang lambat (tanpa OOM) tidak meninggalkan jejak di log: itu yang dijawab")
    add("   metrik host (Alloy) di insiden berikutnya. Kondisi RAM/swap SAAT INI ada di 30_free.txt.")
else:
    add("=> Tidak bisa disimpulkan: journal kernel untuk jendela ini tidak tersimpan.")
add("")

add("H2 — Rate limit per IP (429)")
add("----------------------------")
n429 = status_total.get("429", 0)
add("429 di nginx: %d   |   baris kp.ratelimit di aplikasi: %d" % (n429, sum(rl_ip.values())))
if n429:
    ip, n = ip_429.most_common(1)[0]
    share = 100.0 * n / n429
    add("IP teratas untuk 429: %s (%d, %.0f%%) — daftar lengkap di 53_nginx_top.txt" % (ip, n, share))
    if share >= 60:
        add("=> 429 terkonsentrasi di satu IP: pola banyak perangkat di balik satu NAT (Wi-Fi bersama). H2 DIDUKUNG.")
    else:
        add("=> 429 tersebar di banyak IP: bukan pola NAT bersama. H2 lemah.")
elif coverage_start is not None and coverage_start <= since:
    add("=> Nol 429 di jendela. H2 TERBANTAH untuk jendela ini.")
else:
    add("=> Tidak bisa disimpulkan: log nginx untuk jendela tidak tersedia.")
if api:
    ip, n = ip_api.most_common(1)[0]
    add("Sebaran IP untuk request /api/: %d IP berbeda, teratas %s memegang %.0f%%." % (
        len(ip_api), ip, 100.0 * n / len(api)))
    if 100.0 * n / len(api) >= 50:
        add("   Satu IP mendominasi -> perangkat kemungkinan besar di satu jaringan (Wi-Fi venue).")
    else:
        add("   Tidak ada IP dominan -> perangkat kemungkinan besar memakai data seluler masing-masing.")
add("")

add("H3 — Rantai query Supabase yang lambat")
add("--------------------------------------")
if timed:
    rec = [r["rt"] for r in timed if r["path"] == "/api/recognize"]
    add("Format kp_timed terdeteksi: %d request bertiming di jendela." % len(timed))
    if rec:
        add("/api/recognize: n=%d p50=%.3fs p95=%.3fs max=%.3fs (per menit: 54_nginx_request_time_per_minute.tsv)" % (
            len(rec), pct(rec, 50), pct(rec, 95), max(rec)))
elif recog_ms:
    add("Dari log JSON aplikasi: /api/recognize n=%d p95=%.0f ms max=%.0f ms." % (
        len(recog_ms), pct(recog_ms, 95), max(recog_ms)))
else:
    add("Tidak bisa dibuktikan dari log: nginx belum mencatat $request_time/$upstream_response_time")
    add("(pasang nginx-logformat.conf) dan log JSON aplikasi belum ada di jendela ini.")
add("Sinyal tidak langsung: 504 = %d (request menggantung melewati proxy_read_timeout nginx," % status_total.get("504", 0))
add("lihat 41_nginx_directives.txt), 499 = %d (klien menyerah sebelum dijawab)." % status_total.get("499", 0))
add("")

add("H4 — Masalah di sisi klien / jaringan venue")
add("-------------------------------------------")
gaps = [mk for mk in MINUTES if per_min[mk]["total"] == 0]
runs, cur = [], []
for mk in MINUTES:
    if per_min[mk]["total"] == 0:
        cur.append(mk)
    else:
        if len(cur) >= 2:
            runs.append(cur)
        cur = []
if len(cur) >= 2:
    runs.append(cur)
add("Menit tanpa request sama sekali di nginx: %d dari %d menit." % (len(gaps), len(MINUTES)))
for run_ in runs[:10]:
    add("    celah %s s/d %s (%d menit)" % (run_[0], run_[-1], len(run_)))
if records:
    add("Request per menit ada di 51_nginx_status_per_minute.tsv.")
if runs and not lifecycle:
    add("=> Ada celah tanpa request padahal layanan tidak berhenti/restart: request tidak sampai ke")
    add("   server. Itu menunjuk ke jaringan/klien (H4) — cocokkan jamnya dengan kronologi panitia.")
elif records and not runs:
    add("=> Request terus masuk sepanjang jendela: server bisa dijangkau dari luar. Kalau pengguna")
    add("   merasa 'down', penyebabnya ada di jawaban server (lihat 5xx/504), bukan jaringan saja.")
add("")

add("H5 — Koneksi HTTP/2 ke Supabase putus (RemoteProtocolError / ConnectionTerminated)")
add("---------------------------------------------------------------------------------")
for label in ("RemoteProtocolError", "ConnectionTerminated", "ReadTimeout", "ConnectTimeout/ConnectError",
              "PoolTimeout", "Exception in ASGI application"):
    add("%-30s: %d" % (label, pat_total[label]))
first_err = sorted(mk for mk in pat_per_min
                   if pat_per_min[mk]["RemoteProtocolError"] or pat_per_min[mk]["ConnectionTerminated"])
if first_err:
    add("Pertama muncul %s WIB, terakhir %s WIB (per menit: 14_upstream_errors_per_minute.tsv)." % (
        first_err[0], first_err[-1]))
    first504 = next((mk for mk in MINUTES if per_min[mk]["504"]), None)
    if first504:
        add("504 pertama di nginx: %s WIB." % first504)
        if first504 >= first_err[0]:
            add("=> 504 muncul SESUDAH error HTTP/2 pertama: urutannya cocok dengan H5")
            add("   (koneksi hulu putus -> request menumpuk -> timeout nginx).")
        else:
            add("=> 504 sudah muncul SEBELUM error HTTP/2 pertama: H5 tidak menjelaskan awal")
            add("   kejadian sendirian. Cari apa yang membuat request menggantung sebelum %s." % first_err[0])
else:
    add("Tidak ada error protokol HTTP/2 di journal jendela ini.")
add("")

add("Ringkasan status nginx di jendela: " + ", ".join("%s x%d" % (k, v) for k, v in sorted(status_total.items())))
if uvi_status:
    add("Ringkasan status dari log akses aplikasi: " + ", ".join("%s x%d" % (k, v) for k, v in sorted(uvi_status.items())))
if err_kinds:
    add("Error log nginx: " + ", ".join("%s x%d" % (k, v) for k, v in err_kinds.most_common()))
if app_json:
    add("Log JSON aplikasi per logger: " + ", ".join("%s x%d" % (k, v) for k, v in app_json.most_common()))
    add("Level error/critical: %d. Hasil check-in: %s" % (
        app_errors, ", ".join("%s x%d" % kv for kv in checkin_outcome.most_common()) or "-"))
add("")
add("Kondisi host di 30-37_*.txt adalah kondisi SAAT SKRIP DIJALANKAN, bukan saat insiden.")
write("SUMMARY.txt", "\n".join(S) + "\n")
PY

LC_ALL=C python3 "$TOOLS/analyze.py" "$SINCE_EPOCH" "$UNTIL_EPOCH" "$OUT" "$NGINX_LOG_DIR" "$UNIT" \
  2> "$OUT/99_analyze_stderr.txt" || echo "Analisis gagal sebagian — lihat 99_analyze_stderr.txt" >&2

# Log akses mentah bisa memuat token di query string; saring sekali lagi.
if [ -f "$OUT/50_nginx_access_window.log" ]; then
  redact < "$OUT/50_nginx_access_window.log" > "$TOOLS/access.tmp" && mv "$TOOLS/access.tmp" "$OUT/50_nginx_access_window.log"
fi
if [ -f "$OUT/55_nginx_error_window.log" ]; then
  redact < "$OUT/55_nginx_error_window.log" > "$TOOLS/error.tmp" && mv "$TOOLS/error.tmp" "$OUT/55_nginx_error_window.log"
fi

TARBALL="$OUT.tar.gz"
tar -czf "$TARBALL" -C "$OUT_BASE" "$NAME"
chmod 600 "$TARBALL"
# Supaya bisa di-scp oleh user biasa yang menjalankan sudo, tanpa sudo kedua.
if [ -n "${SUDO_USER:-}" ]; then
  chown "$SUDO_USER" "$TARBALL" || true
fi

echo
cat "$OUT/SUMMARY.txt"
echo
echo "Folder : $OUT"
echo "Arsip  : $TARBALL ($(du -h "$TARBALL" | cut -f1))"
echo "Ambil ke laptop: scp <user>@<ip-vps>:$TARBALL ."
echo "Isinya memuat IP dan user_id — simpan privat, hapus dari /tmp setelah diambil."
