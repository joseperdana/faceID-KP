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
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
        return f"http://{lan_ip}:8000"
    except Exception:
        return "http://localhost:8000"

@router.post("/api/photobooth/upload")
async def upload_photobooth_strip(request: Request, payload: PhotoboothUploadDto):
    try:
        raw_data = payload.image
        if "," in raw_data:
            raw_data = raw_data.split(",", 1)[1]

        image_bytes = base64.b64decode(raw_data)
        
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Ukuran foto melebihi batas 10MB.")

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
            <body class="bg-[#07090e] text-slate-100 min-h-screen flex items-center justify-center p-6 text-center">
                <div class="max-w-md bg-[#0c0f17] p-8 rounded-3xl border-2 border-white/10 shadow-[4px_4px_0px_#000000]">
                    <h1 class="text-xl font-bold text-rose-400 mb-2">Foto Tidak Ditemukan</h1>
                    <p class="text-sm text-slate-400 mb-6">Foto mungkin sudah kedaluwarsa atau tautan salah.</p>
                    <a href="/photobooth" class="inline-block px-5 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-2xl text-xs font-bold text-white shadow-[2px_2px_0px_#000000] border border-black">Buka Photobooth</a>
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
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700;800&family=Plus+Jakarta+Sans:wght@500;700;800;900&family=Space+Grotesk:wght@700;800&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
                        display: ['"Space Grotesk"', 'sans-serif'],
                        mono: ['"JetBrains Mono"', 'monospace'],
                    }},
                    colors: {{
                        canvas: {{ 950: '#07090e', 900: '#0c0f17', 850: '#121623' }},
                        pop: {{ blue: '#2563eb', yellow: '#fbbf24', red: '#ef4444' }}
                    }},
                    boxShadow: {{
                        'neo': '4px 4px 0px #000000',
                        'neo-sm': '2px 2px 0px #000000',
                    }}
                }}
            }}
        }}
    </script>
</head>
<body class="bg-canvas-950 text-slate-100 min-h-screen flex flex-col items-center justify-between p-4 selection:bg-pop-blue selection:text-white font-sans antialiased">
    
    <!-- Top Bar -->
    <header class="w-full max-w-sm flex items-center justify-between py-3 border-b-2 border-white/10 mb-3">
        <div class="flex items-center gap-2.5">
            <div class="w-9 h-9 rounded-2xl bg-gradient-to-br from-pop-red to-pop-yellow flex items-center justify-center font-display font-black text-xs text-white border-2 border-black shadow-neo-sm">
                KP
            </div>
            <div>
                <h1 class="text-xs font-display font-black tracking-tight text-white leading-none">KP BROMO PHOTO STRIP</h1>
                <p class="text-[10px] text-slate-400 font-mono mt-0.5">Komisi Pemuda GKI Bromo</p>
            </div>
        </div>
        <a href="/photobooth" class="text-xs font-mono font-bold text-pop-yellow hover:underline">Booth &rarr;</a>
    </header>

    <!-- Photo Strip Container -->
    <main class="w-full max-w-sm flex flex-col items-center flex-1 justify-center my-2">
        <div class="relative bg-canvas-900 p-3 rounded-3xl border-2 border-white/15 shadow-neo max-h-[68vh] flex items-center justify-center">
            <img id="photo-strip" src="{image_src}" alt="KP Bromo Photo Strip" class="max-h-[64vh] w-auto rounded-2xl object-contain shadow-md border border-white/10" />
        </div>
    </main>

    <!-- Actions Bottom Bar -->
    <footer class="w-full max-w-sm flex flex-col gap-2.5 pt-3 pb-2 border-t-2 border-white/10">
        <div class="grid grid-cols-2 gap-2.5">
            <a href="{image_src}" download="KP_Bromo_PhotoStrip_{photo_id}.jpg" class="py-3.5 px-4 bg-pop-blue hover:brightness-110 active:translate-x-0.5 active:translate-y-0.5 text-white rounded-2xl text-xs font-display font-black text-center shadow-neo border-2 border-black flex items-center justify-center gap-2 transition-all">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                <span>Simpan Foto</span>
            </a>
            
            <button id="btn-share" class="py-3.5 px-4 bg-canvas-850 hover:bg-canvas-900 border-2 border-white/15 active:translate-x-0.5 active:translate-y-0.5 text-slate-200 rounded-2xl text-xs font-display font-bold flex items-center justify-center gap-2 transition-all shadow-neo">
                <svg class="w-4 h-4 text-pop-yellow" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                </svg>
                <span>Bagikan</span>
            </button>
        </div>

        <p class="text-center text-[10px] font-mono text-slate-400 mt-1">
            Tekan & tahan foto jika download otomatis terblokir browser.
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
                alert('Tautan foto berhasil disalin!');
            }}
        }});
    </script>
</body>
</html>
        """
    )
