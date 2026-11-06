# Bot Peper — parecer sobre o código REAL

**Data:** 06/11/2026
**Base:** `melhorias]\whats-bot` (o projeto com `.git`), estado de ~23/09/2026
**Substitui** o parecer de 16/10, que foi feito em cima de um snapshot de 08/09 e está desatualizado.

---

## 0. A pergunta que precisa de resposta hoje

**`2.25.147.117:8081` está acessível pela internet ou só pela rede da loja?**

Se for público, o item 1 abaixo deixa de ser "arrumar essa semana" e vira hoje.

---

## 1. URGENTE — a API não tem autenticação nenhuma

Nenhuma rota tem `Depends`, não há middleware de auth, não existe token em lugar nenhum. Confirmado por varredura em todos os routers.

Quem alcançar a porta 8081 consegue:

| Ação | Rota | Consequência |
|---|---|---|
| Ler toda conversa de todo cliente | `GET /human/sessoes/{id}/mensagens` | exposição LGPD |
| Baixar os anexos dos clientes | mesma rota, campo `file_url` | **inclui os currículos** do fluxo TRABALHE CONOSCO |
| Pegar a base de contatos | `GET /bot/yup/contatos` | 500 por chamada, com nome e telefone — é o seu pré-CRM inteiro |
| Pegar telefone de terceiros | campo `remetente_telefone` | números de **gente dentro dos grupos**, que nunca falou com a loja |
| **Disparar WhatsApp pelo número da loja** | `POST /human/sessoes/iniciar` | telefone livre no corpo, sem allowlist, sem limite. **Em laço, é spam em massa saindo do seu número** |
| Reiniciar o worker | `POST /admin/worker/restart` | — |

`/docs` e `/openapi.json` estão abertos: qualquer um abre o formulário pronto para disparar.

O CORS é `allow_origins=["*"]` com `allow_credentials=True` — mas isso é detalhe perto do resto: sem auth, nem precisa de navegador, um `curl` basta.

**Mínimo aceitável:** API key fixa num header + allowlist de IP na rede, e `/docs` fechado. Leva uma hora.

---

## 2. Perda de dados — três mecanismos ativos

### 2.1 A limpeza apaga mensagens de conversa VIVA

`limpeza_worker.py:118-136`, a cada 30 minutos:

1. carrega todos os `_id` de sessões em memória (`:120`)
2. apaga de `mensagens`, `fila_envio`, `fila_humana` e `eventos` tudo cujo `sessao_id` **não esteja nessa lista** (`:126-129`)

Qualquer sessão criada **entre** a linha 120 e a 126 não está na lista — então as mensagens dela são "órfãs" por definição e somem. No pico nascem sessões continuamente. O cliente aparece no painel sem nenhuma mensagem.

### 2.2 O histórico de atendimento dura 3 horas

`limpeza_worker.py:96-116` é `delete_many` puro. Não arquiva, não tem TTL, não tem cópia. Três gatilhos, todos com corte de **3 horas** sem interação.

O pior: atendente responde às 10h, cliente não volta → **às 13h o atendimento inteiro deixou de existir.** Some a conversa, o ticket, o evento e a sessão.

Com 5 atendentes no mesmo número, **nenhum deles consegue conferir o que o outro combinou com o cliente depois de 3 horas.** Preço cotado, prazo prometido, troca autorizada — tudo evapora.

E isso é **bloqueador para a campanha de disparo**: não existe campo de consentimento em lugar nenhum, e a coleção `eventos` (o que mais perto chegaria de um log de tratamento) é justamente uma das apagadas. Sem isso não há como provar base legal nem registrar opt-out.

### 2.3 Mensagem de cliente perdida em silêncio

`database.py:47` cria índice único em `contatos.telefone` **sem `sparse`**. Contato criado só com `chat_lid` grava `telefone: None`. O segundo contato sem telefone colide em `null` → exceção → `webhook.py:365` só loga.

O webhook já respondeu 200 para a Z-API, então **não há reentrega. A mensagem do cliente simplesmente não existe.**

(O mesmo arquivo faz certo na linha 56, com `message_id` unique **e** sparse.)

---

## 3. O que o cliente vive de errado

### 3.1 Áudio e foto recebem "OPÇÃO INVÁLIDA"

O webhook converte mídia em texto sintético (`"🎤 Áudio recebido"`, `webhook.py:113`) e manda esse texto para a máquina de estados, que limpa para `"audiorecebido"` e não casa com nada → cai no `else` → **"⚠️ OPÇÃO INVÁLIDA!"**

Áudio é o hábito dominante do WhatsApp brasileiro. Hoje o bot responde que a pessoa errou.

