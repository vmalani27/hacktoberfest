from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes.session import router as session_router
from app.routes.agent import router as agent_router
from app.routes.terminal import router as terminal_router
from app.routes.sandbox import router as sandbox_router

app = FastAPI(
    title="LabOps Deploy Assistant API",
    description="Interactive containerization & sandbox deployment assistant",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router)
app.include_router(agent_router)
app.include_router(terminal_router)
app.include_router(sandbox_router)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "llm_provider": settings.LLM_PROVIDER
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
