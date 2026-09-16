# Parecer sobre a correção do instrumento B-DFC-01J

**Data:** 2026-09-11. **Objeto:**
[pacote de verificação de 10/09](verificacao_correcao_b_dfc_01j_2026-09-10.md)
e [relatório da implementação](correcao_instrumento_b_dfc_01j_2026-09-10.md).
**Referência:** [revisão original, F1–F12](revisao_independente_b_dfc_01j_2026-09-10.md).

## Veredito

**Correção parcialmente confirmada; não considero o item 1 concluído.**
As duas contraprovas centrais de F1 foram resolvidas e o programa não autoriza
treino sobre a população atual. Entretanto, F7 e F8 permanecem parcialmente
abertos, G1 ainda aceita horizontes fora do contrato e a disponibilidade dos
antecedentes de B1/B2 não é verificada. Há também uma certificação indevida de
independência e números de poder inválidos ainda publicados pela sensibilidade.

Não é motivo para restaurar o J antigo ou interromper a investigação documental.
É motivo para corrigir os resíduos antes de declarar o auditor pronto para
certificar uma população reconstruída. **Não houve treino deste candidato.**

## 1. O que foi efetivamente verificado

- Leitura integral de AGENTS.md, MEMORY.md, pacote e relatório da correção;
  inspeção das funções alteradas, consumidores, testes e artefatos.
- **Suíte completa: 1.953 passed, 30 warnings, zero skips, em 111,22 s.**
- As duas classes de contraprovas indicadas pelo pacote:
  **12 passed em 0,07 s**.
- `executar()` do auditor e da sensibilidade, em memória, reproduziram os
  respectivos JSONs gravados. Não foram invocados os `main()` que os reescrevem.
- O piloto mantém 25 pacotes: 24 não identificados e um sem fonte; zero J pontual
  ou limitado. A extensão mantém 198 registros de J, todos não identificados;
  zero observações elegíveis e zero alvos no auditor. G0 reprova, e os outros
  cinco gates permanecem no relatório como não decidíveis/reprovados.
- A etiqueta de unidade de **198/198** registros J coincide agora com os fatos
  de sua fonte/período. Isso confirma a correção da exportação, não do consumidor.
- Identidades atuais: 12 semestrais e 12 de nove meses conferidas/independentes;
  17 anuais não verificáveis/não independentes. Não reapareceu o certificado 15/15.

Houve um revisor independente para o auditor de prontidão. Ele enviou achados
preliminares e foi interrompido por limite de uso antes do parecer final. **Não
há aprovação final desse agente.** Os achados utilizados abaixo foram reproduzidos
também pela sessão principal; nenhum depende apenas de sua mensagem.

Não foram modificados código, testes, dados, PDFs, corpus ou gates nesta
conferência. Não houve API paga nem acesso ao holdout. Foram escritos apenas
este parecer e a atualização de MEMORY.md. As alterações pré-existentes no
worktree foram preservadas; não houve commit ou merge.

## 2. Resíduos que impedem considerar a correção encerrada

As prioridades abaixo são de **confiabilidade do instrumento**, não de uma
implantação em produção. Os casos sintéticos não representam novos resultados
econômicos nem execução do holdout.

### C1 — P1: F7 continua atribuindo associação máxima a uma variável constante

**Fonte:** [auditor](../scripts/auditar_prontidao_b_dfc_01j.py),
`amplitude_por_quintis`, linhas 597–633; teste em
[test_prontidao_b_dfc_01j.py](../tests/test_prontidao_b_dfc_01j.py), linha 237.

Reprodução direta:

```python
from scripts import auditar_prontidao_b_dfc_01j as a
a.amplitude_por_quintis([1.0]*50, [0,1]*25)[0]       # 0.0: caso coberto
a.amplitude_por_quintis([1.0]*50, [0]*25+[1]*25)[0]  # 1.0: defeito persiste
```

