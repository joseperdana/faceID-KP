import os
import uuid
import base64
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(tags=["photobooth"])

UPLOAD_DIR = Path("frontend/uploads/photobooth")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class PhotoboothUploadDto(BaseModel):
    image: str = Field(..., description="Base64 encoded JPEG data string of the Photo Strip")
    gif_image: Optional[str] = Field(default="", description="Base64 encoded GIF data string")
    frame: str = Field(default="3-strip", description="Selected layout identifier")
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
        
        if len(image_bytes) > 12 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Ukuran foto melebihi batas 12MB.")

        photo_id = uuid.uuid4().hex[:8]
        filename = f"{photo_id}.jpg"
        file_path = UPLOAD_DIR / filename

        with open(file_path, "wb") as f:
            f.write(image_bytes)

        # Save Animated GIF if provided
        gif_filename = None
        gif_download_url = None
        if payload.gif_image and len(payload.gif_image) > 50:
            try:
                raw_gif = payload.gif_image
                if "," in raw_gif:
                    raw_gif = raw_gif.split(",", 1)[1]
                gif_bytes = base64.b64decode(raw_gif)
                gif_filename = f"{photo_id}.gif"
                gif_file_path = UPLOAD_DIR / gif_filename
                with open(gif_file_path, "wb") as gf:
                    gf.write(gif_bytes)
                gif_download_url = f"/static/uploads/photobooth/{gif_filename}"
            except Exception as ge:
                print(f"Warning: Failed to save GIF: {ge}")

        base_host = get_lan_ip()
        view_url = f"/p/{photo_id}"
        full_qr_url = f"{base_host}/p/{photo_id}"
        download_url = f"/static/uploads/photobooth/{filename}"

        return {
            "status": "success",
            "photo_id": photo_id,
            "view_url": view_url,
            "download_url": download_url,
            "gif_download_url": gif_download_url,
            "qr_url": full_qr_url,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.get("/p/{photo_id}", response_class=HTMLResponse)
async def view_photobooth_photo(photo_id: str):
    filename = f"{photo_id}.jpg"
    file_path = UPLOAD_DIR / filename
    gif_filename = f"{photo_id}.gif"
    gif_path = UPLOAD_DIR / gif_filename
    
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
            <body class="bg-[#fff8f1] text-[#211b0b] min-h-screen flex items-center justify-center p-6 text-center">
                <div class="max-w-md bg-white p-8 rounded-3xl border-[3px] border-[#1d3557] shadow-[4px_4px_0px_#1d3557]">
                    <h1 class="text-xl font-bold text-[#b7102a] mb-2">Foto Tidak Ditemukan</h1>
                    <p class="text-sm text-slate-600 mb-6">Foto mungkin sudah kedaluwarsa atau tautan salah.</p>
                    <a href="/photobooth" class="inline-block px-6 py-2.5 bg-[#b7102a] hover:bg-[#e63946] rounded-full text-xs font-bold text-white shadow-[2px_2px_0px_#1d3557] border-2 border-[#1d3557]">Buka Photobooth</a>
                </div>
            </body>
            </html>
            """
        )

    image_src = f"/static/uploads/photobooth/{filename}"
    has_gif = gif_path.exists()
    gif_src = f"/static/uploads/photobooth/{gif_filename}" if has_gif else ""
    
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Photo Strip Pesta Merdeka — KP Bromo</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
                        display: ['"Bricolage Grotesk"', 'sans-serif'],
                    }},
                    colors: {{
                        merdeka: {{
                            surface: '#fff8f1',
                            'surface-container': '#faedd2',
                            'on-surface': '#211b0b',
                            navy: '#1d3557',
                            red: '#b7102a',
                            gold: '#ffd700',
                        }}
                    }},
                    boxShadow: {{
                        'pesta': '4px 4px 0px #1d3557',
                        'pesta-sm': '2px 2px 0px #1d3557',
                    }}
                }}
            }}
        }}
    </script>
</head>
<body class="bg-merdeka-surface text-merdeka-on-surface min-h-screen flex flex-col items-center justify-between p-4 selection:bg-merdeka-red selection:text-white font-sans antialiased">
    
    <!-- Top Bar -->
    <header class="w-full max-w-sm flex items-center justify-between py-3 border-b-2 border-merdeka-navy/15 mb-3">
        <div class="flex items-center gap-2.5">
            <div class="w-9 h-9 rounded-2xl bg-merdeka-red flex items-center justify-center font-display font-extrabold text-xs text-white border-2 border-merdeka-navy shadow-pesta-sm -rotate-2">
                KP
            </div>
            <div>
                <h1 class="text-xs font-display font-extrabold tracking-tight text-merdeka-on-surface leading-none">PESTA MERDEKA</h1>
                <p class="text-[10px] text-slate-500 font-medium mt-0.5">Komisi Pemuda GKI Bromo</p>
            </div>
        </div>
        <a href="/photobooth" class="text-xs font-display font-extrabold text-merdeka-red hover:underline">Booth &rarr;</a>
    </header>

    <!-- Photo Container & Dual Tabs -->
    <main class="w-full max-w-sm flex flex-col items-center flex-1 justify-center my-1">
        
        <!-- Toggle Tabs if GIF is available -->
        <div class="{'flex' if has_gif else 'hidden'} justify-center gap-2 mb-2.5 w-full">
            <button id="mobile-tab-strip" class="py-1 px-4 bg-white border-2 border-merdeka-navy rounded-full text-xs font-display font-extrabold shadow-pesta-sm text-merdeka-red">
                Photo Strip
            </button>
            <button id="mobile-tab-gif" class="py-1 px-4 bg-merdeka-surface-container border-2 border-merdeka-navy rounded-full text-xs font-display font-bold text-merdeka-navy">
                Animated GIF
            </button>
        </div>

        <div class="relative bg-white p-3 rounded-3xl border-[3px] border-merdeka-navy shadow-pesta max-h-[64vh] flex items-center justify-center">
            <img id="mobile-img-strip" src="{image_src}" alt="KP Bromo Photo Strip" class="max-h-[58vh] w-auto rounded-2xl object-contain shadow-sm border border-merdeka-navy/20" />
            <img id="mobile-img-gif" src="{gif_src}" alt="KP Bromo Animated GIF" class="hidden max-h-[58vh] w-auto rounded-2xl object-contain shadow-sm border border-merdeka-navy/20" />
        </div>
    </main>

    <!-- Actions Bottom Bar -->
    <footer class="w-full max-w-sm flex flex-col gap-2 pt-3 pb-2 border-t-2 border-merdeka-navy/15">
        <div class="grid grid-cols-2 gap-2">
            <a id="btn-mobile-download" href="{image_src}" download="KP_Bromo_Photo_{photo_id}.jpg" class="py-3 px-3 bg-merdeka-red hover:bg-[#e63946] active:translate-x-0.5 active:translate-y-0.5 text-white rounded-full text-xs font-display font-extrabold text-center shadow-pesta border-2 border-merdeka-navy flex items-center justify-center gap-2 transition-all">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                <span>Simpan Foto</span>
            </a>
            
            <button id="btn-share" class="py-3 px-3 bg-white hover:bg-merdeka-surface-container border-2 border-merdeka-navy active:translate-x-0.5 active:translate-y-0.5 text-merdeka-navy rounded-full text-xs font-display font-extrabold flex items-center justify-center gap-2 transition-all shadow-pesta">
                <svg class="w-4 h-4 text-merdeka-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                </svg>
                <span>Bagikan</span>
            </button>
        </div>

        <p class="text-center text-[10px] font-mono text-slate-500 mt-0.5">
            Tekan & tahan foto jika unduhan otomatis terblokir browser.
        </p>
    </footer>

    <script>
        const tabStrip = document.getElementById('mobile-tab-strip');
        const tabGif = document.getElementById('mobile-tab-gif');
        const imgStrip = document.getElementById('mobile-img-strip');
        const imgGif = document.getElementById('mobile-img-gif');
        const btnDownload = document.getElementById('btn-mobile-download');

        if (tabStrip && tabGif) {{
            tabStrip.addEventListener('click', () => {{
                imgStrip.classList.remove('hidden');
                imgGif.classList.add('hidden');
                tabStrip.className = "py-1 px-4 bg-white border-2 border-merdeka-navy rounded-full text-xs font-display font-extrabold shadow-pesta-sm text-merdeka-red";
                tabGif.className = "py-1 px-4 bg-merdeka-surface-container border-2 border-merdeka-navy rounded-full text-xs font-display font-bold text-merdeka-navy";
                btnDownload.href = "{image_src}";
                btnDownload.download = "KP_Bromo_Photo_{photo_id}.jpg";
            }});

            tabGif.addEventListener('click', () => {{
                imgGif.classList.remove('hidden');
                imgStrip.classList.add('hidden');
                tabGif.className = "py-1 px-4 bg-white border-2 border-merdeka-navy rounded-full text-xs font-display font-extrabold shadow-pesta-sm text-merdeka-navy";
                tabStrip.className = "py-1 px-4 bg-merdeka-surface-container border-2 border-merdeka-navy rounded-full text-xs font-display font-bold text-merdeka-navy";
                btnDownload.href = "{gif_src}";
                btnDownload.download = "KP_Bromo_Animated_{photo_id}.gif";
            }});
        }}

        document.getElementById('btn-share').addEventListener('click', async () => {{
            if (navigator.share) {{
                try {{
                    await navigator.share({{
                        title: 'Pesta Merdeka Photo Strip KP Bromo',
                        text: 'Keseruan Photobooth 17an di Komisi Pemuda GKI Bromo Malang!',
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
