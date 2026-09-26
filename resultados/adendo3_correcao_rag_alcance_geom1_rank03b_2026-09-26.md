# Adendo 3 à correção RAG — declaração completa do limite do sinal

Data: 2026-09-26. Escrito antes de editar, depois da reconferência do adendo 2:
**FECHADO COM RESSALVAS**. B1, B3, B4 e B5 estão fechados. Resta um achado BAIXA: a
declaração do B2 está incompleta. Parecer na íntegra em
`artefatos/correcao_rag_alcance_geom1_rank03b_2026-09-25/conferencia_3/parecer_auditor.md`.
Valem o escopo e as proibições do contrato da correção e dos adendos 1 e 2, que
seguem fixados por hash. O O1 continua valendo.

## C1 — o limite, dito inteiro, na saída

O campo `limite` da busca passa a dizer, sem dígitos:

- um sinal separado do número por caractere ignorável fora de formatação e controle
  (seletor de variação, combinante de grafema, preenchedor), ou posto antes de
  moeda com espaço interno, **se perde, e o número pode casar como positivo**;
- um ignorável desses **dentro** do número parte o token, e **o prefixo pode casar**;
- nenhum desses caracteres aparece nestas notas; **corrigir isso é pré-condição para
  usar o instrumento em notas de outros emissores**.

O relatório passa a dizer o mesmo. O adendo 2 não é alterado.

## C2 — o comportamento declarado fica fixado em teste

Um teste de caracterização prende o comportamento atual nos casos do parecer
(`−͏1.234`, `(︀1.234︀)`, `-ㅤ1.234`, `-R $ 1.234` casam positivo; `1.234.͏567` casa o
prefixo) **junto** com a presença de cada efeito no texto do `limite`. Quem corrigir
o limite terá de mudar teste e declaração juntos: o teste não aprova o defeito, impede
que a declaração fique para trás.

## Execução

Código e testes do adendo 2 preservados em `codigo_adendo2/`. Em `adendo3/`: busca,
reconferência, contraprovas da conferência de 25/09, comparação com 24/09, diferença
para a busca do adendo 2, mutação e suíte. **Esperado, fixado antes de rodar:** a busca
difere da do adendo 2 só no `limite` e na identidade; tudo o mais igual; todas as
mutações morrem. Scripts de evidência rodam com `PYTHONDONTWRITEBYTECODE=1` (o
bytecode que a rodada do adendo 2 deixou em `adendo/__pycache__/` foi removido; não
tinha hash registrado e o git o ignora).