É a mesma distribuição de pares valor/evento, apenas reordenada. Trocar desempate
pelo evento por desempate pela posição original removeu o uso **explícito** do
rótulo, mas a posição pode carregar emissor, tempo ou classe. A variável constante
continua incapaz de ordenar qualquer observação; os quintis foram criados pela
ordem das linhas, não pela variável auditada.

**Necessário:** política para valores empatados que não fabrique quintis
informativos, incluindo o caso sem variação, e contraprova de invariância à
permutação de linhas. Randomizar empates não demonstra essa invariância. Não
alterar o limiar para acomodar o resultado.

### C2 — P1: F8 corrigiu a etiqueta, mas não a aritmética do auditor

**Fontes:** auditor, `Observacao` (71–86), `carregar_populacao` (93–159),
`montar_alvos` (206–229) e `teste_t1` (636 em diante).

O loader ainda descarta `unidade` e armazena os limites numéricos sem conversão.
Em uma série sintética do mesmo emissor, **1.000 milhares → 1 milhão** representa
o mesmo montante econômico. Passando os dois registros pela função real de carga,
com fonte substituída apenas em memória, o alvo calculado foi:

```text
J-base = 1000; J-futuro = 1
y = −6,907755278982137     # deveria ser 0
```

Entre emissores, os quintis de T1 também continuam misturando milhares e milhões.
Não há efeito sobre um `y` real nesta rodada, pois a população está vazia; não
afirmo que a série histórica tenha sofrido essa troca de unidade dentro do banco.
O defeito, porém, está no caminho que será reutilizado quando houver dados.

**Necessário:** normalizar unidades antes de ordenar ou dividir, ou rejeitar
explicitamente combinações incompatíveis; preservar unidade/procedência no
contrato carregado. A guarda de unidades mistas dentro de `construir_j` não
protege divisões entre períodos nem comparações entre bancos.

### C3 — P2: G1 exige um trimestre posterior, não o primeiro trimestre posterior

**Fonte:** auditor, `horizonte_contratual_respeitado`, linhas 187–203,
e `gate_g1`, linhas 275–314.

Para D = **02/05/2024**, reproduzi helper e G1 com publicações em ordem:

| Trimestre-alvo | Helper e G1 | Contrato q(D) |
|---|---|---|
| 2024T2 | Reprovam | Correto: já começou |
| 2024T3 | Aprovam | Correto: primeiro trimestre inteiro posterior |
| 2024T4 | **Aprovam** | Incorreto: pulou q(D) |
| 2025T1 | **Aprovam** | Incorreto: pulou q(D) |

Adiar a reconstrução da população para um protocolo novo é justificável.
Entretanto, uma função chamada “horizonte contratual respeitado” precisa conferir
**igualdade com q(D)**, não apenas que o início seja maior que D. Isso pode ser
testado sem mudar a população antiga ou medir novo desempenho.

### C4 — P2: calendário corrigido de B2 não resolve disponibilidade do histórico

**Fonte:** auditor, `previsoes_dos_baselines`, linhas 351–401.

Confirmei que B2 agora exige os quatro trimestres anteriores e recusa buracos.
Mas os antecedentes são obtidos de toda a lista de alvos, ignorando suas datas
de disponibilidade. B1 tem a mesma lacuna.

Reprodução: quatro antecedentes 2023T1–T4 com `y = 0,2/0,4/0,6/0,8`, cujo
resultado completo só fica disponível em **01/01/2025**. Para uma decisão em
**02/05/2024**, a função emite **B1=0,2 e B2=0,5**. A informação não existia em D.
Não foi observado backtest real contaminado nesta rodada vazia: é uma contraprova
da função e um requisito ainda aberto para o desenho point-in-time.

Também permanece a mistura declarada de suportes no poder. Na contraprova com
três bancos na população e baseline eleito cobrindo só um, G3 reporta **três
emissores independentes**, embora `trimestres_por_emissor` contenha apenas esse
um; calcula “emissores necessários = 0”. Hoje `B3_EXECUTADO=False` impede a
aprovação, mas não torna esses campos corretos.

