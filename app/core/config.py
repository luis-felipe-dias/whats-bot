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
    
    # ------------------------------------------------------------------
    # API Oficial da Meta (Cloud API)
    # Convivem com a Z-API de propósito: durante o teste o 8882 segue na
    # Z-API e o número novo entra pela Meta. Uma não desliga a outra.
    # ------------------------------------------------------------------
    meta_enabled: bool = False
    meta_api_version: str = "v23.0"
    meta_phone_number_id: str = ""      # ID do número (não é o telefone)
    meta_waba_id: str = ""              # conta de mensagens
    meta_access_token: str = ""         # token do usuário do sistema
    meta_app_secret: str = ""           # assina o webhook — sem ele, porta aberta
    meta_verify_token: str = ""         # string que VOCÊ inventa, igual nos dois lados

    # URL pública do backend, com HTTPS. A Meta não aceita IP nem HTTP,
    # e é ela que monta o link da mídia que o painel abre.
    backend_public_url: str = ""

    # ------------------------------------------------------------------
    # Peper IA (MVP) — faixa paralela à máquina de estados
    # Desligada por padrão. Liga por telefone, nunca para todos.
    # ------------------------------------------------------------------
    ia_enabled: bool = False
    # Lista branca, separada por vírgula, com DDI. Vazia = ninguém.
    ia_numeros: str = ""
    # "meta" (número de teste / 0424) ou "zapi" (produção, 8882).
    ia_canal: str = "meta"
    # Teto de consultas ao ERP por conversa. A cota do Olist é POR CONTA
    # e é dividida com o sync de reposição da Daiane.
    ia_max_consultas_erp: int = 3
    # Minutos sem NENHUM atendente responder até a Peper reassumir a
    # conversa. 0 desliga a devolução automática.
    ia_retomar_apos_minutos: int = 15

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_model_audio: str = "whisper-1"
    openai_model_embedding: str = "text-embedding-3-small"
    # 0.4, não 0.6. Atendimento não é escrita criativa: a Peper precisa
    # repetir a mesma resposta certa para a mesma pergunta. Temperatura alta
    # é o que faz ela "variar" um dado da ficha ou reformular uma regra até
    # ela deixar de ser a regra.
    openai_temperature: float = 0.4
    openai_max_tokens: int = 350

    # Filtro de palavras proibidas na resposta PRONTA, antes de enviar.
    # Ligado significa que resposta com termo bloqueado NÃO sai e a conversa
    # vira chamada de equipe. É mudança de comportamento em produção: se a
    # lista ficar mal preenchida, o efeito é transferência demais, não texto
    # errado — por isso o padrão é ligado, e desligar é uma linha no .env.
    filtro_palavras_ativo: bool = True

    # Backend de estoque (meu_projeto). O bot consulta produto AQUI,
    # nunca direto no Olist — um dono do token, um limitador.
    backend_estoque_url: str = "http://127.0.0.1:8000"

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
