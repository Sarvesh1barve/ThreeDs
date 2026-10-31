from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from .config import get_settings
from .db import SessionLocal
from .routers import admin, auth, orders, public
from .services.seed import bootstrap

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


@asynccontextmanager
async def lifespan(app):
    with SessionLocal() as db:
        bootstrap(db)
    yield


app = FastAPI(title="Three D's Exhibition Store", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)
cfg = get_settings()
app.add_middleware(CORSMiddleware, allow_origins=list(cfg.origins), allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token", "ngrok-skip-browser-warning"])


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            length = int(request.headers.get("content-length", "0") or 0)
            content_type = request.headers.get("content-type", "").lower()
            if length > 6 * 1024 * 1024:
                return JSONResponse({"code": "request_too_large", "message": "Request body is too large."}, status_code=413)
            plain_handoff = request.url.path == "/api/guest-cart-handoff" and content_type.startswith("text/plain")
            if length and not (content_type.startswith("application/json") or content_type.startswith("multipart/form-data") or plain_handoff):
                return JSONResponse({"code": "unsupported_media_type", "message": "Use JSON or multipart form data."}, status_code=415)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeaders)
app.include_router(public.router)
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(admin.router)


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
    return JSONResponse(detail, status_code=exc.status_code, headers=exc.headers)


@app.get("/media/{name}")
def media(name: str):
    if not name.endswith(".webp") or Path(name).name != name:
        raise HTTPException(404)
    path = get_settings().data_dir / "uploads" / name
    if not path.is_file(): raise HTTPException(404)
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})


app.mount("/assets", StaticFiles(directory=FRONTEND / "assets", check_dir=False), name="assets")


@app.get("/")
def home(): return FileResponse(FRONTEND / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon(): return Response(status_code=204)


@app.get("/checkout")
def checkout(): return FileResponse(FRONTEND / "checkout.html")


@app.get("/checkout.html", include_in_schema=False)
def checkout_static_alias(): return FileResponse(FRONTEND / "checkout.html")


@app.get("/admin")
def admin_page(): return FileResponse(FRONTEND / "admin.html")


@app.get("/admin.html", include_in_schema=False)
def admin_static_alias(): return FileResponse(FRONTEND / "admin.html")

