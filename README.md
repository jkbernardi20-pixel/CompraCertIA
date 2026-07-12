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

### 3. Ver o relatório

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

### Consultas rápidas

```bash
python -m compracertia compras [--item Café]   # histórico
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