**Necessário:** histórico conhecido em D, elegibilidade separada da mensurabilidade
futura e contagem de unidades efetivamente usadas na comparação. O redesign de
poder pode continuar adiado, desde que seu cálculo inválido não certifique nada.

### C5 — P2: F11 verifica as parcelas, mas ignora se o acumulado é derivado

**Fonte:** [extrator](../scripts/piloto_bancos_dfc.py),
`conferir_identidade_trimestral`, linhas 3057–3067.

A marcação verifica `escolhido[:-1]`, excluindo o acumulado da verificação de
origem. Contraprova mínima na mesma fonte: T1=−100 e T2=−100 como comparativas,
S1=−200 com `origem_periodo="derivada"`. Resultado real da função:

```text
confere=True; independente=True; motivo_nao_independente=None
```

Uma soma comparada a um acumulado derivado dela não é verificação independente.
Esse exemplo não ocorre nos 51 registros de conferência atuais e o gerador
atual deriva trimestres, não semestres: é uma lacuna do contrato da função,
não evidência de que as 24 conferências presentes sejam inválidas.

Além disso, o resumo da extensão conta `confere=True` sem filtrar `independente`
(extrator, linhas 3366–3370); G0 recebe essa contagem sem distinguir as duas
classes. Hoje coincidem. Uma futura identidade que feche por construção pode
voltar a ser contabilizada como conferida no resumo.

**Necessário:** verificar todos os operandos, propagar linhagem quando houver
derivação e separar contagens aritméticas de certificações independentes.

### C6 — P2: F3 não está somente latente; a sensibilidade ainda publica 16/60

**Fontes:** [sensibilidade](../scripts/sensibilidade_rubricas_suspeitas_b_dfc_01j.py),
`_poder` (106–155), `cenario_volatilidade` (251–282), `executar` (286–315);
[JSON atual](../artefatos/b_dfc_01j/prontidao/sensibilidade.json).

O pacote declara expressamente F3 adiado. Não cobro nesta correção a implantação
do novo método estatístico. Mas é incorreto dizer que a conta ficou inócua por
não haver população: os cenários de **volatilidade** continuam produzindo-a.

| Cenário atual | `decidivel` | `ressalva` | Emissores necessários |
|---|---|---|---:|
| `volatilidade_conforme` | **true** | **null** | **16** |
| `volatilidade_estado_anterior_nao_conforme` | **true** | **null** | **60** |

Reproduzi esses campos em memória. Logo, “~16 emissores deixaram de existir como
medições” não descreve a saída atual. O aviso “NÃO é J” distingue o estimando,
mas não avisa que a fórmula **não estima poder para ganho pareado**. Os testes
da sensibilidade ainda exigem que o número de emissores caia e permaneça acima
de três, preservando uma conclusão já invalidada pela revisão original.

**Necessário agora:** retirar esses campos da decisão/saída vigente ou identificá-los
explicitamente como cálculo invalidado, sem `decidivel=True`. Preservar a perda
descritiva não exige apresentar sua dispersão como poder. Isso não requer escolher
um novo limiar nem implementar o experimento futuro.

## 3. Avaliação dos sete julgamentos declarados pelo autor

