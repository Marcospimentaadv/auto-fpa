# Como funciona o Auto-FP&A (versão portfólio)

Este documento explica o caminho que um extrato percorre dentro do sistema, do arquivo CSV até o parecer final. A primeira parte é para quem não programa. A segunda é para recrutadores e devs.

## Parte 1: em linguagem de negócio

Imagine o dono de uma empresa de serviços que fatura cerca de R$ 100 mil por mês. Ele exporta do sistema financeiro um extrato com tudo o que entrou e saiu e envia esse arquivo ao Auto-FP&A.

**1. O sistema confere o arquivo.** Verifica se cada linha tem data, descrição, categoria, tipo e valor. Se houver um valor com letras ou uma data impossível, ele avisa em qual linha está o problema, em vez de gerar um relatório errado.

**2. Guarda o histórico.** Os lançamentos vão para um banco de dados local. Se o empresário enviar o mesmo arquivo duas vezes, nada é duplicado. Se enviar o mês seguinte, ele se soma aos anteriores.

**3. Monta a DRE Gerencial.** Para cada mês:

| Linha | Exemplo (jan/2026) |
|---|---|
| Receita Bruta | R$ 85.000,00 |
| (−) Impostos | R$ 9.350,00 |
| (=) Receita Líquida | R$ 75.650,00 |
| (−) Custos Variáveis | R$ 18.500,00 |
| (=) Margem de Contribuição | R$ 57.150,00 |
| (−) Despesas Fixas | R$ 37.500,00 |
| (=) EBITDA (lucro operacional) | R$ 19.650,00 |

**4. Calcula o ponto de equilíbrio.** Em janeiro, cada R$ 1,00 vendido deixou R$ 0,67 para pagar as despesas fixas. Como elas somaram R$ 37.500, a empresa precisava faturar R$ 55.774 só para empatar. Ela faturou R$ 85.000, portanto tinha 34% de folga, que é a **margem de segurança**.

**5. Dispara alertas.** Se a folga cair abaixo de 15% (valor ajustável), o mês fica vermelho. No arquivo `cenario_estresse.csv`, abril aparece com prejuízo e faturamento abaixo do ponto de equilíbrio.

**6. Avalia investimentos.** O empresário quer comprar um sistema de R$ 60 mil que deve gerar entre R$ 18 mil e R$ 30 mil por ano. Se o dinheiro dele precisa render pelo menos 14% ao ano (a TMA), o sistema calcula:

- **VPL de R$ 21.751:** o projeto cria esse valor acima dos 14%;
- **TIR de 26,9%:** a rentabilidade do projeto;
- **Payback descontado de 3,6 anos:** o prazo real para recuperar o dinheiro.

Parecer: **viável**.

**7. Escreve o parecer do CFO Virtual.** Todos esses números viram um texto estruturado e são entregues a uma IA que roda no próprio computador. Ela devolve um parecer executivo com diagnóstico, o mês mais crítico e três recomendações. Nada é enviado à internet.

**8. Entrega o Excel.** O resultado sai numa planilha formatada. Os totais são fórmulas, então o gestor pode testar cenários direto no Excel.

## Parte 2: visão técnica

### Fluxo de dados

```
CSV ──► ingestao.carregar_csv()         valida e normaliza (DataFrame)
    ──► RepositorioLancamentos.salvar()  INSERT OR IGNORE no SQLite
    ──► repo.listar()                    histórico completo
    ──► dre.gerar_dre()                  pivot por mês + indicadores (funções puras)
    ──► dre.gerar_alertas()              regras de negócio → lista de Alerta
    ──► viabilidade.analisar_projeto()   ResultadoViabilidade (dataclass imutável)
    ──► ia_local.montar_prompt_cfo()     prompt em Markdown
    ──► ClienteOllama.gerar()            POST /api/generate em localhost
    ──► exportacao_excel.exportar_relatorio()   .xlsx com fórmulas e formatação condicional
```

As duas interfaces (`main.py` para terminal e `app.py` para web) só orquestram essas chamadas. Nenhuma regra de negócio mora nelas.

### Pontos que valem a conversa na entrevista

**Validação na borda.** `ingestao.py` detecta o separador, converte o formato brasileiro (`85.000,00` → `85000.0`), aceita `Saída` ou `Saida` e confere se o tipo combina com a categoria. Toda falha vira `ErroValidacao` com o número da linha.

**Idempotência.** A tabela tem `UNIQUE (data, descricao, categoria, valor)`. O retorno de `salvar()` informa quantos registros eram realmente novos, calculado com `conn.total_changes`.

**Casos de borda financeiros.** Margem de contribuição ≤ 0 deixa o ponto de equilíbrio como `NaN` (não existe faturamento que cubra os custos), o que gera um alerta crítico. Receita zero não causa divisão por zero.

**`npf.npv` × Excel.** A `numpy_financial.npv` não desconta o primeiro fluxo (t = 0), mas a função VPL do Excel desconta. Por isso a aba de viabilidade do Excel calcula o VPL somando os fluxos descontados, e os dois resultados batem.

**Privacidade como requisito.** `ClienteOllama` recusa hosts fora de `localhost`, `127.0.0.1` e `::1`, a menos que `permitir_remoto=True` seja passado explicitamente.

**Excel "vivo".** Os valores de entrada são escritos em azul e os subtotais como fórmulas (`=B9+B10`). A regra condicional de margem de segurança aponta para a célula `$B$22`, então mudar a premissa recolore a planilha sem rodar o Python.

**Testes.** São 35 testes que cobrem a validação de entrada, contas conferidas à mão, propriedades matemáticas (TIR zera o VPL; no ponto de equilíbrio, MC = despesas fixas), banco em diretório temporário, cliente de IA com `requests` simulado, estrutura do Excel e o painel Streamlit rodando sem navegador (`streamlit.testing.AppTest`).
