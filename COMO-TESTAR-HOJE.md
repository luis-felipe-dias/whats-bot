# Peper IA — MVP · como testar hoje

**Resposta curta à sua pergunta:** sim, dá para testar tudo no número de teste da Meta antes de encostar no 0424. É exatamente para isso que ele existe.

---

## 1. O que o número de teste permite (e o que não)

| | |
|---|---|
| Receber mensagem | ✅ dos destinatários cadastrados |
| Responder | ✅ texto, botões, lista, mídia |
| Destinatários | ⚠️ **até 5**, cada um confirma por código no próprio WhatsApp |
| Custo | ✅ grátis, não consome conversas |
| Token | ⚠️ o da tela é **temporário (24h)** |

Então o teste é completo em comportamento. As duas limitações reais: cinco números, e o token que vence amanhã. Para hoje, o temporário resolve. Se vai testar a semana toda, gere um token de **Usuário do Sistema** (Configurações do Negócio › Usuários › Usuários do sistema) — esse não expira.

**Cadastrar seu celular:** App Peper V1 › WhatsApp › Configuração da API › em "Para", botão **Gerenciar** › adicionar o número › digitar o código que chega no WhatsApp.

## 2. O bloqueio de verdade: HTTPS

Sem URL pública em HTTPS a Meta não entrega webhook nenhum — nem no número de teste. E o backend hoje roda local.

Solução para hoje, em dois minutos, sem mexer em DNS:

```bash
# instala uma vez
winget install --id Cloudflare.cloudflared

# com o bot rodando na 8080:
cloudflared tunnel --url http://localhost:8080
```

Sai uma URL tipo `https://algo-aleatorio.trycloudflare.com`. Essa URL vai em **duas** partes:

1. `BACKEND_PUBLIC_URL` no `.env`
2. App › WhatsApp › Configuração › **Webhook › Editar**:
   - URL de callback: `https://algo-aleatorio.trycloudflare.com/bot/yup/webhook-meta`
   - Verificar token: o mesmo `META_VERIFY_TOKEN` do `.env`
   - Depois clicar em **Gerenciar** e marcar o campo **`messages`** — sem isso a URL valida e mesmo assim não chega mensagem. É o erro mais comum.

O túnel grátis muda de endereço a cada reinício. Para o 0424 em diante, subdomínio de verdade com certificado.

## 3. Arquivos

| Arquivo | Onde vai |
|---|---|
| `bot/core/config.py` | `whats-bot/app/core/config.py` (substitui) |
| `bot/core/openai_client.py` | `whats-bot/app/core/` (novo) |
| `bot/services/ia_catalogo.py` | `whats-bot/app/services/` (novo) |
| `bot/services/ia_handler.py` | `whats-bot/app/services/` (novo) |
| `bot/webhook.py` | `whats-bot/app/api/webhook.py` (substitui) |
| `bot/scripts/retencao_7_dias.py` | `whats-bot/scripts/` (novo) |
| `ENV-whats-bot.txt` | renomear para `whats-bot/.env` |
| `backend/tempo_real_routes.py` | `meu_projeto/src/api/routes/` (novo) |

No `meu_projeto`, registrar a rota nova:

```python
# src/api/routes/__init__.py — acrescentar
from .tempo_real_routes import router as tempo_real_router

# main.py — acrescentar
from src.api.routes import tempo_real_router
app.include_router(tempo_real_router)
```

Dependência: nenhuma nova. Tudo em `httpx`, que já está no projeto.

## 4. Ordem de subida

```bash
# 1. backend de estoque (dá o catálogo ao bot)
cd "melhorias]\meu_projeto" && python main.py           # :8000

# 2. bot
cd "melhorias]\whats-bot" && uvicorn app.main:app --port 8080

# 3. túnel
cloudflared tunnel --url http://localhost:8080
```

Confira antes de mandar mensagem:

```bash
curl http://localhost:8000/estoque/produtos/buscar?termo=caderno
curl http://localhost:8080/health
```

## 5. Roteiro de teste (nessa ordem)

1. `oi` → deve responder como atendente, não como menu
2. `vcs tem caderno?` → busca, e deve **pedir para você especificar** se achar muita coisa
3. `quanto custa o 26705?` → tem que **consultar** antes de falar valor
4. **manda um áudio** perguntando preço → transcreve e responde
5. **manda uma foto** → pergunta "currículo ou impressão?" com dois botões
6. `quero falar com uma pessoa` → transfere e cria ticket na fila

No log, o que confirma que está certo:

```
IA respondeu — entrada=820 saida=64 tokens
```

E se aparecer isto, a trava funcionou — é bom sinal, não erro:

```
IA tentou falar preço sem consultar o ERP. Resposta bloqueada.
```

## 6. Decisões que eu tomei e você pode querer mudar

**A cota do Olist eu não precisei perguntar — está no seu código.** `TINY_V3_LIMITE_FILIAL=54`, `MATRIZ=27`. Ou seja: filial em Impulsione (60/min), matriz em Construa (30/min), com margem nos dois. O balcão roda na conta da **filial**, então **o teto do bot é 54/min, dividido com o sync da reposição.** O `IA_MAX_CONSULTAS_ERP=3` por conversa cabe com folga — pode subir para 5 se a IA ficar pedindo para o cliente repetir.

**Busca no espelho, confirmação em tempo real.** Você pediu tempo real em tudo; com 54/min divididos com o sync, isso cai no primeiro sábado de movimento e leva o sistema da Daiane junto. Busca textual não gasta cota nenhuma e é instantânea; a chamada ao Olist acontece só quando a conversa chega no valor. Com 54/min isso fica confortável — com busca em tempo real, não ficaria.

**A trava de preço é no código, não no prompt.** Se a resposta cita `R$` e nenhuma consulta foi feita, a mensagem não sai — o modelo é obrigado a consultar ou reescrever. Prompt sozinho não segura isso.

**Retenção de 7 dias ficou FORA do código**, num script separado. O TTL é global na coleção: ligar 7 dias apaga também a conversa dos clientes reais do 8882. Leia o aviso no topo do arquivo antes de rodar.

**Foto não passa pela IA.** "Currículo ou impressão?" é sempre a mesma pergunta — é regra. Gastar token e arriscar alucinação nisso não se paga.

## 7. O que ainda falta para o 01/12

| | |
|---|---|
| HTTPS de verdade (subdomínio + certificado) | túnel não serve para o 0424 |
| Token de Usuário do Sistema | o temporário vence em 24h |
| Verificação da empresa na Meta | está **REJEITADA** — sem ela, limite baixo de conversas |
| Painel publicado | o `server.js` nunca subiu para o VPS |
| Decidir a retenção definitiva | 7 dias no teste, 90 antes de 10/12 |
