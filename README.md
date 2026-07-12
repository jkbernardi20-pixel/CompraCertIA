# CompraCertIA (MVP de uso pessoal)

Analisa o **histórico acumulado** de compras de supermercado e sinaliza onde
uma decisão diferente manteria a qualidade de vida gastando menos. Exemplo do
tipo de sinal que o app gera:

> "Nos últimos 12 meses você comprou 46 pacotes deste café. Uma alternativa
> dentro do seu perfil economizaria R$ 280/ano sem perda perceptível de
> qualidade."

Este é um MVP para testar a hipótese central — o valor está na análise do
histórico, não na comparação isolada de dois produtos. Sem monetização, sem
deploy, sem app publicado.

## Princípios que não mudam

- **Imparcialidade absoluta** — nenhuma recomendação por comissão/afiliado.
- Interesse do usuário acima de qualquer interesse comercial.
- Toda recomendação vem com **justificativa técnica explícita**.
- A decisão final é sempre do usuário — o app nunca decide por ele.
- **Categoria A** (decisão técnica, mensurável — leite, massa, café, pão,
  azeite) é otimizada. **Categoria B** (preferência pessoal — cerveja, vinho,
  perfume) **nunca** recebe recomendação.

## Requisitos

Python 3.10+ (só biblioteca padrão — sem dependências).

## Uso

Tudo roda via CLI a partir da raiz do projeto. O banco SQLite é criado
automaticamente em `./compras.db` (mude com `--db caminho.db` ou a variável
de ambiente `COMPRACERTIA_DB`).

### 1. Registrar uma compra

```bash
python -m compracertia registrar --item Café --marca Melitta \
    --preco 37.80 --quantidade 2 --unidade 500g --categoria A
```

- `--preco` é o **total pago**; `--quantidade` é o número de pacotes.
- `--unidade` descreve o pacote (`500g`, `1L`, `un`...) — a comparação com
  alternativas só acontece entre pacotes da mesma unidade.
- `--data AAAA-MM-DD` é opcional (padrão: hoje).
- `--categoria A|B` só é exigida na **primeira** compra do item; depois o app
  lembra.

### 2. Cadastrar alternativas (base manual, só Categoria A)

```bash
python -m compracertia alternativa --item Café --marca "Três Corações" \
    --preco 15.90 --unidade 500g --atributos "100% arábica, torra média"
```

`--preco` aqui é por pacote. `--atributos` são os atributos técnicos que
justificam a equivalência de qualidade. Cadastrar de novo a mesma
marca/unidade atualiza o preço.

### 3. Importar compras em lote (CSV)

Para não digitar item por item, importe um CSV com cabeçalho:

```bash
python -m compracertia importar compras.csv
```

Colunas: `item`, `marca`, `preco` (obrigatórias) e, opcionais, `quantidade`,
`unidade`, `data`, `categoria`. Exemplo:

```csv
item,marca,preco,quantidade,unidade,data,categoria
Café,Melitta,18.90,1,500g,2025-01-10,A
Café,Melitta,19.50,1,500g,2025-02-10,
Azeite,Gallo,35.00,1,500ml,2025-01-15,A
```

A `categoria` só é necessária na primeira vez que cada item aparece. Linhas
inválidas são ignoradas e reportadas com o número da linha — as válidas
entram normalmente.

### 4. Corrigir ou remover uma compra

Cada compra tem um id (mostrado em `compras`). Para corrigir um registro
errado, informe só os campos que mudam:

```bash
python -m compracertia editar 12 --preco 15.00 --marca "Três Corações"
python -m compracertia remover 12
```

A edição altera marca, preço, quantidade, unidade e data. Para trocar o item
em si, remova e registre de novo.

### 5. Ver o relatório

```bash
python -m compracertia relatorio
```

O relatório (sob demanda) mostra:

- **Onde dá para economizar**: itens Categoria A recorrentes (3+ compras) com
  alternativa mais barata na mesma unidade, economia **anualizada pela sua
  frequência real de compra** e justificativa técnica completa.
- **Recorrentes sem recomendação**: itens A frequentes que ainda não têm
  alternativa cadastrada — é onde vale alimentar a base.
- **Categoria B**: listados como recorrentes, mas explicitamente fora da
  otimização.

### Interface web local (opcional)

Se preferir clicar a digitar, há uma página local mínima (sem deploy, só na
sua máquina) para registrar uma compra e ver o relatório:

```bash
python -m compracertia web        # abre em http://127.0.0.1:8000
```

Use `--porta` e `--host` para ajustar. A CLI continua sendo o caminho
completo; a web cobre o essencial do dia a dia.

**Testar no celular (mesmo Wi-Fi):** rode com `--host 0.0.0.0` e o servidor
imprime o endereço da máquina na rede local — abra esse endereço no navegador
do telefone:

```bash
python -m compracertia web --host 0.0.0.0
# No celular (mesmo Wi-Fi):  http://192.168.x.x:8000
```

Isso expõe o app na sua rede local (sem senha), o que é adequado para uso
pessoal em casa. Não use em redes públicas.

*Não conectou pelo celular na rede local?* É comum: o firewall do PC pode
bloquear a porta, ou o roteador isola os dispositivos entre si (Wi-Fi de
convidado, "AP/client isolation"). Nesses casos o acesso externo abaixo
resolve — o túnel é uma conexão de saída do PC e não depende de os dois
aparelhos se enxergarem na rede.

### Testar no celular fora de casa (acesso externo)

Para abrir no celular em qualquer rede (4G, fora de casa), o comando
`compartilhar` expõe a interface numa URL pública temporária via
[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-tunnel/downloads/),
sem deploy, sem conta e sem abrir portas no roteador:

```bash
python -m compracertia compartilhar
```

Requisito: o binário `cloudflared` instalado
(`brew install cloudflared` no macOS; `winget install Cloudflare.cloudflared`
no Windows; pacote/baixa direta no Linux). O comando sobe o servidor, abre o
túnel e imprime uma URL `https://...trycloudflare.com` — abra no celular. Com
o extra opcional de QR instalado (`pip install "compracertia[qr]"`), ele ainda
desenha um QR Code no terminal para escanear direto. `Ctrl+C` encerra o
compartilhamento e fecha a URL.

A URL é temporária e pública enquanto o comando roda: qualquer pessoa com o
link acessa (o app não tem senha). Use para testes pontuais e encerre depois.

### Consultas rápidas

```bash
python -m compracertia compras [--item Café]   # histórico (com ids)
python -m compracertia itens                   # itens e categorias
python -m compracertia alternativas [--item Café]
```

## Como a economia é calculada

1. Item é **recorrente** se tem 3+ compras registradas.
2. A frequência anual é projetada do histórico real:
   `quantidade_total × 365 ÷ dias entre a primeira e a última compra`
   (com menos de 30 dias de histórico, o relatório avisa que a base é curta).
3. Economia/ano = (preço médio pago por pacote − preço da alternativa mais
   barata) × pacotes projetados por ano.
4. Só compara pacotes da **mesma unidade** (nunca R$/500g contra R$/1kg).

## Testes

```bash
python -m unittest discover -s tests -v
```

## Fora de escopo deste MVP

Leitura de QR Code de NFC-e (meta para v2), OCR de nota fiscal, app mobile,
monetização, benchmarking contra concorrentes. Primeiro: meses de uso real
validando a hipótese.
