# MEMORY.md

> Memória de trabalho entre sessões de agentes. Leia no início de toda
> tarefa; ao final, sobrescreva o que ficou desatual. Não é changelog — é
> contexto de handoff para o próximo agente. Regras de uso em
> [AGENTS.md](AGENTS.md#memória-entre-sessões--memorymd).

## Estado atual

- Etapas ativas (plano §2 do AGENTS.md): Etapa 1 (Gate G1 real), bloqueada
  por reautenticação no Azure CLI, e Etapa 3 (segunda leitura e congelamento
  do conjunto-padrão).
- Última etapa concluída: Etapa 2, Corpus (2026-07-15) — janela comum
  `2T2025`–`1T2026`, 20 documentos oficiais, hashes validados e 2.790 páginas.
- Primeira leitura da Etapa 3: 10 perguntas `dev` validadas no arquivo do
  pipeline e 45 candidatas `teste` no arquivo separado de curadoria. As
  candidatas ainda não estão congeladas nem autorizadas para medir métricas.

## Decisões e bloqueios em aberto

- `.env` ainda não existe. A assinatura ativa do Azure CLI é `Azure for
  Students`, mas as consultas de gerenciamento falharam com `AADSTS50078`
  (MFA expirada). Rodar `az login` e só depois executar novamente o gate;
  `resultados/gate.md` ainda NÃO é evidência final.
- O corpus usa os relatórios gerenciais oficiais substantivos, incluindo as
  demonstrações anexas, em vez de apresentações curtas. Por isso os PDFs têm
  20–312 páginas (2.790 no total), acima da estimativa inicial. Eles seguem
  ignorados pelo Git; manifesto, URL, data e SHA-256 são versionáveis.
- A auditoria cruzada da primeira leitura corrigiu ambiguidades de série e
  comparabilidade. A segunda leitura das 45 candidatas ainda deve ocorrer em
  outro dia; só então promover para `perguntas.csv` e registrar o congelamento.
- `sentence-transformers==5.6.0` foi adicionado ao `requirements.txt` (para
  a Etapa 6 — embeddings locais) mas **ainda não foi instalado** no venv.
  Rodar `pip install -r requirements.txt` antes de implementar
  `EmbeddingsLocal.embedar`.

## Próximo passo concreto

- Reautenticar com `az login`, escolher/configurar o ramo de provedor no
  `.env` local e rodar `python scripts/gate.py` para produzir o Gate G1 real.
- Em outro dia, fazer a segunda leitura descrita em
  `conjunto_padrao/README.md`; promover e congelar as 45 perguntas somente se
  valor, definição, unidade, página e classe de verificação forem confirmados.
