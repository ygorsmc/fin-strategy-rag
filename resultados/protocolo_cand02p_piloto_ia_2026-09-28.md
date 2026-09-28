# Protocolo — CAND-02-P: piloto de viabilidade do redline, com rótulo de IA

**Data:** 2026-09-28. **Fixado antes do primeiro rótulo**, no commit que
introduz este arquivo. Nenhum evento tinha sido gerado nem rotulado.

**Decisão do responsável (28/09).** Fazer a anotação com IA para chegar rápido
ao primeiro treino, e aperfeiçoar o processo depois: "De que adianta a gente
fazer perfeito e chegar lá frente e descobrir não ser viável?". Ele escolheu
dois leitores, um agente Claude com contexto limpo e o Gemini via API (opt-in
de API paga dado nessa escolha), e os 24 pares de releases.

## 1. Pergunta e o que a resposta pode dizer

Um ranqueador **treinado** prioriza as mudanças entre releases consecutivos
melhor que o B1 determinístico, sob o mesmo universo de eventos?

**O rótulo é de IA, e isso torna a resposta assimétrica:**
- **"Não" é confiável.** O rótulo de IA tende a favorecer modelos semânticos,
  e o M é treinado para imitá-lo. Se mesmo assim o M não vencer o B1, com
  rótulos consistentes, é inviável.
- **"Sim" é só promissor.** Pode ser o viés do rótulo. Só vira evidência com a
  conferência humana da seção 6.

**Relação com o CAND-02 congelado:** é outro experimento. O CAND-02 continua
INDECIDÍVEL, e este piloto não o valida. O piloto expõe os pares de
desenvolvimento e de teste do CAND-02; um CAND-02 humano futuro exige
pré-registro próprio, que declare essa exposição. O embargo (3T→4T) não é
usado.

## 2. Pares e divisão

Oito emissores: BTG, ITAU, BRADESCO, SANTANDER e BB (`corpus/metadados.csv`),
mais BMG, ABC e BANESTES (`corpus/expansao/`, só material de teste; nada entra
no índice nem em `metadados.csv`, AGENTS.md §3.15).

| Papel | Pares | Uso |
|---|---|---|
| treino | 2T2025 → 3T2025, oito pares | rótulos para treinar o M |
| embargo | 3T2025 → 4T2025 | não usado |
| teste | 4T2025 → 1T2026, oito pares | único resultado |

Treino e teste não compartilham documento. A unidade de inferência é o par.

## 3. Evento e braços

**Evento:** uma mudança entre os dois releases de um par.
- Em texto, a unidade é a sentença, que é a afirmação atômica.
- Em tabela, a unidade é a linha, com título, cabeçalho, unidade e períodos.
- A operação é adição, remoção ou alteração.
- Não é evento:
  - texto idêntico em outra posição (movimento);
  - cabeçalho e rodapé repetidos;
  - número de página;
  - artefato de OCR.

Os quatro braços **só ordenam o mesmo universo**, gerado uma vez pelo
extrator:
- **B0:** massa de tokens alterados, com desempate por página.
- **B1:** lexicográfico do CAND-02, em quatro níveis:
  1. número acima da triagem (50 bp em razão, 20 bp em crédito, 10% em
     valor), ou mudança de sinal, negação ou modal;
  2. categoria sensível;
  3. adição ou remoção integral;
  4. massa e distância de edição.
- **C, pré-treinado e congelado:** `bge-m3` via Ollama, pelo digest do
  modelo. Ordena pela maior similaridade com as âncoras fixadas no código antes
  dos rótulos, com desempate pelo B1.
- **M, o primeiro treino:** `HistGradientBoostingRegressor` do scikit-learn.
  - Os hiperparâmetros ficam fixados no código, sem busca.
  - A semente é `20260928`.
  - As features vêm do B1, do C e da forma do evento.
  - O alvo é o ganho médio dos dois leitores.
  - O treino usa só os pares de treino.

## 4. Pool e rotulagem

- **Treino:** por par, a união do top-20 de B0, B1 e C, mais amostra
  aleatória do restante até 120 eventos, ou todos, se houver menos.
- **Teste:** é montado só depois de o M estar congelado. Por par, a união do
  top-20 de B0, B1, C e M, mais aleatórios até 120.
- **Pacotes cegos:** ordem aleatória, sem braço e sem score. Cada evento traz
  o trecho antes e depois, a página e a seção; em tabela, também o título, o
  cabeçalho e os períodos.
- **Leitor Claude:** agente de contexto limpo. Recebe só a rubrica, o pacote e
  os dois documentos de OCR inteiros. Não lê código nem artefatos do piloto.
- **Leitor Gemini:** `gemini-3.5-flash-lite`, com temperatura 0 e os dois
  documentos de OCR inteiros no contexto. Os lotes têm até 40 eventos.
  **Teto de US$ 15 no piloto inteiro:** o script para antes de ultrapassá-lo.
- **Rubrica:** a do CAND-02, sem alteração:
  - nota 0, 1 ou 2, com motivo e ação;
  - marca de evento crítico;
  - `nao_julgavel_ocr_ou_estrutura`.
- **Nota final:** a média dos dois leitores. O ganho do nDCG é a média dos
  ganhos 0/1/3. Um evento que algum leitor declare não julgável sai das
  métricas e é contado.
- **Tipo de leitor:** todo rótulo guarda `tipo_leitor = ia`. Nenhum é
  promovido a gabarito humano.

## 5. Paradas, na ordem, sobre o pool de teste

1. **Confiabilidade.** α de Krippendorff ordinal entre os leitores < 0,67, ou
   mais de 5% de não julgáveis → **INDECIDÍVEL**. O rótulo não sustenta nem
   "sim" nem "não".
2. **Densidade.** Menos de 30 eventos com nota final ≥ 1,5 → **INDECIDÍVEL**.
3. **Teto do B1.** Macro nDCG@10 do B1 ≥ 0,95 → **INVIÁVEL**, porque não há o
   que treinar.
4. **Desafio.** O M precisa cumprir três condições ao mesmo tempo:
   - Δ macro nDCG@10 ≥ +0,10 e Δ macro nDCG@20 ≥ +0,05 sobre o B1;
   - nDCG@10 estritamente maior em pelo menos 7 dos 8 pares (teste do sinal
     unilateral, p ≈ 0,035);
   - o top-20 do M não pode trazer menos eventos críticos que o do B1, com
     crítico marcado pelos dois leitores.

   Se faltar qualquer uma → **INVIÁVEL**. Se cumprir as três →
   **PROMISSOR**.

O C e o B0 entram publicados como comparação, sem decidir nada.

## 6. Se PROMISSOR: conferência humana

Uma amostra de 60 eventos do pool de teste é sorteada com semente fixa,
estratificada por par. O responsável a rotula às cegas, num pacote sem as notas
da IA, e não abre os rótulos antes disso.
- α entre humano e nota final da IA ≥ 0,67 → "promissor, rótulo de IA
  conferido por amostra humana".
- Abaixo disso → INDECIDÍVEL.

Em nenhum caso algo entra no produto.

## 7. Ordem de congelamento

1. Este protocolo.
2. Extrator, B0, B1 e C, com os testes.
3. Prompt e rubrica dos leitores.
4. Rótulos do treino.
5. M treinado.
6. Pool de teste e rótulos.
7. Métricas.

Cada passo é commitado antes do seguinte. Depois de ver um rótulo de teste,
nada acima muda. Se algo precisar mudar, é outro piloto.
