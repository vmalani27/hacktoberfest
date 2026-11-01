import os
from pydantic_settings import BaseSettings

default_workspace = "/workspace" if os.path.exists("/workspace") else os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "workspace")
)

class Settings(BaseSettings):
    APP_NAME: str = "DeployAssistant"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # LLM Provider Configuration ("bedrock" or "openai")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "bedrock")

    # Amazon Bedrock Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")
    BEDROCK_MODEL_ID: str = os.getenv("BEDROCK_MODEL_ID", "google.gemma-3-4b-it")

    # OpenAI-Compatible Configuration (Google AI Studio, OpenAI, etc.)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", os.getenv("GROQ_API_KEY", os.getenv("GEMINI_API_KEY", "")))
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "qwen-2.5-coder-32b")

    # Sandbox / Execution
    DOCKER_HOST_URL: str = os.getenv("DOCKER_HOST", "")
    SANDBOX_CONTAINER_NAME: str = os.getenv("SANDBOX_CONTAINER_NAME", "deploy-assistant-sandbox")
    WORKSPACE_DIR: str = os.getenv("WORKSPACE_DIR", default_workspace)
    COMMAND_TIMEOUT_SECONDS: int = 120
    MAX_STEP_LIMIT: int = 25
    MAX_RETRY_LIMIT: int = 3

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
