import os
import uuid
import base64
import socket
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(tags=["photobooth"])

UPLOAD_DIR = Path("frontend/uploads/photobooth")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class PhotoboothUploadDto(BaseModel):
    image: str = Field(..., description="Base64 encoded JPEG data string")
    frame: str = Field(default="merah-putih", description="Selected frame identifier")
    caption: str = Field(default="", description="Custom strip caption")

def get_lan_ip() -> str:
    """Retrieve host local network IP for accurate mobile QR code resolution."""
    configured_url = os.getenv("PHOTOBOOTH_BASE_URL")
    if configured_url:
        return configured_url.rstrip("/")
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        # Connect to public DNS to determine default routing interface IP
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
        return f"http://{lan_ip}:8000"
    except Exception:
        return "http://localhost:8000"

@router.post("/api/photobooth/upload")
async def upload_photobooth_strip(request: Request, payload: PhotoboothUploadDto):
    try:
        # Validate base64 header
        raw_data = payload.image
        if "," in raw_data:
            raw_data = raw_data.split(",", 1)[1]

        image_bytes = base64.b64decode(raw_data)
        
        # Max 10MB sanity check
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Ukuran foto terlalu besar.")

        photo_id = uuid.uuid4().hex[:8]
        filename = f"{photo_id}.jpg"
        file_path = UPLOAD_DIR / filename

        with open(file_path, "wb") as f:
            f.write(image_bytes)

        base_host = get_lan_ip()
        view_url = f"/p/{photo_id}"
        full_qr_url = f"{base_host}/p/{photo_id}"
        download_url = f"/static/uploads/photobooth/{filename}"

        return {
            "status": "success",
            "photo_id": photo_id,
            "view_url": view_url,
            "download_url": download_url,
            "qr_url": full_qr_url,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.get("/p/{photo_id}", response_class=HTMLResponse)
async def view_photobooth_photo(photo_id: str):
    filename = f"{photo_id}.jpg"
    file_path = UPLOAD_DIR / filename
    
    if not file_path.exists():
        return HTMLResponse(
            status_code=404,
            content="""
            <!DOCTYPE html>
            <html lang="id">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Foto Tidak Ditemukan — KP Bromo</title>
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body class="bg-[#06070a] text-slate-100 min-h-screen flex items-center justify-center p-6 text-center">
                <div class="max-w-md bg-[#0b0d13] p-8 rounded-3xl border border-white/10 shadow-2xl">
                    <h1 class="text-xl font-bold text-rose-400 mb-2">Foto Tidak Ditemukan</h1>
                    <p class="text-sm text-slate-400 mb-6">Foto mungkin sudah kedaluwarsa atau tautan salah.</p>
                    <a href="/photobooth" class="inline-block px-5 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-xl text-xs font-semibold text-white">Buka Photobooth</a>
                </div>
            </body>
            </html>
            """
        )

    image_src = f"/static/uploads/photobooth/{filename}"
    
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Photo Strip — KP Bromo Malang</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
                        mono: ['"JetBrains Mono"', 'monospace'],
                    }},
                    colors: {{
                        obsidian: {{ 950: '#06070a', 900: '#0b0d13', 850: '#11141e', 800: '#171b28' }},
                        azure: {{ 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8' }}
                    }}
                }}
            }}
        }}
    </script>
</head>
<body class="bg-obsidian-950 text-slate-100 min-h-screen flex flex-col items-center justify-between p-4 selection:bg-azure-500 selection:text-white font-sans antialiased">
    
    <!-- Top Bar -->
    <header class="w-full max-w-sm flex items-center justify-between py-3 border-b border-white/[0.06] mb-4">
        <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-rose-600 to-azure-600 flex items-center justify-center font-bold text-xs text-white shadow-md">
                KP
            </div>
            <div>
                <h1 class="text-xs font-extrabold tracking-tight text-white leading-none">KP BROMO PHOTOBOOTH</h1>
                <p class="text-[10px] text-slate-400 font-mono mt-0.5">Komisi Pemuda GKI Bromo</p>
            </div>
        </div>
        <a href="/photobooth" class="text-[11px] font-mono font-semibold text-cyan-400 hover:underline">Booth &rarr;</a>
    </header>

    <!-- Photo Strip Container -->
    <main class="w-full max-w-sm flex flex-col items-center flex-1 justify-center my-2">
        <div class="relative bg-obsidian-900 p-2.5 rounded-3xl border border-white/[0.08] shadow-2xl shadow-black/80 max-h-[68vh] flex items-center justify-center">
            <img id="photo-strip" src="{image_src}" alt="KP Bromo Photo Strip" class="max-h-[64vh] w-auto rounded-2xl object-contain shadow-md" />
        </div>
    </main>

    <!-- Actions Bottom Bar -->
    <footer class="w-full max-w-sm flex flex-col gap-2.5 pt-4 pb-2 border-t border-white/[0.06]">
        <div class="grid grid-cols-2 gap-2.5">
            <a href="{image_src}" download="KP_Bromo_PhotoStrip_{photo_id}.jpg" class="py-3.5 px-4 bg-azure-600 hover:bg-azure-500 active:scale-[0.98] text-white rounded-2xl text-xs font-bold text-center shadow-lg shadow-azure-600/30 flex items-center justify-center gap-2 transition-all">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                <span>Simpan Foto</span>
            </a>
            
            <button id="btn-share" class="py-3.5 px-4 bg-obsidian-850 hover:bg-obsidian-800 border border-white/10 active:scale-[0.98] text-slate-200 rounded-2xl text-xs font-semibold flex items-center justify-center gap-2 transition-all">
                <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                </svg>
                <span>Bagikan</span>
            </button>
        </div>

        <p class="text-center text-[10px] font-mono text-slate-500 mt-1">
            Tekan & tahan foto jika unduhan otomatis terblokir browser.
        </p>
    </footer>

    <script>
        document.getElementById('btn-share').addEventListener('click', async () => {{
            if (navigator.share) {{
                try {{
                    await navigator.share({{
                        title: 'Photo Strip KP Bromo',
                        text: 'Keseruan di Komisi Pemuda GKI Bromo Malang!',
                        url: window.location.href
                    }});
                }} catch (err) {{
                    console.log('Share dismissed');
                }}
            }} else {{
                await navigator.clipboard.writeText(window.location.href);
                alert('Tautan foto berhasil disalin ke papan klip!');
            }}
        }});
    </script>
</body>
</html>
        """
    )