| Item do pacote | Parecer |
|---|---|
| 4.1: `limite_demonstravel=False` em todas as rubricas | **Aceitável provisoriamente.** Ausência de prova não vira limite. Não demonstrei over-correction documental nesta conferência; adjudicar BB é tarefa separada. Sinal líquido credor/devedor, sozinho, não identifica sinais dos componentes. |
| 4.2: limites 0/0 para não identificado | **Representação problemática.** Os consumidores atuais recusam pelo status, mas os 198 registros exportam `largura_relativa="0"`. Isso não representa precisão demonstrada. Preferir ausência explícita dos limites/largura com schema versionado; não chamar automaticamente a soma incluída de piso sem hipóteses de sinal. |
| 4.3: não reconstruir a população | **Escopo adequado.** Corrigir o verificador q(D) ainda é necessário (C3); a população nova fica para protocolo novo. |
| 4.4: eleger no suporte comum e medir poder no próprio | **Não resolve uma comparação pareada.** Pode descrever cobertura própria separadamente, mas não usar a mistura como poder/certificação (C4). |
| 4.5: adiar F3 | **Aceitável como dívida, não como resultado válido.** A saída atual da sensibilidade exige quarentena explícita (C6). |
| 4.6: `B3_EXECUTADO` manual | **Bloqueia hoje; integração futura incompleta.** A aprovação deverá depender de previsões B3 reais, datadas, com cobertura e suporte comum, não apenas da flag. |
| 4.7: derivado não herda limite | **Cautela aceitável.** Dois intervalos acumulados válidos não dão automaticamente intervalo trimestral válido da mesma forma. Propagar limites exige comparabilidade e hipóteses; não basta que os acumulados sejam devedores. |

Os zeros de 4.2 são sentinelas documentadas, não evidência de J=0. A limitação
de schema não foi criada totalmente nesta onda, mas agora se estende aos 198
registros. Ser conservador ao recusar o rótulo não exige publicar largura zero.

## 4. As cinco alterações de testes enfraqueceram o contrato?

**Não encontrei redução de limiar ou retirada das asserções contábeis centrais
nos cinco casos indicados.** Corrigir um teste que exigia um intervalo matematicamente
inválido é legítimo; não se deve perpetuar o defeito para manter o teste intacto.
Isso é distinto de certificar que toda a suíte anterior permaneceu igual.

Os três arquivos são **não rastreados pelo Git nesta branch**: `git ls-files
--error-unmatch` não os encontra. Portanto, não há no HEAD uma versão anterior
que permita auditar um diff integral dessa correção. Comparei o contrato descrito
na revisão anterior com os testes presentes; não afirmo uma comparação histórica
linha a linha de todos os testes.

| Caso indicado | Avaliação |
|---|---|
| Residual com/sem limite | A substituição é justificada; os casos válido, inválido e cancelamento permanecem distintos. A fixture válida declara o limite; não prova que exista tal rubrica na fonte real. |
| P2 sem total | Separar P2 de identificação é correto. O caso positivo adicional testa fechamento com J não identificado. A condição sem total tem exemplos atuais, mas convém travar sua não vacuidade em fixture própria. |
| Sensibilidade: retirada de G2 1,0464 | Retirar a asserção sobre número sem validade é correto. O substituto lê apenas JSON congelado: sozinho não detecta regressão na função `cenario_intervalo`. Acrescentar contraprova sintética executando a função. |
| Sensibilidade: retirada da folga 48× | Também justificada. “Um emissor restante” é descrição do snapshot, não contrato universal de uma implementação correta. |
| Exclusão documentada do Bradesco | Exclusões nomeadas, valor positivo excluído e fechamento exato continuam exigidos; a mudança de status é coerente com F1. Isso não comprova a antiga atribuição causal a câmbio que ainda aparece no docstring. |

Os testes novos de F7 e F8 são insuficientes, como C1/C2 demonstram. Assim,
“1.953 passaram” confirma a execução da suíte, **não a eliminação de todos os
defeitos declarados**. Não houve alteração de testes por esta revisão.

## 5. O que está confirmado e o próximo passo

**Confirmado:** F1 recusa as duas entradas sem limite; intervalos são condicionados
à declaração; unidades mistas na soma de J levantam erro; B2 exige quatro períodos;
eleição inicial usa suporte comum; T2 não informativo reprova; B3 ausente bloqueia
G3 no estado atual; falta de população não apaga os gates já medidos; o veto
continua em G0 e o denominador documental de 25 pacotes foi preservado.

