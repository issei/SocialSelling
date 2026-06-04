"""Aprendizado por feedback (ADR-007).

Loop human-in-the-loop: a operadora marca leads com like/dislike; um modelo
treinado determinístico reajusta os pesos do score. Camada de APRESENTAÇÃO
(opera sobre os componentes de `LeadCard.score`), nunca sobre evidências/inferências.
"""
