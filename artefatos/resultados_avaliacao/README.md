# Validade dos artefatos de avaliação

`metricas_dev.json`, o checkpoint histórico e o log de 2026-07-15 foram
produzidos antes das guardas de avaliação v3. As métricas antigas estão
explicitamente invalidadas e não podem ser copiadas para o README ou usadas
como resultado do projeto. O checkpoint e o log permanecem somente como trilha
histórica; o fingerprint v3 impede seu reaproveitamento automático.

`respostas_cacheadas.json` fica vazio até existirem perguntas `teste`
congeladas, índice reconstruído e uma execução integral concluída sem erros.
Rodadas `dev` escrevem em `respostas_cacheadas_dev.json` e nunca substituem o
cache final.
