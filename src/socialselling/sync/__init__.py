"""Pacote motor-side de sincronização com o portal (ADR-010).

CLIs `publish` e `pull-feedback` conversam com o portal EXCLUSIVAMENTE via HTTP.
O motor nunca acessa o banco. HTTP sempre mockado nos testes.
"""
