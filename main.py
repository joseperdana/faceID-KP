from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import sentry_sdk

load_dotenv()

sentry_sdk.init(
    dsn="https://ff28457d829bca1529a766c0a39ac98e@o4510878135484416.ingest.us.sentry.io/4510878144987136",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

from routers import pages, auth, kiosk, users, analytics, attendance

app = FastAPI(title="KPBromoMalang API")

@app.exception_handler(401)
async def unauthorized_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
    return RedirectResponse(url="/login", status_code=303)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(kiosk.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(attendance.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
