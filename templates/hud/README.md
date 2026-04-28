# Templates do HUD — Slayer Legend

Esta pasta contém os recortes que o detector visual (OpenCV template matching) usa para confirmar que o jogo está em primeiro plano. Há **dois grupos**:

## 🟢 Starter pack (versionado no repo)

Quatro templates **universais e independentes de idioma**, prontos para usar em qualquer instância:

| Arquivo | O que mostra |
|---|---|
| `starter_manabar.png` | Barra de cooldown azul segmentada (sequência de blocos) |
| `starter_map.png` | Sprite do mini-mapa |
| `starter_stage.png` | Caixa com símbolo "?" |
| `starter_toolbar.png` | Faixa horizontal de ícones da nav inferior (livro + espadas + avatar) |

> ⚠ Estes 4 sozinhos **não são suficientes** com a configuração padrão (`VISUAL_MIN_MATCHES=3`). Se a detecção falhar com só os starters em uma tela atípica, baixe `VISUAL_MIN_MATCHES=2` **temporariamente** ou — preferencialmente — adicione seus templates pessoais.

## 🔵 Templates pessoais (você adiciona)

Recortes específicos do seu setup, ignorados pelo git. **Nunca prefixe com `starter_`** (esse prefixo é reservado).

Sugestão: prefixe com `hud_`, ex: `hud_autobutton.png`, `hud_navbarstrip.png`. Idealmente adicione **3-6** próprios cobrindo:

- **Tela de combate normal**: botão "AUTO", strip da nav inferior com texto, avatar do personagem.
- **Modo de economia de bateria**: pelo menos 1-2 elementos exclusivos desse modo (ele aparece após X minutos de idle).
- **Diferentes fases**: um elemento estável que apareça em qualquer fase (ex: contador de stage, sem incluir o número que muda).

Por que pessoais e não no repo:
- **Idioma do jogo** — quem joga em PT-BR tem "AVENTURA"; em EN-US é "ADVENTURE".
- **Resolução da sua instância** — varia conforme o modelo do telefone na nuvem.
- **Personagem/equipamento** — alguns elementos do HUD mostram nick e nível.

---

## Como gerar (resumo)

> O passo a passo completo está no [README.md](../../README.md#configurando-o-fallback-visual-recomendado) na raiz do projeto.

1. Abra o jogo na instância em uma tela típica de combate.
2. Capture um screenshot via API:
   ```powershell
   python tools/capture.py
   ```
3. Abra o arquivo gerado em `screenshots/` em qualquer editor de imagem.
4. Recorte 3-6 elementos do HUD e salve aqui (sem prefixo `starter_`).
5. Valide com o jogo aberto **e** com o jogo fechado:
   ```powershell
   python tools/test_visual.py
   ```
6. **Só depois que os testes passarem**, habilite no `.env`:
   ```ini
   ENABLE_VISUAL_FALLBACK=true
   ```

---

## Critérios para escolher bons templates

| ✅ Bom template | ❌ Template ruim |
|---|---|
| Tem **texto + ícone** (botão "AUTO", nav inferior) | Forma geométrica simples (círculo, losango) |
| **≥ 60×60 px** após recorte | < 30×30 px (gera warning + falso positivo) |
| **Cor única do jogo** (azul-cobalto, verde-tóxico) | Preto/branco/cinza puro (combina com tudo) |
| Bate em **escala 1.00** quando jogo está aberto | Só bate em 0.85 ou 1.15 (assinatura de falso positivo) |
| **Estático** — sempre no mesmo lugar | Animado, scroll, mudança constante |
| **Apenas o elemento** (sem cenário ao redor) | Inclui pixels do background dinâmico |

### Cuidados específicos

⚠ **Não inclua o NÚMERO da fase no recorte.** Se você está na fase 920 e recorta "FASE 920" inteiro, o template para de casar quando você avançar para 921. Recorte só "FASE" ou só a moldura/ícone.

⚠ **Não inclua nick/nível.** Esses mudam ao trocar personagem ou subir level — o template fica inútil. Se quiser usar a área do avatar, recorte só a moldura colorida sem o texto.

⚠ **Não inclua valores de moedas/HP.** Mudam constantemente durante o jogo.

### Exemplos práticos (Slayer Legend, qualquer idioma)

**Sempre bons:**
- Botão "AUTO" (lateral direita, gear + texto)
- Strip horizontal da nav inferior com 2-3 botões juntos
- Linha de skills com cooldowns (10 ícones circulares em 2 linhas)
- Frame do avatar (apenas a moldura colorida, sem texto/level)

**Geralmente ruins (evite):**
- Ícones de moeda isolados (diamante, esmeralda, ouro) — formas simples casam com qualquer coisa
- Botões pequenos pretos/cinzas
- Setas de navegação genéricas
- Qualquer elemento com número que muda

---

## Calibração avançada

Após salvar os templates, rode os testes nos **dois cenários** e compare:

```powershell
# Com o jogo aberto em combate:
python tools/test_visual.py
```

Resultado esperado: maioria dos templates com score ≥ 0.80 em **escala 1.00**.

```powershell
# Com o jogo fechado (na tela inicial do Android virtual):
python tools/test_visual.py
```

Resultado esperado: nenhum template com score ≥ 0.70.

### Interpretando os scores

```
✅ 0.913 (escala 1.08) ███████████████████████████   hud_autobutton.png
✅ 0.844 (escala 1.00) █████████████████████████     starter_toolbar.png
❌ 0.521 (escala 0.92) ███████████████               hud_savebattery.png
```

- **Score alto + escala 1.00**: template excelente, mantém.
- **Score alto + escala 0.85 ou 1.15**: suspeito. Provavelmente está casando algo no fundo. Recorte um template maior e mais distintivo.
- **Score baixo (< 0.50)**: não está casando bem. Talvez o template tenha ficado com muito background, ou mudou de posição. Recapture.

---

## Ajustes finos no `.env`

```ini
VISUAL_MATCH_THRESHOLD=0.80   # 0.65 = permissivo, 0.85 = rigoroso
VISUAL_MIN_MATCHES=3           # quantos templates precisam casar simultaneamente
```

Prefira **melhorar os templates** a baixar o threshold — falsos positivos quando o jogo está fechado são mais perigosos que falsos negativos (você prefere receber alerta a mais do que descobrir 8h depois que o jogo parou).

---

## Arquivos suportados

`.png`, `.jpg`, `.jpeg`, `.bmp`, `.webp` — todos convertidos para escala de cinza no carregamento.
