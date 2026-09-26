# Pendências GEOM-1 — adendo após revisão independente

Data: 2026-09-26. Antes da correção dos achados do auditor-conformidade.
O contrato de pendências (`97a7d537…`) permanece íntegro e governante.

## AP1 — prefixo monetário não incorpora sufixo de palavra

Achado MÉDIA: o laço novo incorporava as letras finais de `TOTAL` e `ATIVO`
como prefixo de `R$`/`US$`/`$`, gerando falsa ambiguidade. O laço deve
examinar **palavras maiúsculas inteiras**, não cortá-las para caber no limite
de três letras. Se a próxima palavra não cabe, para sem consumi-la nem o
espaço que a separa da moeda. Os casos `TOTAL R$`, `ATIVO US$` e `TOTAL $`
continuam limpos; `R $`, `U S $` e interferências internas continuam ambíguos.
Uma sequência curta como `PL R$` ainda pode ser ambígua: cabe na gramática
conservadora de três letras fragmentadas; não se promete resolver semântica
de todos os rótulos por expressão lexical.

Contraprovas adicionais: rótulos inteiros maiúsculos longos, moedas com e sem
espaços, sinais e parênteses, além dos casos P1 anteriores. Não muda o
inventário congelado nem relaxa recusa de sinal.

## AP2 — sintaxe CSV estrita também no campo sem aspas

Achado BAIXA: `csv.DictReader(strict=True)` aceita uma aspa literal solta no
meio de um campo sem aspas. Isso contradiz a promessa de recusar sintaxe
inválida. Uma verificação lexical anterior ao DictReader deve exigir:

- aspa de abertura somente no início do campo;
- aspa literal dentro do campo delimitado representada por duas aspas;
- depois de fechar aspas, somente delimitador, fim de registro ou de arquivo;
- fim de arquivo não pode ocorrer dentro do campo delimitado.

Quebras de linha e vírgulas dentro de campo delimitado continuam válidas.
Mensagens de erro não reproduzem o conteúdo do campo. Testes exercitam a
recusa antes da validação semântica e o controle positivo com aspas
corretamente escapadas. O esquema e a exceção histórica de P2 não mudam.

## Reconferência

Preservar código pré-correção do parecer, executar contraprovas e suíte final,
registrar hashes novamente e solicitar reconferência ao mesmo auditor.
Continuam proibidas busca/reconferência real com FCO, medição de alvo,
alteração dos sete protegidos e aprovação implícita do v2.
