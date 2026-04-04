[🇺🇸  English](README.md) | 🇧🇷  **Português (BR)**

# everyday-causal-skills

<p align="center">
  <img src="repo-cover.png" alt="everyday-causal-skills" width="60%" />
</p>

> Use para pensar em problemas causais, planejar sua análise e implementá-la: conceitualmente ou em R e Python.

Plugin de inferência causal para agentes de IA. Descreva um problema em linguagem natural e ele ajuda você a escolher o método, verificar premissas, escrever a análise em R ou Python e validar os resultados. Para profissionais que querem um workflow estruturado e para quem está aprendendo junto com [o livro](https://www.everydaycausal.com/).

**Funciona com:** Claude Code · Gemini CLI · GitHub Copilot CLI · Codex CLI · Cursor

**Para quem é:** Qualquer pessoa que precise medir se algo realmente funcionou, como times de Marketing e growth; Product managers e analistas de BI; Cientistas de dados; Times de revenue e operações; Pesquisadores de políticas públicas; Estudantes e autodidatas.

## O que este plugin faz por você

O plugin funciona em cinco etapas, desde refinar a pergunta que você quer responder até escrever o relatório. Você pode começar por qualquer uma.

```
Descreva seu problema
→ Receba uma recomendação de método
→ Verifique premissas e estruture a análise
→ Teste a robustez dos resultados
→ Escreva o relatório executivo
```

**Exemplo:**

1. Digamos que uma empresa de varejo lançou um programa de fidelidade em 12 lojas e quer saber se as compras recorrentes realmente aumentaram. Você roda `/causal-planner`, responde algumas perguntas sobre tratamento, resultado e estrutura dos dados.
2. O plugin recomenda usar diferenças em diferenças como ferramenta para medir o impacto do programa.
3. Depois, `/causal-did` assume: verifica se as tendências pré-tratamento se sustentam, escreve o código de estimação em R ou Python e roda testes placebo e de robustez. Se algo falhar no caminho, ele avisa antes de você perder tempo com código que não vai se sustentar.
4. Com os resultados em mãos, `/causal-auditor` busca falhas na análise para que você não precise esperar um revisor fazer isso.

## Skills

| Skill | Finalidade |
|---|---|
| `/causal-planner` | Descreva uma questão causal em linguagem natural e receba uma recomendação de método com plano de análise |
| `/causal-experiments` | Desenhe e analise RCTs e testes A/B (análise de poder, verificação de aleatorização, diagnóstico de balanceamento) |
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

- **Verification gate.** O plugin não interpreta resultados até ter visto o output real do seu código, não apenas o código em si.
- **Severity flags.** Problemas fatais (como premissas violadas) bloqueiam o progresso; problemas sérios são sinalizados como ressalvas; atalhos de racionalização são apontados.
- **Method integration.** Cada skill sabe o que vem antes, o que vem depois e o que sugerir quando as premissas falham.

## Instalação

Escolha sua plataforma abaixo e clique para expandir as instruções.

<details>
<summary><h3>Claude Code</h3></summary>

Execute estes comandos no prompt do Claude Code:

```bash
# 1. Registrar o marketplace
/plugin marketplace add RobsonTigre/everyday-causal-skills

# 2. Instalar o plugin (formato: plugin@marketplace)
/plugin install everyday-causal-skills@everyday-causal-skills

# 3. Ativar
/reload-plugins
```

Para atualizar:

```bash
/plugin marketplace update everyday-causal-skills
/reload-plugins
```

Para atualizar automaticamente ao iniciar: `/plugin` → aba **Marketplaces** → ative **auto-update**.

</details>

<details>
<summary><h3>Gemini CLI</h3></summary>

```bash
gemini extensions install https://github.com/RobsonTigre/everyday-causal-skills
```

Para atualizar:

```bash
gemini extensions update everyday-causal-skills
```

</details>

<details>
<summary><h3>GitHub Copilot CLI</h3></summary>

```bash
copilot plugin install RobsonTigre/everyday-causal-skills
```

</details>

<details>
<summary><h3>Codex CLI</h3></summary>

```bash
git clone https://github.com/RobsonTigre/everyday-causal-skills.git ~/.codex/plugins/everyday-causal-skills
```

</details>

<details>
<summary><h3>Cursor</h3></summary>

```bash
git clone https://github.com/RobsonTigre/everyday-causal-skills.git ~/.cursor/plugins/everyday-causal-skills
```

</details>

<details>
<summary><h3>Instalação manual</h3></summary>

Se seu agente suporta o padrão SKILL.md mas não está listado acima, clone o repositório e aponte seu agente para o diretório `skills/`:

```bash
git clone https://github.com/RobsonTigre/everyday-causal-skills.git
```

</details>

---

Verifique com `/causal-planner`. Se perguntar sobre seu problema causal, está tudo pronto.

## Recursos

Este plugin ajuda você a pensar em problemas causais passo a passo, mas não substitui o seu julgamento. IAs podem cometer erros, especialmente ao interpretar premissas específicas do contexto. Para o raciocínio por trás de cada método, consulte o livro.

- [Everyday Causal Inference: How to Estimate, Test, and Explain Impacts with R and Python](https://www.everydaycausal.com/), por [Robson Tigre](https://www.robsontigre.com/)

### Recomendados para usuários do Claude Code

- [superpowers](https://github.com/obra/superpowers): ajuda a IA a pensar antes de agir, planejando e raciocinando sobre problemas em vez de pular direto para código ou respostas
- [claude-mem](https://github.com/thedotmack/claude-mem): captura informações relevantes entre sessões e as recupera quando necessário, dando à IA uma memória de trabalho

## Roadmap

- [ ] **`/causal-dag`**: construção e crítica de DAGs, raciocínio sobre estratégias de identificação
- [ ] **`/causal-ml`**: Causal forests, X-learner, DML, efeitos heterogêneos de tratamento
- [ ] **`/causal-sensitivity`**: E-values, limites de Rosenbaum, viés de variável omitida (Cinelli & Hazlett)
- [ ] **`/causal-mediation`**: efeitos diretos/indiretos, mediação natural e controlada
- [ ] **`/causal-discovery`**: descoberta de estrutura causal a partir de dados (PC, FCI, score-based)
- [ ] **`/causal-trivia`**: exercícios conceituais e trivia de inferência causal
- [ ] **`/causal-news`**: resumos de artigos recentes de inferência causal
- [ ] **`/causal-report`**: relatórios prontos para publicação com tabelas, figuras e resumos de métodos
- [ ] **`/causal-roi`**: avaliar o ROI de uma intervenção calculando o ROI causal (incremental), separando o impacto real do que teria acontecido de qualquer forma
- [ ] **Fundamentar skills em artigos seminais**: vincular cada skill aos seus artigos seminais com resultados-chave e premissas
- [ ] **Otimização de tokens**: comprimir arquivos SKILL.md para reduzir custo de tokens sem perder precisão
