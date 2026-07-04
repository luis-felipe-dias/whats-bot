# app/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional
import pytz

class Settings(BaseSettings):
    # MongoDB Atlas
    mongodb_url: str
    mongodb_db_name: str = "yup_customer_service"
    
    # Z-API
    zapi_instance_id: str
    zapi_token: str
    zapi_client_token: str
    zapi_url: str = "https://api.z-api.io"
    
    # WhatsApp Config
    whatsapp_save_contacts: bool = True
    whatsapp_delay_min: int = 1
    whatsapp_delay_max: int = 3
    whatsapp_retry_attempts: int = 3
    
    # Environment
    environment: str = "development"
    log_level: str = "INFO"
    
    # Timezone
    timezone: str = "America/Sao_Paulo"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Criar objeto de timezone para usar em toda a aplicação
TIMEZONE = pytz.timezone(settings.timezone)