Pior: o próprio bot pede currículo em PDF (`state_machine.py:84`). Arquivo chamado `CV_Joao.pdf` vira `"documentocvjoaopdf"`, o teste `"curriculo" in msg_clean` falha, e o candidato leva "OPÇÃO INVÁLIDA".

### 3.2 Figurinha e reação somem sem deixar rastro

Não tratados no webhook: sticker, reação, enquete, localização ao vivo, mensagem editada. Para todos, o webhook devolve `{"status":"ignored"}` **sem logar nada**.

Cliente manda figurinha de "oi" — abertura comum — e **não acontece nada.** Nem resposta, nem sessão, nem linha no histórico. Os 5 atendentes não ficam sabendo que alguém chamou. O cliente conclui que o número está morto.

### 3.3 VER VAGAS → ENVIAR CURRÍCULO → "OPÇÃO INVÁLIDA"

`state_machine.py:203-207`: VER VAGAS devolve o estado `menu_principal` mas mostra o botão ENVIAR CURRÍCULO. No menu principal esse botão não existe → `else` → opção inválida.

**O caminho de RH quebra em dois cliques.**

### 3.4 O VOLTAR do menu ATENDIMENTO nunca chega no celular

`whatsapp_api.py:87` ainda tem `botoes[:5]`. O menu ATENDIMENTO tem **6** opções (`state_machine.py:75`) — o 6º é o VOLTAR, cortado em silêncio, sem log.

O menu mais usado do bot é uma rua sem retorno visual.

### 3.5 O VOLTAR das folhas pula um nível

Todas as folhas devolvem `"menu_principal"` em vez do submenu de origem. Cliente em INFORMAÇÕES → ENDEREÇO → VOLTAR cai no menu principal, não em INFORMAÇÕES. Em 3 das 5 ramificações o VOLTAR mente sobre para onde leva.

O dado para fazer certo já é gravado (`menu_anterior`, `webhook.py:322-328`) — a máquina de estados só nunca lê.

### 3.6 "Quanto custa X?" não tem resposta

Não existe nenhuma referência a Olist, Tiny, preço ou estoque em todo o backend. Sua regra de "preço nunca inventado pelo bot" está cumprida **por ausência** — o bot não tem como consultar nada. O efeito é que a pergunta nº1 do cliente cai em OPÇÃO INVÁLIDA.

### 3.7 Link de promoção desatualizado no ar

`state_machine.py:104` aponta fixo para `/categoria/promocoes_inverno/`. Em novembro, com Black Friday rodando, o botão 🔥 PROMOÇÕES manda o cliente para promoções de inverno. Está hardcoded — mudar exige deploy.

---

## 4. Os 5 atendentes atropelam uns aos outros

**Não existe dono de sessão.** O campo `atendente_id` existe no banco, mas os 4 pontos que chamam a função de gravação não passam o argumento — fica sempre `None`.

Consequências confirmadas:

- **Duas pessoas respondem a mesma conversa ao mesmo tempo** e o cliente recebe as duas. Sem trava, sem versão, `last write wins`.
- **O painel não mostra quem respondeu.** O nome do atendente é gravado na mensagem, mas o histórico devolvido ao painel não inclui esse campo. Dado existe, só não sai.
- **Duas transferências simultâneas** criam dois tickets e mandam duas mensagens de "seu atendimento foi transferido", para setores diferentes.
- **Duas mensagens do mesmo cliente chegando juntas criam duas sessões ativas** — não há índice único. O cliente aparece duas vezes no painel, e dois atendentes pegam cada uma.

Ainda: **o ticket criado pelo bot nasce sem `aguardando_desde`.** A função que gravava esse campo ficou órfã quando a ativação virou código inline no webhook. Resultado: **todo ticket vindo do bot aparece no painel sem tempo de espera** — justamente a informação que decide quem atender primeiro na fila da Black Friday.

---

## 5. Desempenho — o painel é o gargalo, não o bot

`GET /human/sessoes` faz **um `find_one` por sessão** dentro do laço: até 151 idas e voltas ao Atlas por chamada.

Com 5 atendentes e polling de 5s:

| Rota | Carga |
|---|---|
| `/human/sessoes` | ~9.060 operações Mongo/min |
| `/mensagens` | histórico **inteiro** a cada 5s, por atendente |
| `/estatisticas` | 7 counts por chamada |
| **Total realista** | **10.000 a 12.000 operações por minuto, para 5 pessoas olhando uma tela** |

**Mas o que quebra primeiro não é performance, é correção:** a listagem corta em 150 sessões e **a busca filtra depois do corte, em Python**. Com 100 clientes/hora, 150 sessões são ~1h30 de movimento. A partir daí conversas reais somem do painel e a busca não acha.

