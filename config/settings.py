import os
from pathlib import Path

class Settings:
    PROJECT_NAME: str = "Jarvis"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    
    # IoT Settings
    MQTT_BROKER: str = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
    
    # Memory Settings
    DB_PATH: Path = BASE_DIR / "memory" / "jarvis_memory.db"

settings = Settings()
