# app/core/state_machine.py
from typing import Tuple, Dict

class StateMachine:
    async def process_message(self, sessao: dict, mensagem: str) -> Tuple[str, Dict]:
        """Processa a mensagem e retorna próximo estado e resposta"""
        
        # Menu principal
        if mensagem == "🛍️ Promoções":
            return "promocoes", {"texto": "Confira nossos canais de promoções 💙\n\n🎁 Grupo VIP\n🔥 Ofertas do Dia\n🌐 Site Yup\n\n⬅️ Voltar\n🏠 Menu Principal"}
        
        elif mensagem == "🖨️ Impressões":
            return "impressoes", {"texto": "Selecione o serviço desejado 💙\n\n⚫ Preto e Branco\n🌈 Colorida\n📚 Encadernação\n📄 Plastificação\n📎 Enviar Arquivo\n\n⬅️ Voltar\n🏠 Menu Principal"}
        
        elif mensagem == "🤝 Atendimento":
            return "atendimento", {"texto": "Como podemos ajudar? 💙\n\n👨‍💼 Atendimento Humano\n📦 Pedido em Andamento\n🔄 Trocas e Devoluções\n⚠️ Reclamações\n💡 Sugestões\n\n⬅️ Voltar\n🏠 Menu Principal"}
        
        elif mensagem == "📍 Informações da Loja":
            return "informacoes", {"texto": "Selecione a informação desejada 💙\n\n📍 Endereço\n🕒 Horários\n📞 Telefones\n📱 Redes Sociais\n🗺️ Como Chegar\n\n⬅️ Voltar\n🏠 Menu Principal"}
        
        elif mensagem == "💼 Trabalhe Conosco":
            return "trabalhe_conosco", {"texto": "Escolha uma opção 💙\n\n📄 Enviar Currículo\n📢 Vagas Disponíveis\n\n⬅️ Voltar\n🏠 Menu Principal"}
        
        elif mensagem == "🏠 Menu Principal":
            return "menu_principal", {"texto": "Olá! 💙\n\nSou a Peper, assistente virtual da Yup Papelaria.\n\nComo posso ajudar você hoje?\n\n🛍️ Promoções\n🖨️ Impressões\n🤝 Atendimento\n📍 Informações da Loja\n💼 Trabalhe Conosco\n\n⬅️ Voltar\n🏠 Menu Principal"}
        
        # Promoções
        elif mensagem == "🎁 Grupo VIP":
            return "menu_principal", {"texto": "Participe do nosso grupo VIP e receba ofertas exclusivas 💙\n\n🔗 Entrar no Grupo\n\n🏠 Menu Principal"}
        
        elif mensagem == "🔥 Ofertas do Dia":
            return "menu_principal", {"texto": "Confira nossas ofertas disponíveis hoje 💙\n\n🔥 Oferta 1: ...\n\n🏠 Menu Principal"}
        
        elif mensagem == "🌐 Site Yup":
            return "menu_principal", {"texto": "Acesse nossa loja online 💙\n\n🌐 Acessar Site\n\n🏠 Menu Principal"}
        
        # Atendimento humano
        elif mensagem == "👨‍💼 Atendimento Humano":
            return "menu_principal", {"texto": "Seu atendimento foi encaminhado para nossa equipe 💙\n\n🏠 Menu Principal", "criar_fila_humana": True, "tipo_fila": "atendimento"}
        
        elif mensagem == "📎 Enviar Arquivo":
            return "menu_principal", {"texto": "Seu arquivo foi recebido com sucesso 💙\n\nUm atendente dará continuidade ao seu atendimento.\n\n🏠 Menu Principal", "criar_fila_humana": True, "tipo_fila": "impressao"}
        
        # Voltar
        elif mensagem == "⬅️ Voltar":
            return "menu_principal", {"texto": "Olá! 💙\n\nSou a Peper, assistente virtual da Yup Papelaria.\n\nComo posso ajudar você hoje?\n\n🛍️ Promoções\n🖨️ Impressões\n🤝 Atendimento\n📍 Informações da Loja\n💼 Trabalhe Conosco\n\n⬅️ Voltar\n🏠 Menu Principal"}
        
        # Default - menu principal
        return "menu_principal", {"texto": "Olá! 💙\n\nSou a Peper, assistente virtual da Yup Papelaria.\n\nComo posso ajudar você hoje?\n\n🛍️ Promoções\n🖨️ Impressões\n🤝 Atendimento\n📍 Informações da Loja\n💼 Trabalhe Conosco\n\n⬅️ Voltar\n🏠 Menu Principal"}