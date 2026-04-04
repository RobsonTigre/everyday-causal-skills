[🇺🇸  English](README.md) | 🇧🇷  **Português (BR)**

# everyday-causal-skills

<p align="center">
  <img src="repo-cover.png" alt="everyday-causal-skills" width="60%" />
</p>

> Use para pensar em problemas causais, planejar sua análise e implementá-la — conceitualmente ou em R e Python.

Plugin para o [Claude Code](https://docs.anthropic.com/en/docs/claude-code) voltado para inferência causal. Descreva um problema em linguagem natural e ele te guia na escolha do método, verificação de premissas, escrita da análise em R ou Python e stress-test dos resultados. Feito para profissionais que querem um workflow estruturado e para quem está aprendendo junto com [o livro](https://www.everydaycausal.com/).

## Início rápido

1. `/causal-planner` — Descreva seu problema em linguagem natural. O plugin identifica a questão causal e recomenda um método.
2. `/causal-did` (ou o método que se encaixar) — Percorra premissas, gere código de análise e rode verificações de robustez.
3. `/causal-auditor` — Faça stress-test da análise finalizada contra ameaças à validade.

## Como funciona na prática

Em um exemplo: uma empresa de varejo lançou um programa de fidelidade em 12 lojas e quer saber se as compras recorrentes aumentaram. Você digita `/causal-planner`, responde algumas perguntas sobre tratamento, resultado e estrutura dos dados, e o plugin recomenda diferenças em diferenças.

Você roda `/causal-did`. O plugin te guia por cinco etapas: confirmar o setup, testar tendências paralelas pré-tratamento, gerar código de estimação em R ou Python, rodar testes placebo e de robustez, e resumir o resultado com ressalvas. Se as tendências pré-tratamento divergirem, ele sinaliza o problema e sugere alternativas antes de seguir em frente.

## Skills

| Skill | Finalidade |
|---|---|
| `/causal-planner` | Descreva uma questão causal em linguagem natural e receba uma recomendação de método com plano de análise |
| `/causal-experiments` | Desenhe e analise RCTs e testes A/B — análise de poder, verificação de aleatorização, diagnóstico de balanceamento |
| `/causal-did` | Diferenças em diferenças com suporte para adoção escalonada, TWFE e estudos de evento |
| `/causal-iv` | Estimação por variáveis instrumentais com 2SLS, diagnóstico de instrumentos fracos e verificação de exclusão |
| `/causal-rdd` | Regressão descontínua sharp e fuzzy com seleção de bandwidth e testes de manipulação |
| `/causal-sc` | Controle sintético com ponderação de doadores, diagnóstico de ajuste pré-tratamento e testes placebo |
| `/causal-matching` | Matching por escore de propensão, IPW e estimadores duplamente robustos com diagnóstico de balanceamento |
| `/causal-timeseries` | Séries temporais interrompidas e CausalImpact com validação pré-período |
| `/causal-auditor` | Stress-test de qualquer análise finalizada contra cinco categorias de ameaças à validade |
| `/causal-exercises` | Pratique com dados simulados com ground truth conhecido e receba feedback sobre sua abordagem |

## Como funciona

Cada skill de método segue cinco etapas: setup, premissas, implementação, robustez e interpretação.

Salvaguardas em cada etapa:

- **Verification gate** — O plugin não interpreta resultados até ter visto o output real do seu código, não apenas o código em si
- **Severity flags** — Problemas fatais (como premissas violadas) bloqueiam o progresso; problemas sérios são sinalizados como ressalvas; atalhos de racionalização são apontados
- **Integração de métodos** — Cada skill sabe o que vem antes, o que vem depois e o que sugerir quando as premissas falham

## Instalação

Execute estes três comandos no prompt do Claude Code:

```bash
# 1. Registrar o marketplace
/plugin marketplace add RobsonTigre/everyday-causal-skills

# 2. Instalar o plugin (formato: plugin@marketplace)
/plugin install everyday-causal-skills@everyday-causal-skills

# 3. Ativar
/reload-plugins
```

Verifique com `/causal-planner` — se perguntar sobre seu problema causal, está tudo pronto.

Para atualizar:

```bash
/plugin marketplace update everyday-causal-skills
/reload-plugins
```

Para atualizar automaticamente ao iniciar: `/plugin` → aba **Marketplaces** → ative **auto-update**.

## Recursos

Este plugin ajuda você a pensar em problemas causais passo a passo, mas não substitui o seu julgamento. IAs podem cometer erros, especialmente ao interpretar premissas específicas do contexto. Para o raciocínio por trás de cada método, consulte o livro.

- [Everyday Causal Inference: How to Estimate, Test, and Explain Impacts with R and Python](https://www.everydaycausal.com/) — [Robson Tigre](https://www.robsontigre.com/)

Plugins complementares recomendados:

- [superpowers](https://github.com/obra/superpowers) — Ajuda a IA a pensar antes de agir, planejando e raciocinando sobre problemas em vez de pular direto para código ou respostas
- [claude-mem](https://github.com/thedotmack/claude-mem) — Captura informações relevantes entre sessões e as recupera quando necessário, dando à IA uma memória de trabalho

## Roadmap

- [ ] **`/causal-dag`** — Construção e crítica de DAGs, raciocínio sobre estratégias de identificação
- [ ] **`/causal-ml`** — Causal forests, X-learner, DML, efeitos heterogêneos de tratamento
- [ ] **`/causal-sensitivity`** — E-values, limites de Rosenbaum, viés de variável omitida (Cinelli & Hazlett)
- [ ] **`/causal-mediation`** — Efeitos diretos/indiretos, mediação natural e controlada
- [ ] **`/causal-discovery`** — Descoberta de estrutura causal a partir de dados (PC, FCI, score-based)
- [ ] **`/causal-trivia`** — Exercícios conceituais e trivia de inferência causal
- [ ] **`/causal-news`** — Resumos de artigos recentes de inferência causal
- [ ] **`/causal-report`** — Relatórios prontos para publicação com tabelas, figuras e resumos de métodos
- [ ] **Fundamentar skills em artigos seminais** — Vincular cada skill aos seus artigos seminais com resultados-chave e premissas
- [ ] **Otimização de tokens** — Comprimir arquivos SKILL.md para reduzir custo de tokens sem perder precisão
