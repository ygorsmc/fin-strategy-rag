# Rodada de correção — preenchedor

O revisor independente examinou a sua proposta (SHA-256 `5c0e72b9…31e0`) e deu
**APTA COM RESSALVAS**: dois erros de fato e duas divergências de julgamento. O
parecer, na íntegra, está em
`artefatos/preenchimento_decidir_v2_rank03b_2026-09-26/parecer_fase2_revisor.md`.
Leia só esse arquivo da pasta, além da sua proposta.

A sua proposta, idêntica à que você escreveu, está em
`artefatos/preenchimento_decidir_v2_rank03b_2026-09-26/proposta_v1_revisada.md`
(o scratchpad original foi apagado num reinício da sessão). Não a altere. Escreva a
versão corrigida em **um único arquivo novo**:
`artefatos/preenchimento_decidir_v2_rank03b_2026-09-26/proposta_v2.md`.

## Obrigatório: os dois erros

- **E1 (§5.1).** A frase de que o trimestre derivado entre métodos "não existia
  no painel para o qual a frase foi escrita" não tem fonte. O orquestrador
  conferiu no código: a derivação do 4T junta anual e nove meses sem olhar o
  demonstrativo (`src/dados_estruturados.py:1500–1504`; `chave_pareamento` sem
  demonstrativo em `:1325`) e grava o do anual (`:1486`). Troque pelo fato
  verificável que o revisor indica: o G0.1 que a v1 executou contava só grupos
  com mais de um demonstrativo (`scripts/auditar_rank03b_consumo_operacional.py:407–415`).
  Corrija no texto pronto e no julgamento.
- **E2 (§5.5).** O texto pronto diz que os casos não alcançados "continuam
  cobertos só pelo G0.3, no ativo". É falso para erro de escala consistente, sem
  transição. Corrija de modo coerente com o seu próprio "O que não se pode alegar".

## Ressalvas: incorpore ou justifique

Para cada uma, incorpore ou diga por que não:

- **§3.2:** "nenhuma das sete decisões altera G0.3" passa a "nenhuma faz o G0.3
  passar"; e o texto manda publicar quantos dos 132 saltos saem com as três
  companhias.
- **§5.1:** "o critério de refutação nunca foi cumprido" é ausência de teste, não
  evidência.
- **§5.5:** publicar também a fração de companhias do universo perdida, não só as
  observações.
- **§8.1 (opcional):** IC da lacuna por reamostragem de companhias, sem papel
  decisivo.
- **§12-bis:** (a) dizer o que prova a conta `1`; (b) corrigir a frase sobre
  "G0.3 e G0.5 lerem o veredito por documento"; (c) registrar o ativo de 140867
  como erro demonstrado conhecido, pendente de G0.3 por conta.
- **O1:** (a) depois de uma recusa, a execução termina, e nova execução exige
  registro do incidente e contrato novo; (b) incluir o comparativo nas formas
  enumeradas; (c) datar a retroatividade em 25–26/09; (d) o texto manda declarar
  no §11 do v2 as leituras de FCO por igualdade de 24 a 26/09 e o piso/teto
  calculado em memória em 25–26/09.
- **Transversal:** condicionar o congelamento também à resolução estrutural do
  G0 (os pins atuais descrevem um painel com G0 sabidamente reprovado), com o O1
  vigente até lá.

## Divergências: não mude as suas escolhas

Em §5.5 (C contra C+E) e §6.1 (deduplicação por companhia e q1), **mantenha a sua
escolha nesta rodada**. As duas vão ao responsável como alternativas. Em cada
item, apresente a alternativa do revisor com os argumentos dele e, separada, uma
resposta curta sua, com fonte.

## Regras

Valem as mesmas da primeira rodada: cegueira ao desfecho, O1 (sem DuckDB, RAD,
PDF ou valor de FCO), sem rodar scripts, sem alterar o estado do git, fonte para
cada afirmação. O único arquivo que você escreve é `proposta_v2.md`.

Ao fim do arquivo, acrescente a seção **"Registro da revisão"**: E1, E2 e cada
ressalva, com "incorporada" ou "não incorporada" e o motivo.

## Resposta final

Curta: as mudanças feitas e o SHA-256 de `proposta_v2.md`.
