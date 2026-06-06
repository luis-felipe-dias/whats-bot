from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # MongoDB Atlas
    mongodb_url: str
    mongodb_db_name: str = "yup_customer_service"
    
    # Z-API
    zapi_instance_id: str
    zapi_token: str  # Token da instância (URL)
    zapi_client_token: str  # Client-Token (Header)
    zapi_url: str = "https://api.z-api.io"
    
    # WhatsApp Config
    whatsapp_save_contacts: bool = True
    whatsapp_delay_min: int = 1
    whatsapp_delay_max: int = 3
    whatsapp_retry_attempts: int = 3
    
    # Environment
    environment: str = "development"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()