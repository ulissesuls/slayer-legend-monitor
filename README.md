# Slayer Legend Monitor — VMOS Cloud / VSPhone

Monitor 24/7 que verifica se o jogo **Slayer Legend** continua rodando na sua instância de cloud Android. Em caso de falha (instância caiu, jogo fechou, stream travado), envia alerta imediato no **Telegram**.

**Provedores suportados:** VMOS Cloud, VSPhone. Outros (UGPhone, Redfinger…) podem ser adicionados em poucas linhas — ver seção [Adicionando um novo provedor](#adicionando-um-novo-provedor).

Feito para quem deixa o farming automático ligado o dia inteiro e não quer descobrir 12 horas depois que o jogo parou no minuto 5.

## O que é detectado

| Falha                                          | Como é detectado                             |
| ---------------------------------------------- | --------------------------------------------- |
| Instância offline / em erro                   | API do provedor (`padDetails`)              |
| Jogo desinstalado                              | API do provedor (`listInstalledApp`)        |
| Jogo crashou ou foi para segundo plano         | Screenshot via API + template matching OpenCV |
| Stream congelado (HUD na tela mas jogo travou) | Comparação de 2 screenshots em sequência   |

## Arquitetura

```
┌─ a cada 20 min ─────────────────────────────────────────────┐
│                                                              │
│   1. API do provedor  ──→  online? padStatus=10? instalado? │
│         │                                                    │
│         ↓ sim                                                │
│   2. API screenshot  ──→  HUD presente? (OpenCV)             │
│         │                                                    │
│         ↓ sim                                                │
│   3. Screenshot+6s  ──→  pixels mudaram? (anti-congelamento) │
│                                                              │
│   Falha em qualquer etapa → alerta no Telegram               │
└──────────────────────────────────────────────────────────────┘
```

---

## Pré-requisitos

- **Python 3.10+** ([python.org/downloads](https://www.python.org/downloads/))
- **Git** ([git-scm.com](https://git-scm.com/downloads))
- Conta ativa em **um** dos provedores suportados, com pelo menos 1 instância:
  - [VMOS Cloud](https://www.vmoscloud.com)
  - [VSPhone](https://cloud.vsphone.com)
- Conta no Telegram

---

## Passo a passo de instalação (Windows)

> Para Linux/macOS os comandos são quase idênticos — substitua `.\.venv\Scripts\Activate.ps1` por `source .venv/bin/activate`.

### 1. Clonar o repositório

```powershell
git clone https://github.com/SEU_USUARIO/slayer-legend-monitor.git
cd slayer-legend-monitor
```

### 2. Criar e ativar o ambiente virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> Se a ativação falhar com erro de política, rode uma vez:
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

Você deve ver `(.venv)` no início do prompt.

### 3. Instalar dependências

```powershell
pip install -r requirements.txt
```

### 4. Criar o arquivo `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Preencha as 5 linhas marcadas como `[OBRIGATÓRIO]`. As demais já vêm com defaults validados.

---

## Escolhendo o provedor

O *Slayer Legend Monitor* suporta **VMOS Cloud** e **VSPhone**. Os dois usam APIs essencialmente idênticas (mesmo algoritmo de assinatura HMAC-SHA256, mesmos schemas de resposta) — diferem apenas no host e no prefixo das rotas.

No arquivo `.env`, defina qual provedor você usa:

```ini
CLOUD_PROVIDER=vmos       # ou: vsphone
```

E preencha apenas as credenciais do provedor escolhido (`VMOS_*` para VMOS, `VSPHONE_*` para VSPhone). As outras podem ficar como placeholders.

## Configurando o VMOS Cloud (`CLOUD_PROVIDER=vmos`)

### Obter Access Key e Secret Key

1. Entre em [vmoscloud.com](https://www.vmoscloud.com) e faça login.
2. No menu da esquerda, clique em → **Desenvolvedor**.
3. Procure o campo **AccessKey ID** (pode estar em "API" ou "Developer").
4. Clique em **Create AccessKey** (ou similar). Anote ambos:
   - `AccessKeyId` → vai em `VMOS_ACCESS_KEY`
   - `SecretAccessKey` → vai em `VMOS_SECRET_KEY`

> ⚠ A Secret Key só aparece uma vez na criação. Se perder, gere outra.

### Obter o ID da instância (`padCode`)

No painel das suas instâncias, clique na que você quer monitorar. Clique no ícone de configuração daquela instância e copie o **"ID do telefone na nuvem"** . 

Será algo como `APP64N6T7S3N8L6K`.

Coloque no arquivo `.env`:

```ini
VMOS_PAD_CODES=APP64N6T7S3N8L6K
```

> Para monitorar múltiplas instâncias, separe por vírgula:
> `VMOS_PAD_CODES=APP64N...,APP78M...`

> ⚠ **Não confunda o `padCode` com outros códigos do painel.** A API retorna vários identificadores em outros endpoints (ex: códigos `AC32010100091` que aparecem em listagens administrativas). O **único** identificador que você deve usar aqui é o **"ID do telefone na nuvem"** mostrado nas Informações Básicas da sua instância. Se a API responder `Instance not found`, é quase sempre o padCode errado.

## Configurando o VSPhone (`CLOUD_PROVIDER=vsphone`)

### Obter Access Key e Secret Key

1. Entre em [cloud.vsphone.com](https://cloud.vsphone.com) e faça login.
2. Acesse a página de credenciais (no painel deve haver uma seção **AK/SK** ou **API Access**).
3. Anote os dois valores:
   - `AccessKeyId` → vai em `VSPHONE_ACCESS_KEY`
   - `SecretAccessKey` → vai em `VSPHONE_SECRET_KEY`

### Obter o ID da instância

No painel do VSPhone, abra a instância e procure pelo identificador do telefone na nuvem (mesmo conceito do VMOS — uma string como `APP...`). Coloque no arquivo `.env`:

```ini
VSPHONE_PAD_CODES=APPxxxxxxxxxxxx
```

> O VSPhone parece ser baseado na mesma plataforma que o VMOS — os IDs têm formato similar e o algoritmo de assinatura é literalmente o mesmo (`armcloud-paas` no credentialScope). O `tools/diagnose.py` funciona idêntico para os dois — basta `CLOUD_PROVIDER=vsphone` no `.env`.

---

## Configurando o Telegram

Você precisa de **dois valores**: o `TELEGRAM_BOT_TOKEN` (identidade do bot) e o `TELEGRAM_CHAT_ID` (para onde enviar os alertas).

### Criar o bot

1. No Telegram, busque por **@BotFather** e abra o chat.
2. Envie `/newbot`.
3. Escolha um **nome** (ex: `Slayer-Legend-Monitor`) — pode ser qualquer texto.
4. Escolha um **username** terminado em `bot` (ex: `MeuSlayerMonitorBot`).
5. O BotFather vai responder com o **token** — algo tipo `123456:ABC-DEF...`. Copie e cole no `.env` em `TELEGRAM_BOT_TOKEN`.

### Obter seu Chat ID

1. No Telegram, busque pelo bot que você acabou de criar (pelo username).
2. Abra o chat e clique em **Iniciar** (ou envie `/start`). **Esse passo é obrigatório** — sem isso, o bot não consegue te enviar mensagens.
3. Busque por **@userinfobot**, abra e envie qualquer mensagem.
4. Ele responde com seu **ID** — um número como `989662939`. Cole no `.env` em `TELEGRAM_CHAT_ID`.

### Validar a configuração

```powershell
python tools/diagnose.py
```

Abra o jogo e deixe-o rodando na sua instância. Esse script detecta automaticamente o provedor configurado (`CLOUD_PROVIDER` no `.env`) e faz as verificações:

- ✅ Credenciais do provedor (VMOS ou VSPhone) funcionam — lista padCodes da sua conta.
- ✅ Token do Telegram é válido.
- ✅ Mensagem de teste chega no chat configurado.
- ✅ Lista todos os apps instalados e destaca o pacote do Slayer Legend.

Se algum item falhar, ele mostra exatamente qual variável corrigir no `.env`.

---

## Primeiro teste

Ainda com o jogo aberto e com o `.env` preenchido, faça uma verificação única para confirmar tudo:

```powershell
python monitor.py --once
```

Saída esperada:

```
[INFO] slayer_monitor: Verificando instância APP64N6T7S3N8L6K ...
[INFO] slayer_monitor: [API] APP64N6T7S3N8L6K -> API: instância online, padStatus=running, pacote instalado.
```

Não chega mensagem no Telegram porque está tudo OK — o monitor só envia alertas quando há problema. Para confirmar que o Telegram funciona, rode `python tools/diagnose.py` (ele envia uma mensagem de teste).

---

## Configurando o fallback visual (recomendado)

Sem o fallback visual, o monitor detecta apenas "instância offline" ou "jogo desinstalado". O fallback visual cobre o caso mais comum: **jogo crashou e voltou para a tela inicial do Android, mas a instância continua ligada**. Nesta parte, é importante que cada jogador configure de acordo com a sua tela.

### Starter pack incluído no repo

Para reduzir o atrito de primeira instalação, o repo já inclui **4 templates universais** no diretório `templates/hud/`:

| Arquivo                 | O que é                                      | Universal?              |
| ----------------------- | --------------------------------------------- | ----------------------- |
| `starter_manabar.png` | Barra de cooldown azul (sequência de blocos) | ✅ Pixel art, sem texto |
| `starter_map.png`     | Sprite do mini-mapa                           | ✅ Sem texto            |
| `starter_stage.png`   | Caixa com símbolo "?"                        | ✅ "?" é universal     |
| `starter_toolbar.png` | Faixa de ícones da barra inferior            | ✅ Só ícones          |

Estes funcionam **independentemente do idioma** do seu jogo. **Mas com 4 templates a detecção fica no limite** (`VISUAL_MIN_MATCHES=3` exige ≥3 batendo simultaneamente). Você precisa adicionar **3-4 templates próprios** para um conjunto robusto. Os melhores candidatos pessoais são:

- **3 elementos da fase atual** (nome da fase, contador, barra de progresso, botão de boss)
- **3 elementos do modo de economia de bateria** (que aparecem após o jogo ficar idle)

### Por que você ainda precisa de templates próprios?

Os 4 starters cobrem só elementos **estáticos e genéricos**. Para detecção robusta também queremos elementos que:

- Confirmam que o jogo está em **combate ativo**, não na tela inicial do app.
- Aparecem em **modos diferentes** (combate normal, economia de bateria, idle de farming).

Esses elementos quase sempre têm:

- **Texto** ("FASE 920", "AUTO", "AVENTURA") — varia com o idioma.
- **Resolução específica** da sua instância (720×1280, 1080×1920…) — varia com o modelo do telefone na nuvem.

Por isso são pessoais. Você gera os seus em ~3 min seguindo o passo a passo abaixo. Esses passos são importantes para deixar o detector mais robusto e reduzir em muito a possibilidade de falhas na detecção.

### Passo a passo para adicionar seus templates

**1. Abra o jogo na sua instância** (VMOS ou VSPhone) em uma tela típica de combate (farming ativo, boss). É importante que, no farming, você deixe sempre na tela mais básica (skills e toolbar inferior), para fins de padronização. Se você deixa, por exemplo, farmando na tela de minimapa, o matching pode não funcionar.

**2. Capture um screenshot via API:**

```powershell
python tools/capture.py
```

O arquivo é salvo em `screenshots/<padCode>_<timestamp>.png`.

**3. Abra o screenshot** em qualquer editor de imagem (Paint, Recortes do Windows, Photoshop, GIMP).

**4. Recorte de 3 a 6 elementos do HUD** e salve cada um como `.png` em `templates/hud/`. Use **qualquer prefixo exceto `starter_`** (esses são reservados para os starters versionados). Sugestão: `hud_*.png`.

| ✅ Bons templates pessoais                               | ❌ Evite                                                                          |
| -------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Botão "AUTO" (texto + ícone de engrenagem)             | Ícones de moeda (diamante, esmeralda) — formas simples casam com qualquer coisa |
| Strip horizontal com 2-3 botões da nav inferior + texto | Quadrados pretos/cinzas                                                           |
| Nome da fase ("FASE 920" em PT, "STAGE 920" em EN)       | Pixels isolados ou setas genéricas                                               |
| Faixa de ícones da toolbar ou seu nickname              | Letras isoladas                                                                   |
| Avatar do personagem com moldura colorida                | Formas geométricas simples                                                       |

**Regras práticas:**

- **≥ 60×60 pixels** após recorte
- **Texto ou cores únicas do jogo** (azul-cobalto, verde-tóxico)
- **Estático** — sempre na mesma posição durante o combate
- **Apenas o elemento** — sem incluir pixels do cenário ao redor (que muda)

> ⚠ **Cuidado misturando elementos.** Se você recortar "botão da fase" mas pegar pixels do número da fase junto, o template fica pessoal (cada player está em uma fase) e pode parar de bater quando você avançar. Recorte só a moldura/ícone, **sem o número**.

**5. Execute um teste dos seus templates ANTES de habilitar o fallback** — o `test_visual.py` funciona sem precisar do `ENABLE_VISUAL_FALLBACK=true`:

```powershell
# Com o jogo aberto na tela de combate:
python tools/test_visual.py
```

Esperado: `🎯 HUD DETECTADO` com **maioria dos templates ≥ 0.80 em escala 1.00**.

```powershell
# Feche o jogo (volte pra home do Android virtual) e rode de novo:
python tools/test_visual.py
```

Esperado: `⚠ HUD NÃO detectado`. Se algum template ainda bater alto **com o jogo fechado** (especialmente em escalas 0.85 ou 1.15, **não** em 1.00), **remova esse template** — ele é fonte de falso positivo. Substitua por algo maior/mais distintivo, e repita o teste.

**6. Quando ambos os testes derem o resultado esperado, habilite o fallback no `.env`:**

```ini
ENABLE_VISUAL_FALLBACK=true
```

Esse é o passo que faz o `monitor.py` realmente usar o template matching em cada ciclo. Sem ele, o monitor segue funcionando só com a checagem da API.

### Ajustando os parâmetros

Se quiser tornar a detecção mais ou menos sensível, edite o `.env`:

```ini
VISUAL_MATCH_THRESHOLD=0.80   # 0.65 = permissivo, 0.85 = rigoroso
VISUAL_MIN_MATCHES=3          # quantos templates precisam casar simultaneamente
```

---

## Configurando a detecção de "frame congelado" (opcional)

Detecta o cenário raro: jogo crashou mas a imagem permaneceu congelada na tela do streaming (VMOS/VSPhone), com o HUD ainda visível. Sem essa checagem o fallback visual diria "tudo OK" porque o HUD ainda está lá.

> Pré-requisito: o **fallback visual já deve estar funcionando** (templates calibrados e validados). O frozen check só roda quando o HUD foi detectado no ciclo.

### Como ativar

**1. Calibre o threshold com o jogo em combate ativo** (o `test_frozen.py` funciona sem precisar habilitar nada no `.env`):

```powershell
python tools/test_frozen.py --runs 3
```

Saída exemplo:

```
[1/3] diff=0.14701  🎬 ATIVO
[2/3] diff=0.16262  🎬 ATIVO
[3/3] diff=0.09414  🎬 ATIVO

Resumo: min=0.09414  avg=0.13459
```

**2. Defina `FROZEN_DIFF_THRESHOLD` com base na sua medição** — um pouco abaixo do mínimo, bem acima de 0:

```ini
FROZEN_DIFF_THRESHOLD=0.02   # entre ~0.005 (default) e o seu min medido
FROZEN_CHECK_DELAY_SECONDS=6
```

**3. Quando o threshold estiver calibrado, ative no `.env`:**

```ini
ENABLE_FROZEN_CHECK=true
```

A partir daí, em cada ciclo onde o HUD for detectado, o monitor automaticamente:

- Tira screenshot 1 → faz template matching.
- Espera 6 segundos.
- Tira screenshot 2 → compara pixel-a-pixel.
- Se `diff < FROZEN_DIFF_THRESHOLD` → alerta "Frame CONGELADO".

**Observação**: é recomendável **DESATIVAR** o modo de economia de energia, pois como ele é quase inteiramente "estático", o Monitor pode confundir o estado de congelamento se tirar prints iguais.

---

## Checklist final do `.env` antes de subir em produção

Depois de validar tudo com as ferramentas de teste, confira que seu `.env` tem as flags certas. Os defaults do `.env.example` vêm em **modo seguro** (`false`) para que o primeiro `python monitor.py --once` funcione sem templates. Para a configuração 24/7 completa:

| Variável                  | Default   | Recomendado em produção                                       |
| -------------------------- | --------- | --------------------------------------------------------------- |
| `ENABLE_VISUAL_FALLBACK` | `false` | `true` ← depois de validar templates com `test_visual.py`  |
| `ENABLE_FROZEN_CHECK`    | `false` | `true` ← depois de calibrar threshold com `test_frozen.py` |

> ⚠ **Se você esquecer de virar essas flags, o monitor segue rodando** mas só faz a checagem básica da API (instância online + jogo instalado). **Não vai detectar jogo crashado nem frame congelado** — só instância caída ou desinstalada.

Confirme com:

```powershell
# Saída esperada com tudo ligado, jogo aberto, no log do --once:
# [API] ... -> API: instância online, padStatus=running, pacote instalado.
# [Visual] ... -> HUD detectado — 4/3 matches (≥0.80). ...
# [Frozen] ... -> diff=0.13456 (threshold=0.02000, frozen=False)
python monitor.py --once
```

Se você não vê as linhas `[Visual]` e `[Frozen]`, alguma flag ainda está `false`.

---

## Rodando em produção (24/7)

### Opção 0 — Atalhos de área de trabalho (mais simples no Windows)

O projeto inclui três scripts `.bat` que automatizam tudo:

| Arquivo                          | O que faz                                                  | Como parar                    |
| -------------------------------- | ---------------------------------------------------------- | ----------------------------- |
| `start_monitor.bat`            | Roda em janela visível (vê os logs em tempo real)        | `Ctrl+C` ou fechar a janela |
| `start_monitor_background.bat` | Roda invisível em segundo plano (libera o terminal)       | Executar `stop_monitor.bat` |
| `stop_monitor.bat`             | Encerra qualquer instância do monitor que estiver rodando | —                            |

**Para criar atalhos na área de trabalho:**

1. Abra a pasta do projeto no Explorer.
2. Clique com o botão direito em `start_monitor_background.bat` → **Enviar para** → **Área de trabalho (criar atalho)**.
3. (Opcional) Renomeie o atalho para algo amigável: `Iniciar Slayer Monitor`.
4. Repita para `stop_monitor.bat` → `Parar Slayer Monitor`.

A partir daí: dois cliques na área de trabalho e o monitor começa a rodar invisivelmente. Os logs ficam gravados em `monitor.log` dentro da pasta do projeto.

> Para inicialização **automática com o Windows**: cole o atalho de `start_monitor_background.bat` na pasta `shell:startup` (cole esse nome literal no Executar — `Win+R` — e Enter).

### Opção 1 — Loop simples na janela do PowerShell

```powershell
python monitor.py
```

A janela precisa ficar aberta. Para parar, `Ctrl + C`.

### Opção 2 — Em segundo plano (Windows)

Use `pythonw.exe` (variante sem janela de console):

```powershell
Start-Process -FilePath ".venv\Scripts\pythonw.exe" `
              -ArgumentList "monitor.py" `
              -WorkingDirectory (Get-Location) `
              -RedirectStandardOutput "monitor.log" `
              -RedirectStandardError "monitor.err.log"
```

Para parar:

```powershell
Get-Process pythonw | Stop-Process
```

Acompanhar o log ao vivo:

```powershell
Get-Content monitor.log -Wait
```

### Opção 3 — Como serviço com auto-restart (Windows, recomendado)

Use o **NSSM** ([nssm.cc](https://nssm.cc/download)):

```powershell
# Baixe e extraia o NSSM, depois:
nssm install SlayerMonitor
```

No GUI que abrir:

- **Path**: `C:\caminho\completo\.venv\Scripts\pythonw.exe`
- **Startup directory**: `C:\caminho\completo\Projeto MONITOR`
- **Arguments**: `monitor.py`

Inicie o serviço:

```powershell
nssm start SlayerMonitor
```

Ele reinicia automaticamente em caso de queda, sobrevive a logoff, e inicia com o Windows.

### Como parar o Monitor

Depende de **como** você iniciou:

| Iniciado com                           | Como parar                                             |
| -------------------------------------- | ------------------------------------------------------ |
| `python monitor.py` (janela aberta)  | `Ctrl + C` na janela                                 |
| `start_monitor.bat`                  | `Ctrl + C` ou fechar a janela                        |
| `start_monitor_background.bat`       | Duplo-clique em `stop_monitor.bat`                   |
| `Start-Process pythonw ...` (manual) | `Get-Process pythonw \| Stop-Process` no PowerShell   |
| Serviço NSSM                          | `nssm stop SlayerMonitor` (no PowerShell como admin) |
| systemd (Linux)                        | `sudo systemctl stop slayer-monitor`                 |

**Verificar se o monitor ainda está rodando:**

```powershell
Get-Process pythonw -ErrorAction SilentlyContinue
```

Se não retornar nada, está parado.

> ⚠ Se você rodar `stop_monitor.bat` quando tem **outros scripts Python invisíveis** abertos no PC (ex: outros bots, automações), eles também serão encerrados — o `pythonw.exe` é compartilhado. Nesse caso prefira parar pelo Gerenciador de Tarefas: aba **Detalhes**, procurar `pythonw.exe`, clicar com direito → **Finalizar tarefa** apenas no que tem `monitor.py` na linha de comando.

### (Avançado) Empacotar como `.exe` standalone

Se quiser distribuir um único `.exe` para usuários **sem Python instalado**, dá para usar [PyInstaller](https://pyinstaller.org):

```powershell
pip install pyinstaller
pyinstaller --onefile --noconsole --name SlayerMonitor monitor.py
```

O executável fica em `dist\SlayerMonitor.exe`. Para uso pessoal isso é exagero (o `.bat` resolve), mas é útil se for distribuir para amigos que não programam. Atenção: o binário fica grande (~200-500 MB por causa do OpenCV e numpy embutidos), e antivírus às vezes marcam executáveis PyInstaller como suspeitos — pode ser necessário criar uma exceção.

### Opção 4 — Linux com systemd

Crie `/etc/systemd/system/slayer-monitor.service`:

```ini
[Unit]
Description=Slayer Legend Monitor
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/slayer-legend-monitor
EnvironmentFile=/opt/slayer-legend-monitor/.env
ExecStart=/opt/slayer-legend-monitor/.venv/bin/python monitor.py
Restart=on-failure
RestartSec=30
User=monitor

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now slayer-monitor
journalctl -u slayer-monitor -f
```

---

## Estrutura do projeto

```
.
├── monitor.py                       # entry point + loop principal
├── start_monitor.bat                # inicia com janela visível (Windows)
├── start_monitor_background.bat     # inicia em segundo plano (Windows)
├── stop_monitor.bat                 # encerra o monitor (Windows)
├── slayer_monitor/
│   ├── config.py                    # carrega o .env
│   ├── vmos_client.py               # cliente VMOS/VSPhone (HMAC-SHA256 AK/SK)
│   ├── telegram_notifier.py         # alertas no Telegram
│   └── visual_detector.py           # OpenCV template matching + frozen detection
├── tools/
│   ├── diagnose.py                  # valida credenciais, lista padCodes e apps
│   ├── capture.py                   # captura screenshot da API para templates
│   ├── test_visual.py               # testa template matching e mostra scores
│   └── test_frozen.py               # mede diff entre screenshots para calibrar
├── templates/hud/
│   ├── starter_*.png                # 4 templates universais (versionados)
│   └── hud_*.png                    # SEUS templates (fora do git)
├── screenshots/                     # screenshots gerados (fora do git)
├── .env                             # SUAS credenciais (fora do git)
├── .env.example                     # modelo comentado
├── requirements.txt
├── LICENSE                          # MIT
└── README.md
```

---

## Ferramentas auxiliares

Todas rodam dentro do `.venv` ativo, na raiz do projeto:

| Comando                                         | O que faz                                                     |
| ----------------------------------------------- | ------------------------------------------------------------- |
| `python monitor.py`                           | Loop contínuo (a cada 20 min)                                |
| `python monitor.py --once`                    | Verificação única                                          |
| `python tools/diagnose.py`                    | Valida `.env` e descobre padCodes/packageName               |
| `python tools/capture.py`                     | Salva um screenshot da instância em `screenshots/`         |
| `python tools/test_visual.py`                 | Mostra score de cada template contra um screenshot            |
| `python tools/test_visual.py --image foo.png` | Testa template matching numa imagem local                     |
| `python tools/test_frozen.py --runs 3`        | Mede diff entre capturas (calibrar `FROZEN_DIFF_THRESHOLD`) |

---

## Troubleshooting

### `Erro 2020: Instance not found` (VMOS ou VSPhone)

O `padCode` no `.env` (`VMOS_PAD_CODES` ou `VSPHONE_PAD_CODES`, conforme o provedor) está errado. Causas comuns:

- **Você colou outro identificador** que apareceu no painel (ex: ID do servidor físico tipo `AC32010100091`). O único correto é o **"ID do telefone na nuvem"** mostrado nas Informações Básicas, ex: `APP64N6T7S3N8L6K`.
- **Tem espaço ou caractere invisível** colado junto. Apague e digite manualmente.
- **Você está com `CLOUD_PROVIDER` errado** — se a conta é VSPhone mas você deixou `vmos`, a API responde "instance not found" porque está consultando outro provedor.

Use `python tools/diagnose.py` — ele lista os padCodes que sua conta consegue acessar via API do provedor configurado.

### `Pacote NÃO está instalado` mesmo com o jogo aberto

O `packageName` do Slayer Legend **varia por região do APK**. Por exemplo:

- **Versão global atual**: `com.gear2.growslayer` ← este é o default no `.env.example`
- **Versão antiga**: `com.superplanet.slayerlegend`
- Outras regiões podem ter sufixos como `.kr`, `.jp`, etc.

Rode `python tools/diagnose.py` — a seção "APPS INSTALADOS NA INSTÂNCIA" lista cada pacote e destaca o do Slayer Legend. Copie o `packageName` exato e cole em `GAME_PACKAGE` no seu `.env`.

### `chat not found` no Telegram

Você ainda **não enviou mensagem ao bot**. Bots do Telegram só conseguem mandar mensagens para usuários que **iniciaram a conversa primeiro**.

1. No Telegram, busque pelo username do seu bot.
2. Abra o chat e envie `/start`.
3. Rode `python tools/diagnose.py` de novo — deve enviar a mensagem de teste.

### `Bad Request: Bot was blocked by the user`

Você bloqueou seu próprio bot em algum momento. No Telegram, abra o chat com o bot, role até o fim, e clique em **Desbloquear**.

### `HTTP 401/403` da API do provedor

Suas credenciais AK/SK estão erradas, expiraram, ou foram revogadas. Vá no painel do provedor configurado:

- **VMOS**: [vmoscloud.com](https://www.vmoscloud.com) → Personal Center → AccessKey
- **VSPhone**: [cloud.vsphone.com](https://cloud.vsphone.com) → AK/SK

Em ambos:

- Confirme que a chave está ativa.
- Recrie se necessário (a Secret só aparece uma vez na criação).
- Cuidado para não copiar espaços antes/depois quando colar no `.env`.

### `HTTP 404: Not Found` em algum endpoint

Pode acontecer se o provedor atualizar a API. O endpoint `/padList` (em qualquer prefix) retorna 404 em algumas regiões/contas — isso é esperado e o `diagnose.py` tem fallbacks. Se o erro for em endpoints que o monitor usa (`padDetails`, `listInstalledApp`, `getLongGenerateUrl`), abra uma issue no GitHub indicando qual `CLOUD_PROVIDER` você está usando.

### Visual fallback dá falso positivo (HUD detectado com jogo fechado)

Algum template está casando ruído de fundo. **Sintoma típico:** o template casa em escala **0.85 ou 1.15**, nunca em **1.00**.

```powershell
# Feche o jogo no Android virtual e rode:
python tools/test_visual.py
```

Qualquer template com score ≥ 0.70 nesse cenário é candidato a remoção. Substitua por algo maior e mais distintivo. Os 4 starters foram validados — se o problema for com algum starter especificamente, abra uma issue.

### Visual fallback dá falso negativo (HUD não detectado com jogo aberto)

Possíveis causas:

- **Resolução da sua instância difere muito do template**. Verifique se o screenshot da API tem resolução próxima de 720×1280. Se for muito diferente, recapture os templates pessoais com `python tools/capture.py`.
- **Você está em uma tela atípica do jogo** (loja, missões, configurações). Os starters foram pensados para combate/farming. Faça o teste em combate ativo.
- **`VISUAL_MIN_MATCHES` muito alto para os templates atuais**. Reduza para `2` no `.env` se você só tem os 4 starters + 2 pessoais.

Calibre rodando:

```powershell
python tools/test_visual.py     # com o jogo aberto
```

Olhe quais templates estão batendo (✅) e quais não (❌). Se vários ❌ têm score acima de 0.70, considere reduzir `VISUAL_MATCH_THRESHOLD` para 0.70 no `.env`.

### Frozen check dispara durante jogabilidade real

Seu `FROZEN_DIFF_THRESHOLD` está alto demais. Rode `python tools/test_frozen.py --runs 5` durante combate ativo, anote o **mínimo** medido, e ajuste `FROZEN_DIFF_THRESHOLD` para ~50% desse mínimo.

### Tudo OK mas não recebo nada no Telegram

**Isso é o esperado** — o monitor só envia alertas quando há **problema**. Silêncio = tudo funcionando.

Para confirmar que o canal funciona:

- `python tools/diagnose.py` envia uma mensagem de teste.
- `python monitor.py` (loop completo) envia uma mensagem de "Monitor iniciado" no startup.

### Como ver os logs do monitor rodando em segundo plano

```powershell
# Se rodando com pythonw + redirect (Opção 2):
Get-Content monitor.log -Wait

# Se rodando como serviço NSSM (Opção 3):
Get-EventLog Application -Source "SlayerMonitor" -Newest 20

# Se rodando com systemd (Linux):
journalctl -u slayer-monitor -f
```

---

## Ideias para contribuição

Este projeto é deliberadamente simples — funciona como CLI/serviço local. Algumas direções interessantes para quem quiser estender:

### Funcionalidades

- **Auto-recovery**: ao detectar o jogo fechado, chamar `startApp` da API do provedor para tentar reabrir antes de alertar.
- **Múltiplos jogos**: generalizar `GAME_PACKAGE` para uma lista, com templates por jogo.
- **Dashboard de histórico**: salvar checagens em SQLite e exibir gráfico de uptime.
- **Detecção mais inteligente**: SSIM em vez de diff médio para frozen check; ORB/SIFT em vez de template matching para o HUD.
- **Outros canais de alerta**: Discord webhook, e-mail, Pushover, ntfy.sh.
- **Multi-cloud**: VMOS Cloud e VSPhone já são suportados (alterando `CLOUD_PROVIDER` no `.env`). Falta adicionar UGPhone (próximo alvo) e candidatos como Redfinger e GeeLark — ver seção [Adicionando um novo provedor](#adicionando-um-novo-provedor).

### Empacotamento e UX

- **App Desktop** com Tauri/Electron + UI para configurar o `.env` num formulário, ver status em tempo real, e exibir os screenshots capturados.
- **App mobile multi-plataforma (Android + iOS) com integração aos 3 principais provedores** (VMOS, VSPhone, UGPhone), publicado na **Play Store** e na **App Store**. UI nativa para login na conta do provedor escolhido, configurar instâncias monitoradas, receber push nativo (FCM no Android, APNs no iOS) em vez de Telegram, e visualizar screenshots históricos. Stack possível: React Native ou Flutter (compartilhado entre iOS/Android), backend FastAPI hospedado em VPS rodando o loop de verificação (já que apps mobile não rodam loops 24/7 confiavelmente em background), com o mesmo core deste repo. Pré-requisito: refactor multi-provider concluído.
- **Interface web** com FastAPI + React: hospedável em VPS, dashboard com status de todas as instâncias, login multi-usuário.
- **Imagem Docker** — `docker run -e CLOUD_PROVIDER=vmos -e VMOS_ACCESS_KEY=... slayer-monitor` para deploy 1-comando.
- **GitHub Actions schedule** rodando `python monitor.py --once` a cada 20 min como cron-job-as-a-service grátis.

### Robustez

- **Retry com backoff exponencial** nas chamadas à API do provedor.
- **Tratamento separado para timeouts de rede** (não disparar alerta de Telegram no Telegram em timeouts isolados; só após N falhas consecutivas).
- **Persistência do estado de cooldown** em arquivo, para sobreviver a restart do processo.
- **Métricas Prometheus** para integração com Grafana.
- **Testes automatizados** com mocks da API do provedor e screenshots sintéticos.

PRs e issues são bem-vindos!

---

## Adicionando um novo provedor

Se o provedor que você usa segue o mesmo padrão do VMOS/VSPhone (HMAC-SHA256 com AK/SK, service name `armcloud-paas`, endpoints `padDetails`/`listInstalledApp`/`getLongGenerateUrl`/`startApp`), basta:

**1.** Em [`slayer_monitor/config.py`](slayer_monitor/config.py), adicione uma entrada em `PROVIDER_PROFILES`:

```python
PROVIDER_PROFILES = {
    "vmos":    {"default_host": "api.vmoscloud.com", "path_prefix": "/vcpcloud/api/padApi"},
    "vsphone": {"default_host": "api.vsphone.com",   "path_prefix": "/vsphone/api/padApi"},
    "ugphone": {"default_host": "api.ugphone.com",   "path_prefix": "/ugphone/api/padApi"},  # novo
}
```

**2.** Documente as variáveis no `.env.example` (`UGPHONE_ACCESS_KEY`, `UGPHONE_SECRET_KEY`, `UGPHONE_API_HOST`, `UGPHONE_PAD_CODES`).

**3.** Habilite no `.env`:

```ini
CLOUD_PROVIDER=ugphone
UGPHONE_ACCESS_KEY=...
UGPHONE_SECRET_KEY=...
UGPHONE_PAD_CODES=...
```

Pronto. Se o provedor diverge do padrão (signing diferente, schemas de resposta distintos, polling de taskId em vez de URL longeva), aí é necessário criar uma classe cliente própria — abrir issue para discutir o design.

---

## Licença

[MIT](LICENSE) — use, modifique, distribua livremente. Sem garantias.
