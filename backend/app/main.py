from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import audiences, materials, meta, recipes
from .seed import seed_if_empty

app = FastAPI(title="charkaLab API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    seed_if_empty()


app.include_router(materials.router)
app.include_router(meta.router)
app.include_router(recipes.router)
app.include_router(audiences.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
