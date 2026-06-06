# test_zapi_correct.py
import http.client
import json

def test_zapi_with_correct_tokens():
    """
    Teste usando os dois tokens corretamente:
    - Token da instância na URL
    - Client-Token no header
    """
    
    # Tokens corretos (substitua pelos seus)
    instance_id = "3F43467A7F5BF175DDAF66DA177DAE5D"
    instance_token = "3049626451084430353F7A43"  # Token da instância
    client_token = "Fbce330834b5c44d79be6824d07ca611bS  "  # Client-Token (diferente!)
    
    print("🔍 TESTANDO Z-API COM TOKENS CORRETOS")
    print("="*50)
    print(f"Instance ID: {instance_id}")
    print(f"Instance Token: {instance_token[:10]}...")
    print(f"Client Token: {client_token[:10]}...")
    print("="*50)
    
    # Testar envio de mensagem
    conn = http.client.HTTPSConnection("api.z-api.io")
    
    payload = json.dumps({
        "phone": "5528999857576",
        "message": "Teste YUP Platform - Peper 💙\n\nTokens configurados corretamente!",
        "delayMessage": 15
    })
    
    headers = {
        'Client-Token': client_token,  # Header com Client-Token
        'Content-Type': 'application/json'
    }
    
    # URL com Token da instância
    url = f"/instances/{instance_id}/token/{instance_token}/send-text"
    
    print(f"\n📡 Enviando requisição...")
    conn.request("POST", url, payload, headers)
    res = conn.getresponse()
    data = res.read()
    
    print(f"\nStatus Code: {res.status}")
    print(f"Resposta: {data.decode('utf-8')}")
    
    if res.status == 200:
        print("\n✅ SUCESSO! Mensagem enviada com os dois tokens corretos!")
        return True
    else:
        print("\n❌ ERRO! Verifique os tokens:")
        print("1. Token da instância (URL) está correto?")
        print("2. Client-Token (Header) está correto?")
        print("3. A instância está conectada ao WhatsApp?")
        return False

def get_client_token_from_panel():
    """
    Instruções para encontrar o Client-Token no painel da Z-API
    """
    print("\n" + "="*50)
    print("🔑 ONDE ENCONTRAR O CLIENT-TOKEN")
    print("="*50)
    print("\nNo painel da Z-API:")
    print("1. Acesse https://platform.z-api.io/")
    print("2. Vá em 'Configurações da Conta' ou 'Account Settings'")
    print("3. Procure por 'Client Token' ou 'API Token'")
    print("4. Pode estar em 'Credenciais da API'")
    print("\n⚠️ O Client-Token é DIFERENTE do Token da Instância!")
    print("   - Token da Instância: Fica na página da instância")
    print("   - Client-Token: Fica nas configurações da conta/usuário")
    print("="*50)

if __name__ == "__main__":
    # Mostrar onde encontrar o Client-Token
    get_client_token_from_panel()
    
    # Testar com tokens corretos
    input("\nPressione ENTER após configurar o Client-Token...")
    test_zapi_with_correct_tokens()