**A fechar nesta onda:** C1/C2, contrato exato de horizonte, disponibilidade de
históricos (ou marcação inequívoca de que os baselines ainda não são PIT), proteção
da independência e quarentena dos números de poder inválidos. A representação
de não identificação também precisa de contrato explícito de ausência, não de
precisão zero.

Depois disso, pode-se encerrar a correção do instrumento e continuar o **piloto
documental de subordinadas**. Esse piloto também pode inventariar fontes enquanto
as correções são feitas, desde que não use o auditor pendente como certificado.
Novo estimando, M0/M1, benchmark econômico e treino exploratório continuam sendo
etapas distintas. O holdout não participa dessas iterações.

## 6. Reprodução sem alterar os artefatos

Na raiz do repositório:

```bash
CREWAI_STORAGE_DIR="$(mktemp -d /tmp/bdfc-verificacao-crewai.XXXXXX)" .venv/bin/python -m pytest -q --tb=short
.venv/bin/python -m pytest -q tests/test_prontidao_b_dfc_01j.py::TestContraprovasDaRevisaoIndependente tests/test_piloto_bancos_dfc.py::TestContraprovasDaRevisaoIndependente
```

Contraprovas sem arquivo temporário de dados, treino ou escrita no painel:

```bash
.venv/bin/python - <<'PY'
import io, json, math
from unittest.mock import patch
from pathlib import Path
from scripts import auditar_prontidao_b_dfc_01j as a
from scripts import sensibilidade_rubricas_suspeitas_b_dfc_01j as s

root = Path('artefatos/b_dfc_01j')
assert a.executar() == json.loads((root/'prontidao/gates.json').read_text())
assert s.executar() == json.loads((root/'prontidao/sensibilidade.json').read_text())
print('C1:', a.amplitude_por_quintis([1.0]*50, [0]*25+[1]*25)[0])

def alvo(cd, base, futuro, y=.1, db='2024-05-02', df='2025-02-01'):
    return a.Alvo(cd,base,futuro,y,y,y,1000.,1000.*math.exp(y),db,df,0.)
print('C3:', [(q, a.gate_g1([alvo('A','2024T1',q)])['aprovado'])
             for q in ['2024T2','2024T3','2024T4','2025T1']])

rows = [dict(cd_cvm='A', periodo=q, status='identificado',
    fechamento_confere=True, base_temporal='original', disponivel_em=d,
    limite_inferior=str(v), limite_superior=str(v), unidade=u)
    for q,d,v,u in [('2023T1','2023-05-01',1000,'milhares_de_reais'),
                    ('2023T2','2023-08-01',1,'milhoes_de_reais')]]
class SerieMemoria:
    def is_file(self): return True
    def open(self, **kwargs):
        return io.StringIO('\n'.join(json.dumps(r) for r in rows))
with patch.object(a, 'SERIE', SerieMemoria()):
    obs,_ = a.carregar_populacao()
    ys,_ = a.montar_alvos(obs)
    print('C2: y para mesmo montante real =', ys[0].y_centro)

hist = [alvo('A',f'2023T{q}',a.proximo_trimestre(f'2023T{q}'),q*.2,
             db='2023-05-01',df='2025-01-01') for q in [1,2,3,4]]
current = alvo('A','2024T1','2024T3',.15,df='2024-11-01')
b = a.previsoes_dos_baselines(hist+[current])
print('C4: B1/B2 com histórico ainda não publicado =',
      b['B1'][('A','2024T1')], b['B2'][('A','2024T1')])
for nome in ['volatilidade_conforme','volatilidade_estado_anterior_nao_conforme']:
    c = s.executar()[nome]
    print('C6:', nome, c['decidivel'], c['ressalva'], c['emissores_necessarios'])
PY
```

Saídas relevantes: C1=1,0; C3=False/True/True/True; C2=−6,907755278982137;
C4=0,2/0,5; C6=True/None/16 e True/None/60. São falhas de contrato
reproduzidas, **não resultados que devam ser aprovados por novos testes**.
