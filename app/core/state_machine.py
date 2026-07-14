# app/core/state_machine.py
from typing import Tuple, Dict
import logging
import re

logger = logging.getLogger(__name__)

class StateMachine:
    async def process_message(self, sessao: dict, mensagem: str) -> Tuple[str, Dict]:
        
        estado_atual = sessao.get("estado_atual", "menu_principal")
        msg_clean = self._limpar_mensagem(mensagem)
        
        logger.info(f"Estado: {estado_atual} | Msg: {mensagem[:50]}")
        
        # ============================================
        # CANCELAR
        # ============================================
        if "cancelar" in msg_clean or "cancel" in msg_clean:
            return "menu_principal", {
                "texto": "✅ Atendimento cancelado! Volte ao menu principal. 💙",
                "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
            }
        
        # ============================================
        # VOLTAR - Comando global para voltar ao menu anterior
        # ============================================
        if mensagem == "◀️ VOLTAR" or msg_clean == "voltar":
            # Se estiver em um submenu, volta para o menu principal
            if estado_atual in ["promocoes", "servicos", "atendimento", "informacoes", "trabalhe"]:
                return "menu_principal", {
                    "texto": "✨ *PEPER* - Assistente Virtual\n\nComo posso ajudar você hoje? 💙",
                    "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                }
            # Se estiver no menu principal, mantém
            return "menu_principal", {
                "texto": "✨ *PEPER* - Assistente Virtual\n\nComo posso ajudar você hoje? 💙",
                "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
            }
        
        # ============================================
        # SAUDAÇÃO
        # ============================================
        if msg_clean in ["olá", "ola", "oi", "bomdia", "boatarde", "boanoite", "tudobem", "inicio", "menu", "start"]:
            return "menu_principal", {
                "texto": "‼️ *EM TESTE* - Agradecemos a compreensão de todos! 💙\n\nOi! Eu sou a Peper, assistente virtual da Yup.\n\nSabe aquele \"Yuuup!\" que uma criança diz quando encontra algo que a encanta? ✨ Foi essa alegria espontânea que inspirou o nome da nossa loja.\n\nQueremos que cada visita à Yup desperte esse mesmo sentimento: descobrir, criar, aprender e se divertir!\n\nAgora me conte: como posso ajudar você hoje? 😊",
                "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
            }
        
        # ============================================
        # MENU PRINCIPAL
        # ============================================
        if estado_atual == "menu_principal":
            if msg_clean in ["promoções", "promocoes", "1"]:
                return "promocoes", {
                    "texto": "🎁 *PROMOÇÕES YUP*\n\nOfertas exclusivas para você! 💙",
                    "botoes": ["🎁 GRUPO VIP", "🔥 PROMOÇÕES", "🌐 SITE YUP", "◀️ VOLTAR"]
                }
            elif msg_clean in ["serviços", "servicos", "2"]:
                return "servicos", {
                    "texto": "🖨️ *SERVIÇOS YUP*\n\n⚠️ *ATENÇÃO:* Todos os serviços são realizados APÓS a confirmação do pagamento. 💙\n\nSelecione o serviço desejado:",
                    "botoes": ["⚫ IMPRESSÃO", "📚 ENCADERNAÇÃO", "📄 PLASTIFICAÇÃO", "◀️ VOLTAR"]
                }
            elif msg_clean in ["atendimento", "3"]:
                return "atendimento", {
                    "texto": "🤝 *ATENDIMENTO YUP*\n\nComo podemos ajudar? Selecione uma opção: 💙",
                    "botoes": ["👨‍💼 ATENDENTE", "📦 MEU PEDIDO", "🔄 TROCAS", "⚠️ RECLAMAÇÕES", "💡 SUGESTÕES", "◀️ VOLTAR"]
                }
            elif msg_clean in ["informações", "informacoes", "4"]:
                return "informacoes", {
                    "texto": "📍 *INFORMAÇÕES YUP*\n\nSelecione a informação desejada: 💙",
                    "botoes": ["📍 ENDEREÇO", "📷 INSTAGRAM", "🌐 SITE", "◀️ VOLTAR"]
                }
            elif msg_clean in ["trabalhe", "trabalheconosco", "5"]:
                return "trabalhe", {
                    "texto": "💼 *TRABALHE CONOSCO*\n\nEstamos sempre em busca de talentos! 💙\n\n📄 Envie seu currículo em PDF para o nosso WhatsApp.\n\nNossa equipe de RH entrará em contato em até 5 dias úteis.",
                    "botoes": ["📄 ENVIAR CURRÍCULO", "📢 VER VAGAS", "◀️ VOLTAR"]
                }
            else:
                return "menu_principal", {
                    "texto": "⚠️ *OPÇÃO INVÁLIDA!*\n\nPor favor, selecione uma das opções abaixo: 💙",
                    "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                }
        
        # ============================================
        # PROMOÇÕES
        # ============================================
        if estado_atual == "promocoes":
            if msg_clean in ["grupovip", "1"]:
                return "menu_principal", {
                    "texto": "🎁 *GRUPOS VIP YUP*\n\n📱 Grupo 1: https://chat.whatsapp.com/Cbh5Whh7pmU7jqMciI5bbs\n\n📱 Grupo 2: https://chat.whatsapp.com/I2ZMLyHoGM13hPHpWNcCjD\n\n🔗 Clique nos links acima para entrar! 💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["promoções", "promocoes", "ofertas", "2"]:
                return "menu_principal", {
                    "texto": "🔥 *PROMOÇÕES DA SEMANA* 🔥\n\n👉 https://yupaper.com.br/categoria/promocoes_inverno/\n\nAproveite! 💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["site", "siteyup", "3"]:
                return "menu_principal", {
                    "texto": "🌐 *LOJA ONLINE YUP*\n\n👉 https://yupaper.com.br/\n\n💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["voltar", "◀️ voltar"]:
                return "menu_principal", {
                    "texto": "✨ *PEPER* - Assistente Virtual\n\nComo posso ajudar você hoje? 💙",
                    "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                }
            else:
                return "promocoes", {
                    "texto": "⚠️ *OPÇÃO INVÁLIDA!*\n\nPor favor, selecione uma opção válida: 💙",
                    "botoes": ["🎁 GRUPO VIP", "🔥 PROMOÇÕES", "🌐 SITE YUP", "◀️ VOLTAR"]
                }
        
        # ============================================
        # SERVIÇOS
        # ============================================
        if estado_atual == "servicos":
            if msg_clean in ["impressão", "impressao", "1"]:
                return self._atendente("IMPRESSÃO", "impressao", "tecnico")
            elif msg_clean in ["encadernação", "encadernacao", "2"]:
                return self._atendente("ENCADERNAÇÃO", "encadernacao", "tecnico")
            elif msg_clean in ["plastificação", "plastificacao", "3"]:
                return self._atendente("PLASTIFICAÇÃO", "plastificacao", "tecnico")
            elif msg_clean in ["voltar", "◀️ voltar"]:
                return "menu_principal", {
                    "texto": "✨ *PEPER* - Assistente Virtual\n\nComo posso ajudar você hoje? 💙",
                    "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                }
            else:
                return "servicos", {
                    "texto": "⚠️ *OPÇÃO INVÁLIDA!*\n\nPor favor, selecione um serviço válido: 💙",
                    "botoes": ["⚫ IMPRESSÃO", "📚 ENCADERNAÇÃO", "📄 PLASTIFICAÇÃO", "◀️ VOLTAR"]
                }
        
        # ============================================
        # ATENDIMENTO
        # ============================================
        if estado_atual == "atendimento":
            if msg_clean in ["atendente", "humano", "1"]:
                return self._atendente("ATENDIMENTO HUMANO", "atendente", "atendimento")
            elif msg_clean in ["meupedido", "pedido", "2"]:
                return self._atendente("CONSULTA DE PEDIDO", "pedido", "financeiro")
            elif msg_clean in ["trocas", "devoluções", "devolucoes", "3"]:
                return self._atendente("TROCA/DEVOLUÇÃO", "trocas", "comercial")
            elif msg_clean in ["reclamações", "reclamacoes", "4"]:
                return self._atendente("RECLAMAÇÃO", "reclamacao", "ouvidoria")
            elif msg_clean in ["sugestões", "sugestoes", "5"]:
                return self._atendente("SUGESTÃO", "sugestoes", "qualidade")
            elif msg_clean in ["voltar", "◀️ voltar", "6"]:
                return "menu_principal", {
                    "texto": "✨ *PEPER* - Assistente Virtual\n\nComo posso ajudar você hoje? 💙",
                    "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                }
            else:
                return "atendimento", {
                    "texto": "⚠️ *OPÇÃO INVÁLIDA!*\n\nPor favor, selecione uma opção válida: 💙",
                    "botoes": ["👨‍💼 ATENDENTE", "📦 MEU PEDIDO", "🔄 TROCAS", "⚠️ RECLAMAÇÕES", "💡 SUGESTÕES", "◀️ VOLTAR"]
                }
        
        # ============================================
        # INFORMAÇÕES
        # ============================================
        if estado_atual == "informacoes":
            if msg_clean in ["endereço", "endereco", "1"]:
                return "menu_principal", {
                    "texto": "📍 *ENDEREÇO YUP*\n\n📌 Av. Salime Nacif, 222 - Baixada\nManhuaçu - MG, 36902-051\n\n🗺️ https://maps.app.goo.gl/33EL5Z3HZkWJfkYVA\n\nClique no link! 💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["instagram", "2"]:
                return "menu_principal", {
                    "texto": "📷 *INSTAGRAM YUP*\n\n👉 https://www.instagram.com/papelaria.yup?igsh=dTVjZ3I4ZGRyY2Vn\n\n💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["site", "3"]:
                return "menu_principal", {
                    "texto": "🌐 *SITE YUP*\n\n👉 https://yupaper.com.br/\n\n💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["voltar", "◀️ voltar"]:
                return "menu_principal", {
                    "texto": "✨ *PEPER* - Assistente Virtual\n\nComo posso ajudar você hoje? 💙",
                    "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                }
            else:
                return "informacoes", {
                    "texto": "⚠️ *OPÇÃO INVÁLIDA!*\n\nPor favor, selecione uma informação válida: 💙",
                    "botoes": ["📍 ENDEREÇO", "📷 INSTAGRAM", "🌐 SITE", "◀️ VOLTAR"]
                }
        
        # ============================================
        # TRABALHE CONOSCO
        # ============================================
        if estado_atual == "trabalhe":
            if msg_clean in ["vervagas", "vagas", "1"]:
                return "menu_principal", {
                    "texto": "📢 *VAGAS DISPONÍVEIS*\n\n• Atendente (comércio) - 1 vaga\n• Caixa - 1 vaga\n\n📧 contato@grupoyup.com\n\n💙",
                    "botoes": ["📄 ENVIAR CURRÍCULO", "◀️ VOLTAR"]
                }
            elif "enviarcurriculo" in msg_clean or "curriculo" in msg_clean:
                return self._atendente("ENVIO DE CURRÍCULO", "curriculo", "rh")
            elif msg_clean in ["voltar", "◀️ voltar"]:
                return "menu_principal", {
                    "texto": "✨ *PEPER* - Assistente Virtual\n\nComo posso ajudar você hoje? 💙",
                    "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                }
            else:
                return "trabalhe", {
                    "texto": "⚠️ *OPÇÃO INVÁLIDA!*\n\nPor favor, selecione uma opção válida: 💙",
                    "botoes": ["📄 ENVIAR CURRÍCULO", "📢 VER VAGAS", "◀️ VOLTAR"]
                }
        
        # ============================================
        # ATENDIMENTO HUMANO
        # ============================================
        if sessao.get("status") == "humano":
            logger.info(f"⏸️ Cliente em atendimento humano - ignorando: {mensagem}")
            return "atendimento_humano", {"texto": None}
        
        # ============================================
        # DEFAULT
        # ============================================
        return "menu_principal", {
            "texto": "✨ *PEPER* - Assistente Virtual\n\nComo posso ajudar você hoje? 💙\n\n1️⃣ PROMOÇÕES\n2️⃣ SERVIÇOS\n3️⃣ ATENDIMENTO\n4️⃣ INFORMAÇÕES\n5️⃣ TRABALHE CONOSCO",
            "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
        }
    
    def _limpar_mensagem(self, mensagem: str) -> str:
        if not mensagem:
            return ""
        import unicodedata
        msg = mensagem.lower().strip()
        msg = unicodedata.normalize('NFKD', msg).encode('ASCII', 'ignore').decode('ASCII')
        msg = re.sub(r'[^a-z0-9]', '', msg)
        return msg
    
    def _atendente(self, servico: str, tipo: str, setor: str) -> Tuple[str, Dict]:
        return "atendimento_humano", {
            "texto": f"🔄 *{servico}*\n\n📌 Seu pedido foi registrado! Um atendente da Yup Papelaria entrará em contato em breve.\n\n⚠️ Digite CANCELAR para voltar ao menu principal. 💙",
            "botoes": ["❌ CANCELAR"],
            "criar_fila_humana": True,
            "tipo_fila": tipo,
            "status_humano": True,
            "setor": setor,
            "menu_anterior": tipo
        }
