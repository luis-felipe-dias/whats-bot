class FluxoService:
    async def get_menu_principal(self) -> str:
        return """Olá! 💙

Sou a Peper, assistente virtual da Yup Papelaria.

Como posso ajudar você hoje?

🛍️ Promoções
🖨️ Impressões
🤝 Atendimento
📍 Informações da Loja
💼 Trabalhe Conosco

⬅️ Voltar
🏠 Menu Principal"""
    
    async def get_promocoes_menu(self) -> str:
        return """Confira nossos canais de promoções 💙

🎁 Grupo VIP
🔥 Ofertas do Dia
🌐 Site Yup

⬅️ Voltar
🏠 Menu Principal"""
    
    async def get_impressoes_menu(self) -> str:
        return """Selecione o serviço desejado 💙

⚫ Preto e Branco
🌈 Colorida
📚 Encadernação
📄 Plastificação
📎 Enviar Arquivo

⬅️ Voltar
🏠 Menu Principal"""
    
    async def get_atendimento_menu(self) -> str:
        return """Como podemos ajudar? 💙

👨‍💼 Atendimento Humano
📦 Pedido em Andamento
🔄 Trocas e Devoluções
⚠️ Reclamações
💡 Sugestões

⬅️ Voltar
🏠 Menu Principal"""
    
    async def get_informacoes_menu(self) -> str:
        return """Selecione a informação desejada 💙

📍 Endereço
🕒 Horários
📞 Telefones
📱 Redes Sociais
🗺️ Como Chegar

⬅️ Voltar
🏠 Menu Principal"""
    
    async def get_trabalhe_conosco_menu(self) -> str:
        return """Escolha uma opção 💙

📄 Enviar Currículo
📢 Vagas Disponíveis

⬅️ Voltar
🏠 Menu Principal"""
    
    async def get_grupo_vip(self) -> str:
        return "Participe do nosso grupo VIP e receba ofertas exclusivas 💙\n\n🔗 Entrar no Grupo"
    
    async def get_ofertas_dia(self) -> str:
        return "Confira nossas ofertas disponíveis hoje 💙\n\n🔥 Oferta 1: ...\n🔥 Oferta 2: ..."
    
    async def get_site_yup(self) -> str:
        return "Acesse nossa loja online 💙\n\n🌐 Acessar Site"
    
    async def get_impressao_preco(self, tipo: str) -> str:
        return f"Serviço de {tipo} - Consulte nossos preços 💙\n\nValores sob consulta."
    
    async def get_endereco(self) -> str:
        return "📍 Rua Exemplo, 123 - Centro\nCEP: 00000-000\n\n🗺️ Como Chegar"
    
    async def get_horarios(self) -> str:
        return "🕒 Segunda a Sexta: 08h às 18h\n🕒 Sábado: 09h às 13h\n🕒 Domingo: Fechado"
    
    async def get_telefones(self) -> str:
        return "📞 (11) 99999-9999\n📱 (11) 98888-8888"
    
    async def get_redes_sociais(self) -> str:
        return "📱 Instagram: @yuppapelaria\n📱 Facebook: /yuppapelaria"
    
    async def get_como_chegar(self) -> str:
        return "🗺️ Como Chegar: Estamos localizados no centro da cidade, próximo à praça principal."
    
    async def get_vagas(self) -> str:
        return """📢 Vagas Disponíveis:

• Atendente
• Impressor
• Auxiliar Administrativo

Envie seu currículo para rh@yuppapelaria.com.br"""