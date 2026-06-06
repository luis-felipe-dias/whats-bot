from typing import Dict, Tuple, Optional
from app.services.fluxo_service import FluxoService

class StateMachine:
    def __init__(self):
        self.fluxo_service = FluxoService()
        self.states = {
            "menu_principal": self.handle_menu_principal,
            "promocoes": self.handle_promocoes,
            "impressoes": self.handle_impressoes,
            "atendimento": self.handle_atendimento,
            "informacoes": self.handle_informacoes,
            "trabalhe_conosco": self.handle_trabalhe_conosco,
            "aguardando_arquivo": self.handle_aguardando_arquivo,
            "aguardando_sugestao": self.handle_aguardando_sugestao,
            "cancelamento_confirmacao": self.handle_cancelamento_confirmacao,
            "avaliacao": self.handle_avaliacao
        }
    
    async def process_message(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        current_state = sessao.get("estado_atual", "menu_principal")
        
        if current_state in self.states:
            return await self.states[current_state](sessao, mensagem)
        
        return "menu_principal", {"texto": await self.fluxo_service.get_menu_principal()}
    
    async def handle_menu_principal(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        opcoes = {
            "🛍️ Promoções": "promocoes",
            "🖨️ Impressões": "impressoes",
            "🤝 Atendimento": "atendimento",
            "📍 Informações da Loja": "informacoes",
            "💼 Trabalhe Conosco": "trabalhe_conosco"
        }
        
        if mensagem in opcoes:
            return opcoes[mensagem], {"texto": await self.fluxo_service.get_menu_initial(opcoes[mensagem])}
        
        return "menu_principal", {"texto": await self.fluxo_service.get_menu_principal()}
    
    async def handle_promocoes(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        if mensagem == "🎁 Grupo VIP":
            return "menu_principal", {"texto": await self.fluxo_service.get_grupo_vip()}
        elif mensagem == "🔥 Ofertas do Dia":
            return "menu_principal", {"texto": await self.fluxo_service.get_ofertas_dia()}
        elif mensagem == "🌐 Site Yup":
            return "menu_principal", {"texto": await self.fluxo_service.get_site_yup()}
        elif mensagem in ["⬅️ Voltar", "🏠 Menu Principal"]:
            return "menu_principal", {"texto": await self.fluxo_service.get_menu_principal()}
        
        return "promocoes", {"texto": await self.fluxo_service.get_promocoes_menu()}
    
    async def handle_impressoes(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        if mensagem == "📎 Enviar Arquivo":
            return "aguardando_arquivo", {"texto": "Envie seu arquivo e informe:\n\n• Quantidade\n• Colorido ou P&B\n• Frente ou Frente e Verso\n• Observações\n\n💙"}
        elif mensagem in ["⚫ Preto e Branco", "🌈 Colorida", "📚 Encadernação", "📄 Plastificação"]:
            return "impressoes", {"texto": await self.fluxo_service.get_impressao_preco(mensagem)}
        elif mensagem in ["⬅️ Voltar", "🏠 Menu Principal"]:
            return "menu_principal", {"texto": await self.fluxo_service.get_menu_principal()}
        
        return "impressoes", {"texto": await self.fluxo_service.get_impressoes_menu()}
    
    async def handle_aguardando_arquivo(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        # Marcar que está aguardando arquivo
        return "menu_principal", {"texto": "Seu arquivo foi recebido com sucesso 💙\n\nUm atendente dará continuidade ao seu atendimento.", "criar_fila_humana": True, "tipo_fila": "impressao"}
    
    async def handle_atendimento(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        opcoes = {
            "👨‍💼 Atendimento Humano": "atendimento_humano",
            "📦 Pedido em Andamento": "pedido_andamento",
            "🔄 Trocas e Devoluções": "troca",
            "⚠️ Reclamações": "reclamacao",
            "💡 Sugestões": "sugestao"
        }
        
        if mensagem in opcoes:
            if opcoes[mensagem] == "atendimento_humano":
                return "menu_principal", {"texto": "Seu atendimento foi encaminhado para nossa equipe 💙", "criar_fila_humana": True, "tipo_fila": "atendimento"}
            elif opcoes[mensagem] in ["troca", "reclamacao"]:
                return "menu_principal", {"texto": "Sua solicitação será analisada por um atendente 💙", "criar_fila_humana": True, "tipo_fila": opcoes[mensagem]}
            elif opcoes[mensagem] == "sugestao":
                return "aguardando_sugestao", {"texto": "Sua opinião é muito importante para nós 💙\n\nDigite sua sugestão:"}
        
        if mensagem in ["⬅️ Voltar", "🏠 Menu Principal"]:
            return "menu_principal", {"texto": await self.fluxo_service.get_menu_principal()}
        
        return "atendimento", {"texto": await self.fluxo_service.get_atendimento_menu()}
    
    async def handle_aguardando_sugestao(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        return "menu_principal", {"texto": "Sugestão recebida com sucesso! 💙\n\nObrigado por nos ajudar a melhorar.", "salvar_sugestao": True}
    
    async def handle_informacoes(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        if mensagem == "📍 Endereço":
            return "menu_principal", {"texto": await self.fluxo_service.get_endereco()}
        elif mensagem == "🕒 Horários":
            return "menu_principal", {"texto": await self.fluxo_service.get_horarios()}
        elif mensagem == "📞 Telefones":
            return "menu_principal", {"texto": await self.fluxo_service.get_telefones()}
        elif mensagem == "📱 Redes Sociais":
            return "menu_principal", {"texto": await self.fluxo_service.get_redes_sociais()}
        elif mensagem == "🗺️ Como Chegar":
            return "menu_principal", {"texto": await self.fluxo_service.get_como_chegar()}
        elif mensagem in ["⬅️ Voltar", "🏠 Menu Principal"]:
            return "menu_principal", {"texto": await self.fluxo_service.get_menu_principal()}
        
        return "informacoes", {"texto": await self.fluxo_service.get_informacoes_menu()}
    
    async def handle_trabalhe_conosco(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        if mensagem == "📄 Enviar Currículo":
            return "menu_principal", {"texto": "Envie seu currículo em PDF 💙\n\nCurrículo recebido com sucesso 💙", "criar_fila_humana": True, "tipo_fila": "curriculo"}
        elif mensagem == "📢 Vagas Disponíveis":
            return "menu_principal", {"texto": await self.fluxo_service.get_vagas()}
        elif mensagem in ["⬅️ Voltar", "🏠 Menu Principal"]:
            return "menu_principal", {"texto": await self.fluxo_service.get_menu_principal()}
        
        return "trabalhe_conosco", {"texto": await self.fluxo_service.get_trabalhe_conosco_menu()}
    
    async def handle_cancelamento_confirmacao(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        if mensagem == "✅ Sim":
            return "menu_principal", {"texto": "Atendimento cancelado com sucesso 💙", "cancelar_atendimento": True}
        else:
            return "menu_principal", {"texto": await self.fluxo_service.get_menu_principal()}
    
    async def handle_avaliacao(self, sessao: dict, mensagem: str) -> Tuple[str, dict]:
        avaliacoes = {
            "⭐ 1 - Ruim": 1,
            "⭐⭐ 2 - Regular": 2,
            "⭐⭐⭐ 3 - Bom": 3,
            "⭐⭐⭐⭐ 4 - Muito Bom": 4,
            "⭐⭐⭐⭐⭐ 5 - Excelente": 5
        }
        
        if mensagem in avaliacoes:
            return "menu_principal", {"texto": "Obrigado pela sua avaliação 💙\n\nSua opinião nos ajuda a melhorar continuamente.", "salvar_avaliacao": avaliacoes[mensagem]}
        
        return "avaliacao", {"texto": "Por favor, avalie nosso atendimento:", "mostrar_avaliacao": True}