Faltam índices em pelo menos 6 consultas quentes, incluindo a de mensagens não lidas, que roda por sessão a cada poll.

---

## 6. A fila de envio é código morto — e isso importa

**Nada no projeto insere em `fila_envio`.** O worker roda desde o boot fazendo polling a cada 0,5s numa coleção vazia.

A função chamada `enfileirar_resposta` não enfileira: chama a Z-API direto, no mesmo request. As configurações `whatsapp_delay_min`/`whatsapp_delay_max` existem no config e **não são lidas em lugar nenhum**.

**Logo: não existe controle de ritmo de disparo.** Hoje o ritmo é o do cliente, então o número aguenta. **No dia em que alguém ligar a campanha, não há freio nenhum.**

E se ligar a fila sem consertar o worker, o perfil de envio é: lotes de 20 em paralelo com pausa de 0,5s ≈ **40 mensagens por segundo em rajada**. Para 3.000 msg/mês isso é bloqueio garantido do número.

O worker também está quebrado por conta própria: busca o contato passando string onde o banco guarda ObjectId — nunca casa, tudo viraria erro.

---

## 7. Correção do que eu te disse errado em 16/10

| O que eu disse | Realidade no código atual |
|---|---|
| `human.py` lê `sessao.get("group_id")` enquanto grava `identificador` | **Falso.** `group_id` não existe em lugar nenhum do projeto. Era do snapshot antigo ou leitura minha errada. O problema real é outro: `identificador` guarda o LID do WhatsApp e é devolvido como se fosse telefone em duas rotas — o atendente vê `25812345678@lid` onde deveria ver o número |
| `cancelar_ticket()` existe e nunca é chamado | **Confirmado**, continua morto |
| `botoes[:5]` corta o VOLTAR | **Confirmado**, continua lá |
| VOLTAR pula um nível | **Confirmado** |
| VER VAGAS → OPÇÃO INVÁLIDA | **Confirmado** |
| sticker não tratado | **Confirmado**, e são mais tipos que eu não tinha listado |
| limpeza apaga em vez de arquivar | **Confirmado**, e é pior: também apaga conversa viva |

---

## 8. Ordem que eu atacaria

**Hoje, se a 8081 for pública:**
1. Fechar a porta / API key + allowlist de IP. `/docs` off.

**Esta semana:**
2. Desligar `_remover_dados_orfãos` — está apagando conversa viva
3. `contatos.telefone` → `sparse`, e tratar a colisão com re-busca em vez de `raise`
4. Trocar `delete` por arquivamento na limpeza e subir o corte de 3h
5. Mídia e tipos não tratados: responder "não entendi, quer falar com atendente?" em vez de OPÇÃO INVÁLIDA ou silêncio

**Antes de 15/12:**
6. Cortar o menu ATENDIMENTO para 5 opções (ou voltar a usar mensagem de lista)
7. Consertar VER VAGAS e o VOLTAR das folhas (o `menu_anterior` já existe)
8. Gravar `aguardando_desde` no ticket do bot — é uma linha
9. Dono de sessão com `find_one_and_update` + índice único de sessão ativa por contato
10. Paginação na listagem + busca no Mongo + os índices faltantes
11. Devolver o campo `atendente` no histórico

**Antes de qualquer campanha:**
12. Decidir entre consertar a fila de envio ou apagá-la e construir de novo. O estado atual é o pior dos dois mundos: parece que há controle de ritmo e não há
13. Campo de consentimento e log de tratamento que a limpeza não apague

---

## 9. Código morto encontrado

`fila_humana_service.cancelar_ticket` · `sessao_service.ativar_atendimento_humano` · `sessao_service._determinar_setor` e `MAPA_SETORES` · `mensagem_service.salvar_mensagem_recebida`, `salvar_mensagem_com_midia`, `salvar_mensagem_enviada` · `state_machine.py:224-226` (inalcançável) · `contato_sync_worker` (stub) · `envio_worker.worker_count` (anuncia 3 workers, cria 1) · `app/models/` inteiro (nunca importado, e descreve o banco errado) · `settings.whatsapp_delay_min/max`

E dois bugs pescados de passagem:

- **`GET /human/sessoes/{id}` sempre devolve 404** — busca por string onde o `_id` é ObjectId
- **`estatisticas` conta o dia em UTC**, ou seja das 21h de ontem. "Mensagens hoje" está inflado todos os dias

---

*Três auditorias independentes, todas com arquivo:linha. Nenhum arquivo foi alterado.*
