"""Sensor Apollo.io — busca firmografica + enriquecimento incremental (ADR-004).

Apollo entra como 2o sensor OPCIONAL (opt-in via `[apollo].enabled`), explorando a
assimetria de custo do tier gratuito: People Search (0 credito) faz a descoberta;
Org/People Enrichment (credito escasso) ficam reservados para o topo do ranking.

Camadas preservadas (CLAUDE.md §3.1): a resposta Apollo vira `ObservedEvidence`
(camada 1), nunca inferencia. A inferencia segue nascendo no M2/Gemini.
"""
