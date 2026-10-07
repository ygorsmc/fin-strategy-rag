# Rótulos descartados — fora de qualquer medição

## `claude/teste/BRADESCO_4T2022_1T2023.jsonl` (07/10)

**Motivo: quebra de procedimento, não conteúdo.** Ao ser retomado depois do
limite de sessão, o leitor listou a pasta temporária compartilhada da sessão e
abriu scripts auxiliares de outros leitores (`rot1.py`, `rot2.py`, `rot3.py`,
`gravar.py` e outros). Esses scripts continham rótulos de outros pares de
teste: BANESTES, BMG, ITAU e BB. O próprio leitor declarou isso no relatório,
e a auditoria das chamadas de ferramenta
(`scripts/cand02p_qc.py`, "rascunho indeterminado") confirmou a leitura.

**Decisão:** a leitura foi descartada e o par foi rotulado de novo por um
leitor novo, com pasta temporária exclusiva. A decisão veio antes de qualquer
métrica de teste e foi disparada pela violação, não pelas notas. As notas
descartadas nem destoavam: 8 notas 2 em 120, dentro da faixa do Bradesco.

**Alcance:** reauditadas as 35 transcrições de leitores do v3, de treino,
teste e releitura. Este é o único caso de leitura de arquivo alheio na pasta
temporária. A releitura do SANTANDER 4T2018→1T2019 listou a pasta quando ela
estava vazia ("total 0").

**Prevenção:** os leitores lançados depois disso usam uma pasta temporária
própria (`/tmp/cand02p_v3_<PAR>/`) e são proibidos de abrir qualquer outra
coisa em `/tmp`.

**Depois da releitura, só como descrição:** a leitura descartada e a do leitor
novo concordam em α ordinal 0,866 e acordo exato de 0,933 (120 itens). O
contato com rótulos de outros pares quase não mudou as notas deste par. A
troca continua valendo, porque foi decidida pela violação, não pelo efeito.
