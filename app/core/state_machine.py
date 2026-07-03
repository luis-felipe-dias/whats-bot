# app/core/state_machine.py
from typing import Tuple, Dict
import logging
import re

logger = logging.getLogger(__name__)

class StateMachine:
    async def process_message(self, sessao: dict, mensagem: str) -> Tuple[str, Dict]:
        
        estado_atual = sessao.get("estado_atual", "menu_principal")
        msg_clean = self._limpar_mensagem(mensagem)
        
        logger.info(f"Estado: {estado_atual} | Msg: {mensagem} | Clean: {msg_clean}")
        
        # ============================================
        # COMANDO GLOBAL - CANCELAR
        # ============================================
        if "cancelar" in msg_clean or "cancel" in msg_clean:
            return "menu_principal", {
                "texto": "✅ Atendimento cancelado! Volte ao menu principal. 💙",
                "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
            }
        
        # ============================================
        # SAUDAÇÃO INICIAL
        # ============================================
        if msg_clean in ["olá", "ola", "oi", "bomdia", "boatarde", "boanoite", "tudobem", "inicio", "menu", "start"]:
            return "menu_principal", {
                "texto": "✨ *PEPER* - Assistente Virtual da Yup Papelaria ✨\n\nOlá! Como posso ajudar você hoje? 💙",
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
                    "texto": "🎁 *GRUPOS VIP YUP*\n\nParticipe dos nossos grupos VIP e receba ofertas exclusivas!\n\n📱 *Grupo 1:*\nhttps://chat.whatsapp.com/Cbh5Whh7pmU7jqMciI5bbs\n\n📱 *Grupo 2:*\nhttps://chat.whatsapp.com/I2ZMLyHoGM13hPHpWNcCjD\n\n🔗 Clique nos links acima para entrar! 💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["promoções", "promocoes", "ofertas", "2"]:
                return "menu_principal", {
                    "texto": "🔥 *PROMOÇÕES DA SEMANA* 🔥\n\nConfira nossas ofertas especiais:\n\n👉 https://yupaper.com.br/categoria/promocoes_inverno/\n\nAproveite os descontos! 💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["site", "siteyup", "3"]:
                return "menu_principal", {
                    "texto": "🌐 *LOJA ONLINE YUP*\n\nAcesse nosso site e confira o catálogo completo:\n\n👉 https://yupaper.com.br/\n\n💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["voltar", "voltar"]:
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
                return self._atendente("IMPRESSÃO", "servico")
            elif msg_clean in ["encadernação", "encadernacao", "2"]:
                return self._atendente("ENCADERNAÇÃO", "servico")
            elif msg_clean in ["plastificação", "plastificacao", "3"]:
                return self._atendente("PLASTIFICAÇÃO", "servico")
            elif msg_clean in ["voltar", "voltar"]:
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
                return self._atendente("ATENDIMENTO HUMANO", "atendimento")
            elif msg_clean in ["meupedido", "pedido", "2"]:
                return self._atendente("CONSULTA DE PEDIDO", "pedido")
            elif msg_clean in ["trocas", "devoluções", "devolucoes", "3"]:
                return self._atendente("TROCA/DEVOLUÇÃO", "troca")
            elif msg_clean in ["reclamações", "reclamacoes", "4"]:
                return self._atendente("RECLAMAÇÃO", "reclamacao")
            elif msg_clean in ["sugestões", "sugestoes", "5"]:
                return "aguardando_sugestao", {
                    "texto": "💡 *SUGESTÕES*\n\nDigite sua sugestão abaixo. Agradecemos sua opinião! 💙\n\nDigite CANCELAR para voltar.",
                    "botoes": ["❌ CANCELAR"]
                }
            elif msg_clean in ["voltar", "voltar", "6"]:
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
                    "texto": "📍 *ENDEREÇO YUP*\n\n📌 Av. Salime Nacif, 222 - Baixada\nManhuaçu - MG, 36902-051\n\n🗺️ *Google Maps:*\nhttps://maps.app.goo.gl/33EL5Z3HZkWJfkYVA\n\nClique no link para abrir o mapa! 💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["instagram", "2"]:
                return "menu_principal", {
                    "texto": "📷 *INSTAGRAM YUP*\n\nSiga-nos e fique por dentro das novidades!\n\n👉 https://www.instagram.com/papelaria.yup?igsh=dTVjZ3I4ZGRyY2Vn\n\n💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["site", "3"]:
                return "menu_principal", {
                    "texto": "🌐 *SITE YUP*\n\nAcesse nossa loja online:\n\n👉 https://yupaper.com.br/\n\n💙",
                    "botoes": ["◀️ VOLTAR"]
                }
            elif msg_clean in ["voltar", "voltar"]:
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
        # TRABALHE CONOSCO - CORRIGIDO
        # ============================================
        if estado_atual == "trabalhe":
            if msg_clean in ["vervagas", "vagas", "1"]:
                return "menu_principal", {
                    "texto": "📢 *VAGAS DISPONÍVEIS - YUP PAPELARIA*\n\n👥 *OPORTUNIDADES:*\n\n• Atendente (comércio) - 1 vaga\n• Caixa - 1 vaga\n\n📧 Envie seu currículo em PDF para:\ncontato@grupoyup.com\n\n💙 Venha fazer parte do nosso time!",
                    "botoes": ["📄 ENVIAR CURRÍCULO", "◀️ VOLTAR"]
                }
            elif "enviarcurriculo" in msg_clean or "curriculo" in msg_clean:
                return self._atendente("ENVIO DE CURRÍCULO", "curriculo")
            elif msg_clean in ["voltar", "voltar"]:
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
        # SUGESTÕES
        # ============================================
        if estado_atual == "aguardando_sugestao":
            if "cancelar" in msg_clean or "cancel" in msg_clean:
                return "menu_principal", {
                    "texto": "✨ *PEPER* - Assistente Virtual\n\nComo posso ajudar você hoje? 💙",
                    "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                }
            else:
                return "menu_principal", {
                    "texto": f"✅ *SUGESTÃO RECEBIDA!*\n\n\"{mensagem}\"\n\nMuito obrigado! Sua opinião nos ajuda a melhorar. 💙\n\n✨ Como posso ajudar você hoje?",
                    "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                }
        
        # ============================================
        # ATENDIMENTO HUMANO - Ignora mensagens
        # ============================================
        if sessao.get("status") == "humano":
            logger.info(f"⏸️ Cliente em atendimento humano - ignorando: {mensagem}")
            return "atendimento_humano", {"texto": None}
        
        # ============================================
        # DEFAULT
        # ============================================
        return "menu_principal", {
            "texto": "✨ *PEPER* - Assistente Virtual\n\nComo posso ajudar você hoje? 💙\n\n1️⃣ PROMOÇÕES\n2️⃣ SERVIÇOS\n3️⃣ ATENDIMENTO\n4️⃣ INFORMAÇÕES\n5️⃣ TRABALHE CONOSCO\n\nDigite o número ou clique no botão desejado:",
            "botoes": ["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
        }
    
    def _limpar_mensagem(self, mensagem: str) -> str:
        if not mensagem:
            return ""
        import unicodedata
        msg = mensagem.lower().strip()
        msg = unicodedata.normalize('NFKD', msg).encode('ASCII', 'ignore').decode('ASCII')
        # Remove caracteres especiais, mantém letras e números
        msg = re.sub(r'[^a-z0-9]', '', msg)
        return msg
    
    def _atendente(self, servico: str, tipo: str) -> Tuple[str, Dict]:
        return "atendimento_humano", {
            "texto": f"🔄 *{servico}*\n\n📌 Seu pedido foi registrado! Um atendente da Yup Papelaria entrará em contato em breve.\n\n⚠️ Digite CANCELAR para voltar ao menu principal. 💙",
            "botoes": ["❌ CANCELAR"],
            "criar_fila_humana": True,
            "tipo_fila": tipo,
            "status_humano": True
        }
