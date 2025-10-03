from fastsyftbox import FastSyftBox
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from syft_core.config import SyftClientConfig
from fastapi import APIRouter


from .config import app_settings


app = FastSyftBox(
    app_name="SyftAIServer",
    syftbox_config=SyftClientConfig.load(app_settings.syftbox_config_path),
    version="1.0.0",
    syftbox_endpoint_tags=["syftbox"],
    debug=app_settings.debug,
    
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api/v1")

@router.get("/health")
async def health():
    return {"status": "healthy"}

# Include the router in the app
app.include_router(router)

app.mount("/", StaticFiles(directory="frontend/dist", html=True, check_dir=False))
