from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import app_settings

app = FastAPI(
    title="NSAI API",
    version="1.0.0",
    debug=app_settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "healthy"}


app.mount("/", StaticFiles(directory="frontend/dist", html=True, check_dir=False))
