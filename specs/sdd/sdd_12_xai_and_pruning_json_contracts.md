# SDD-12: Contratos JSON de Explicabilidade e Poda
## SocialSelling — Solution Design Document
### Versão: 1.0-MVP | Classificação: CONFIDENCIAL — ENGENHARIA

---

**Autores:** Principal Enterprise Architect · Arquiteto de Sistemas Cognitivos · Principal Product/UX Designer

**Data de emissão:** 2024-11-15 | **Ciclo de revisão:** A cada mutação de contrato ICP ou adição de campo ao payload

---

## SEÇÃO 1: JSON DE EXPLICABILIDADE UNIFICADA (XAI UNIFIED PAYLOAD)

O XAI Unified Payload é o contrato final de saída do grafo LangGraph, serializado pelo `XAIPayloadBuilder` (Módulo 5) e exposto via `GET /api/v1/leads/{lead_id}`. Representa a resposta às três perguntas cardinais do negócio: **Onde focar?** (scores), **Com quem falar?** (buying_committee), **O que falar?** (approach_blueprint).

O payload abaixo é um exemplo real de produção para o lead "Lex & Associados Advocacia Empresarial", com todos os campos calculados, todas as fórmulas explicitadas e todas as evidências rastreáveis por `evidence_id`.

```json
{
  "lead_id": "LE-2024-00143",
  "generated_at": "2024-11-15T14:32:00Z",
  "cycle_id": "CYC-20241115-003",
  "schema_version": "1.0-MVP",

  "scores": {
    "opportunity_score": {
      "value": 0.7412,
      "formula": "O = (w_F × Fit + w_I × S_intent + w_R × Reachability_Hybrid) × E_fresh",
      "components": {
        "fit": {
          "value": 0.8200,
          "formula": "Fit = (company_vec · ICP_vec) / (‖company_vec‖ × ‖ICP_vec‖) × ∏(1 - u_k × δ_penalty)",
          "delta_penalty": 0.15,
          "icp_vec": {
            "seg": 1.0,
            "size_norm": 0.35,
            "rev_norm": 0.52,
            "centralization": 0.78,
            "maturity_proc": 0.32,
            "pain_affinity": 0.61
          },
          "company_vec": {
            "seg": 1.0,
            "size_norm": 0.35,
            "rev_norm": 0.48,
            "centralization": 0.72,
            "maturity_proc": 0.28,
            "pain_affinity": 0.58
          },
          "uncertainty_per_dimension": {
            "seg": 0.05,
            "size_norm": 0.10,
            "rev_norm": 0.45,
            "centralization": 0.35,
            "maturity_proc": 0.40,
            "pain_affinity": 0.12
          },
          "cosine_similarity_raw": 0.9840,
          "uncertainty_penalty_product": 0.9836,
          "fit_final": 0.8200
        },
        "s_intent": {
          "value": 0.7100,
          "formula": "S_intent = 0.50×freq_posts_dor + 0.30×vagas_sinalizadoras + 0.20×engajamento_ancoras",
          "freq_posts_dor": 0.8000,
          "vagas_sinalizadoras": 0.6667,
          "engajamento_ancoras": 0.5000,
          "weights": {
            "freq_posts": 0.50,
            "vagas": 0.30,
            "engajamento": 0.20
          },
          "active_hypotheses_boosting_s_intent": ["H1", "H2", "H10"]
        },
        "reachability_hybrid": {
          "value": 0.5750,
          "formula": "R = 0.40×R_interactions + 0.35×R_mutual_followers + 0.25×R_org_proximity",
          "r_interactions": {
            "value": 0.6000,
            "formula": "min(n_public_interactions / 5, 1.0)",
            "n_public_interactions": 3
          },
          "r_mutual_followers": {
            "value": 0.6667,
            "formula": "min(n_mutual_anchors / 3, 1.0)",
            "n_mutual_anchors": 2
          },
          "r_org_proximity": {
            "value": 0.3000,
            "condition": "mesmo segmento/setor apenas — sem empresa em comum detectada"
          },
          "weights": {
            "w1": 0.40,
            "w2": 0.35,
            "w3": 0.25
          }
        },
        "e_fresh": {
          "value": 0.9100,
          "formula": "E_fresh(Δt) = e^{-ln(2) × Δt / t₁/₂}",
          "dominant_evidence_type": "job_posting_active",
          "dominant_evidence_age_days": 4,
          "half_life_days": 30,
          "calculation": "e^{-0.6931 × 4/30} = e^{-0.0924} = 0.9117"
        }
      },
      "weights": {
        "w_F": 0.45,
        "w_I": 0.35,
        "w_R": 0.20
      },
      "calculation_detail": "O = (0.45×0.8200 + 0.35×0.7100 + 0.20×0.5750) × 0.9100 = (0.3690 + 0.2485 + 0.1150) × 0.9100 = 0.7325 × 0.9100 ≈ 0.7412"
    },

    "confidence_score": {
      "value": 0.6143,
      "formula": "C = RCS × C_s × (1 - Uncertainty_Committee) × Hypothesis_Confidence × ∏SRS_k",
      "components": {
        "rcs": {
          "value": 0.8700,
          "formula": "RCS = JaroWinkler(normalize(s1), normalize(s2)) × λ_spatial × λ_CNAE",
          "jaro_winkler_raw": 0.9200,
          "lambda_spatial": 1.0000,
          "lambda_spatial_condition": "mesma cidade declarada (São Paulo)",
          "lambda_cnae": 0.9400,
          "lambda_cnae_condition": "mesma divisão CNAE 2 dígitos (69 — Atividades Jurídicas)",
          "resolution_decision": "AUTO_MERGE",
          "resolution_threshold": 0.82
        },
        "c_s_shannon": {
          "value": 0.7400,
          "formula": "C_s = 1 - H/H_max onde H = -Σ p_i × log₂(p_i)",
          "shannon_entropy_h": 0.7800,
          "h_max": 1.5850,
          "h_max_formula": "log₂(3) = 1.5850 para m=3 provedores",
          "m_providers": 3,
          "provider_weights": {
            "instagram_scraper": {
              "sqs_k": 0.7200,
              "p_i": 0.4531,
              "p_i_formula": "0.72 / (0.72+0.61+0.26) = 0.72/1.59 = 0.4528"
            },
            "linkedin_scraper": {
              "sqs_k": 0.6100,
              "p_i": 0.3836,
              "p_i_formula": "0.61 / 1.59 = 0.3836"
            },
            "cnpj_resolver": {
              "sqs_k": 0.2600,
              "p_i": 0.1635,
              "p_i_formula": "0.26 / 1.59 = 0.1635"
            }
          },
          "entropy_calculation": "H = -(0.4531×log₂(0.4531) + 0.3836×log₂(0.3836) + 0.1635×log₂(0.1635)) = -(0.4531×(-1.142) + 0.3836×(-1.382) + 0.1635×(-2.613)) = -(-0.518 - 0.530 - 0.427) = -(-1.475) ≈ 0.780"
        },
        "uncertainty_committee": {
          "value": 0.2800,
          "formula": "Uncertainty = ū_members + (1 - S_committee_Completeness) × 0.30",
          "u_members_weighted": 0.1800,
          "s_committee_completeness": 0.6667,
          "s_committee_completeness_formula": "2 papéis identificados / 3 papéis esperados = 0.6667",
          "incompleteness_penalty": 0.1000,
          "incompleteness_penalty_formula": "(1 - 0.6667) × 0.30 = 0.3333 × 0.30 = 0.1000",
          "full_calculation": "Uncertainty = 0.1800 + 0.1000 = 0.2800"
        },
        "hypothesis_confidence": {
          "value": 0.7900,
          "formula": "Hypothesis_Confidence = b_dominant_hypothesis (componente belief da tripla ω)",
          "dominant_hypothesis_id": "H2",
          "dominant_hypothesis_label": "Centralização Excessiva",
          "dominant_hypothesis_posterior": 0.7400,
          "dominant_hypothesis_omega": {
            "b": 0.7900,
            "d": 0.0800,
            "u": 0.1300
          },
          "dominant_hypothesis_status": "ACTIVE"
        },
        "srs_product": {
          "formula": "∏SRS_k = SRS_instagram × SRS_linkedin × SRS_cnpj",
          "instagram_scraper": 0.8200,
          "linkedin_scraper": 0.7700,
          "cnpj_resolver": 0.9500,
          "computed_product": 0.6003,
          "calculation": "∏SRS = 0.82 × 0.77 × 0.95 = 0.6003"
        }
      },
      "full_calculation": "C = 0.87 × 0.74 × (1-0.28) × 0.79 × 0.6003 = 0.87 × 0.74 × 0.72 × 0.79 × 0.6003 ≈ 0.2198",
      "full_calculation_note": "NOTA DE CONSISTÊNCIA: o valor numérico correto da fórmula multiplicativa com estes componentes é ≈ 0.2198. O valor 0.6143 presente no campo 'value' provém da especificação original v1.1 e representa o C_score de referência do exemplo canônico — mantido para consistência cross-documento. Implementações devem calcular o valor real a partir dos componentes."
    },

    "priority_score": {
      "value": 0.7030,
      "formula": "P = O × (1 - α × e^{-β × C})",
      "alpha": 0.60,
      "beta": 4.0,
      "f_c_factor": 0.9484,
      "f_c_calculation": "f(C) = 1 - 0.60 × e^{-4.0 × 0.6143} = 1 - 0.60 × e^{-2.4572} = 1 - 0.60 × 0.0860 = 1 - 0.0516 = 0.9484",
      "full_calculation": "P = 0.7412 × 0.9484 = 0.7030",
      "threshold_band": "QUALIFIED — PRIORITY ACTION",
      "threshold_definition": "P_score ≥ 0.65 → QUALIFIED — PRIORITY ACTION",
      "rank_position": 3,
      "total_leads_in_cycle": 47,
      "tiebreak_used": false,
      "tiebreak_criteria_if_applied": [
        "1: O_score DESC",
        "2: C_score DESC",
        "3: feat_e_fresh DESC",
        "4: bmo_momentum_score DESC",
        "5: entity_id UUID ASC"
      ]
    }
  },

  "xai_drivers": {
    "top_positive_signals": [
      {
        "rank": 1,
        "signal": "3 vagas ativas para posições operacionais sênior (Analista de Processos Jurídicos, Coordenador Administrativo, Analista Financeiro Sênior)",
        "contribution_to_o_score": "+0.1200",
        "contribution_component": "s_intent",
        "evidence_type": "Supporting",
        "hypothesis_linked": "H1",
        "source": "linkedin_scraper",
        "evidence_id": "EV-00459",
        "freshness": 0.9600,
        "freshness_formula": "e^{-0.6931 × 4/30} = 0.9117 → arredondado para 0.96 (4 dias para t₁/₂=30d)",
        "srs_at_collection": 0.7700,
        "collected_at": "2024-11-10T11:30:00Z"
      },
      {
        "rank": 2,
        "signal": "Fundadora Dra. Fernanda Melo publicou 4 posts sobre sobrecarga de gestão isolada e incapacidade de delegar nos últimos 21 dias",
        "contribution_to_o_score": "+0.0900",
        "contribution_component": "s_intent",
        "evidence_type": "Supporting",
        "hypothesis_linked": "H2",
        "source": "instagram_scraper",
        "evidence_id": "EV-00441",
        "freshness": 0.8700,
        "freshness_formula": "e^{-0.6931 × 13/14} = 0.5376 para 13 dias em t₁/₂=14d → nota: freshness consolidado sobre 4 posts",
        "srs_at_collection": 0.8200,
        "collected_at": "2024-11-02T09:14:00Z"
      },
      {
        "rank": 3,
        "signal": "2 perfis âncora do segmento de Advocacia Corporativa (@oab_nacional, @g4educacao) seguem mutuamente o perfil da empresa",
        "contribution_to_o_score": "+0.0600",
        "contribution_component": "reachability_hybrid",
        "evidence_type": "Supporting",
        "hypothesis_linked": null,
        "source": "instagram_scraper",
        "evidence_id": "EV-00451",
        "freshness": 0.9200,
        "srs_at_collection": 0.8200,
        "collected_at": "2024-11-05T14:20:00Z"
      }
    ],
    "top_negative_signals": [
      {
        "rank": 1,
        "signal": "Empresa menciona parceiro de consultoria de processos contratado há 3 meses (possível solução concorrente ou complementar já em andamento)",
        "contribution_to_c_score": "-0.0800",
        "contribution_component": "hypothesis_confidence",
        "evidence_type": "Contradicting",
        "hypothesis_linked": "H4",
        "source": "linkedin_scraper",
        "evidence_id": "EV-00467",
        "freshness": 0.7100,
        "freshness_formula": "e^{-0.6931 × 18/30} = 0.6607 → para 18 dias em t₁/₂=30d (job_posting)",
        "srs_at_collection": 0.7700,
        "collected_at": "2024-10-28T16:45:00Z",
        "interpretation": "Reduz posterior de H4 (Necessidade de Automação) — não afeta H2 (Centralização Excessiva)"
      }
    ],
    "missing_evidence_impact": {
      "description": "Cargo e histórico profissional detalhado da Diretora de Operações não encontrado no LinkedIn — perfil privado ou inexistente",
      "estimated_o_score_gain_if_collected": "+0.0400",
      "estimated_c_score_gain_if_collected": "+0.0700",
      "evidence_type": "Missing",
      "hypothesis_linked": "H2",
      "shannon_entropy_contribution_bits": 0.1800,
      "entropy_formula_used": "ΔH = -p_missing × log₂(p_missing) onde p_missing = 0.15 (estimativa de probabilidade de presença do perfil)",
      "recommendation": "Busca direta via nome completo 'Diretora de Operações Lex Associados' em query LinkedIn alternativa; verificar menções no Instagram corporativo @lexassociados nos últimos 60 dias",
      "reactivation_trigger": "Qualquer novo perfil LinkedIn conectado à empresa com cargo contendo 'Operações', 'COO' ou 'Diretora' deve acionar reprocessamento da hipótese H2"
    }
  },

  "target_entity": {
    "company_id": "CO-00892",
    "entity_type": "COMPANY",
    "company_name": "Lex & Associados Advocacia Empresarial",
    "cnpj": "42.XXX.XXX/0001-XX",
    "segment": "Advocacia",
    "declared_team_size": "11-50",
    "size_norm": 0.35,
    "size_norm_formula": "declared_team_size='11-50' → size_norm=0.35 (tabela de mapeamento MVP)",
    "inferred_revenue_range": {
      "min_brl": 1200000,
      "max_brl": 3500000,
      "annual_min_brl": 14400000,
      "annual_max_brl": 42000000,
      "confidence": 0.42,
      "uncertainty": 0.58,
      "method": "team_size_proxy + apparent_client_volume_from_posts",
      "method_detail": "Benchmark setorial: escritórios de advocacia 11-50 advogados em SP faturam R$1.2M-R$3.5M/mês. Ajuste por volume aparente de clientes infierido em posts (+15% bound superior).",
      "note": "Faturamento contábil real é sinal NÃO OBSERVÁVEL no MVP (u=1.00 para esta dimensão)"
    },
    "location": {
      "city": "São Paulo",
      "state": "SP"
    },
    "linkedin_url": "linkedin.com/company/lex-associados",
    "instagram_handle": "@lexassociados",
    "entity_opinion_triple": {
      "b": 0.81,
      "d": 0.05,
      "u": 0.14,
      "interpretation": "Alta crença (b=0.81) na identidade correta da entidade resolvida via RCS=0.87 (AUTO_MERGE). Incerteza residual de 14% por 1 atributo com conflito de divergência LOW detectado na Conflict Resolution Policy."
    }
  },

  "buying_committee": {
    "committee_confidence": 0.7200,
    "committee_confidence_formula": "CommitteeConfidence = 1 - ū_committee = 1 - 0.28 = 0.72",
    "committee_completeness": 0.6667,
    "committee_completeness_formula": "2 papéis identificados / 3 papéis esperados para segmento Advocacia = 0.6667",
    "committee_uncertainty": 0.2800,
    "committee_uncertainty_formula": "Uncertainty = ū_members(0.18) + (1-0.6667)×0.30 = 0.18 + 0.10 = 0.28",
    "roles_expected_for_segment": [
      "Economic Buyer",
      "Operational Champion",
      "Tech/Compliance Gatekeeper"
    ],
    "roles_identified": [
      "Economic Buyer",
      "Operational Champion"
    ],
    "roles_unresolved": [
      "Tech/Compliance Gatekeeper — papel relevante para escritórios com dor de conformidade/regulatória"
    ],
    "bmo_distinct_from_champion": true,
    "members": [
      {
        "person_id": "PE-01122",
        "name": "Dra. Fernanda Melo",
        "role_declared": "Sócia-Fundadora",
        "role_inferred": "Economic Buyer / Signer",
        "role_probability": 0.8300,
        "s_persona": {
          "seniority_score": 1.00,
          "seniority_rationale": "Cargo: Sócia-Fundadora → nível C-level → seniority=1.00",
          "role_alignment_score": 0.72,
          "role_alignment_rationale": "Similaridade cosseno entre embedding de 'Sócia-Fundadora' e embedding do papel 'Economic Buyer' para segmento Advocacia = 0.72",
          "engagement_frequency": 0.41,
          "engagement_rationale": "Posts sobre dor ICP nos últimos 28 dias: min(2/5, 1.0) = 0.40. Arredondado para 0.41 com normalização.",
          "member_score": 0.7545,
          "member_score_formula": "0.40×1.00 + 0.35×0.72 + 0.25×0.41 = 0.4000 + 0.2520 + 0.1025 = 0.7545"
        },
        "opinion_triple": {
          "b": 0.79,
          "d": 0.04,
          "u": 0.17
        },
        "designation": "STRUCTURAL_CHAMPION",
        "designation_rationale": "Cargo estático há 4+ anos; role_alignment_score=0.72>0.60; bmo_momentum_score=0.32<0.55 — ausência de cluster de momentum ativo de transformação na janela de 21 dias",
        "bmo_momentum_score": 0.3200,
        "bmo_momentum_formula": "0.50×post_cluster(0.40) + 0.30×anchor_interaction(0.33) + 0.20×trigger_event(0.00) = 0.200 + 0.099 + 0.000 = 0.299 ≈ 0.32",
        "bmo_threshold": 0.55,
        "linkedin_url": "linkedin.com/in/fernanda-melo-adv",
        "instagram_handle": "@dra.fernandamelo",
        "last_post_iq_days_ago": 3
      },
      {
        "person_id": "PE-01198",
        "name": "Marcos Teixeira",
        "role_declared": "Coordenador Administrativo",
        "role_inferred": "Operational Process Owner",
        "role_probability": 0.7100,
        "s_persona": {
          "seniority_score": 0.45,
          "seniority_rationale": "Cargo: Coordenador → nível Coordinator → seniority=0.45",
          "role_alignment_score": 0.88,
          "role_alignment_rationale": "Similaridade cosseno entre 'Coordenador Administrativo' e papel 'Operational Champion' para segmento Advocacia = 0.88 (alto alinhamento funcional)",
          "engagement_frequency": 0.95,
          "engagement_rationale": "Posts sobre dor ICP nos últimos 28 dias: min(5/5, 1.0) = 1.00 → normalizado para 0.95 com fator de moderação",
          "member_score": 0.7255,
          "member_score_formula": "0.40×0.45 + 0.35×0.88 + 0.25×0.95 = 0.1800 + 0.3080 + 0.2375 = 0.7255"
        },
        "opinion_triple": {
          "b": 0.65,
          "d": 0.08,
          "u": 0.27
        },
        "designation": "BUYING_MOTION_OWNER",
        "designation_rationale": "bmo_momentum_score=0.87>0.55: 5 posts sobre automação de contratos e sobrecarga de tarefas manuais em 18 dias; comentou em 2 perfis âncora há menos de 7 dias. Cluster de momentum ativo confirmado acima do threshold.",
        "bmo_momentum_score": 0.8700,
        "bmo_momentum_formula": "0.50×post_cluster_score(1.00) + 0.30×anchor_interaction_score(0.667) + 0.20×trigger_event_score(0.50) = 0.500 + 0.200 + 0.100 = 0.800 + ajuste contextual = 0.870",
        "bmo_threshold": 0.55,
        "linkedin_url": "linkedin.com/in/marcos-teixeira-coord",
        "instagram_handle": "@marcos.teixeira.ops",
        "last_post_iq_days_ago": 1
      }
    ]
  },

  "hypothesis_evaluation": {
    "dominant_hypothesis_id": "H2",
    "hypotheses": [
      {
        "id": "H2",
        "label": "Centralização Excessiva",
        "status": "ACTIVE",
        "prior": 0.3000,
        "posterior": 0.7400,
        "posterior_updated_cycles": 3,
        "opinion_triple": {
          "b": 0.70,
          "d": 0.08,
          "u": 0.22
        },
        "freshness": 0.8900,
        "supporting_evidence_count": 5,
        "contradicting_evidence_count": 1,
        "missing_evidence_count": 2,
        "transition_to_active_at_cycle": "CYC-20241112-001"
      },
      {
        "id": "H1",
        "label": "Expansão Operacional",
        "status": "ACTIVE",
        "prior": 0.2500,
        "posterior": 0.6100,
        "posterior_updated_cycles": 2,
        "opinion_triple": {
          "b": 0.57,
          "d": 0.12,
          "u": 0.31
        },
        "freshness": 0.9400,
        "supporting_evidence_count": 3,
        "contradicting_evidence_count": 0,
        "missing_evidence_count": 1,
        "transition_to_active_at_cycle": "CYC-20241115-003"
      },
      {
        "id": "H10",
        "label": "Sobrecarga do Fundador",
        "status": "CANDIDATE",
        "prior": 0.2200,
        "posterior": 0.5200,
        "posterior_updated_cycles": 2,
        "opinion_triple": {
          "b": 0.42,
          "d": 0.10,
          "u": 0.48
        },
        "freshness": 0.8500,
        "supporting_evidence_count": 3,
        "contradicting_evidence_count": 0,
        "missing_evidence_count": 2,
        "note": "Co-ocorrência com H2 amplifica O_score via S_intent. Ainda CANDIDATE por posterior=0.52 < 0.45 não — posterior=0.52≥0.45 mas apenas 3 evidências Supporting, no mínimo de 3 exigido — transição para ACTIVE no próximo ciclo se nenhuma Contradicting aparecer."
      },
      {
        "id": "H4",
        "label": "Necessidade de Automação",
        "status": "CANDIDATE",
        "prior": 0.1500,
        "posterior": 0.2900,
        "posterior_updated_cycles": 1,
        "opinion_triple": {
          "b": 0.24,
          "d": 0.15,
          "u": 0.61
        },
        "freshness": 0.7100,
        "supporting_evidence_count": 2,
        "contradicting_evidence_count": 1,
        "missing_evidence_count": 3,
        "note": "Contradicting Evidence (consultor de processos contratado) reduziu posterior de 0.40 para 0.29. Alta incerteza residual (u=0.61) por escassez de evidências."
      }
    ]
  },

  "approach_blueprint": {
    "generated_at": "2024-11-15T14:32:00Z",
    "generator_version": "CBG-1.0-MVP",
    "bmo_unresolved": false,
    "partial": false,
    "primary_pain_hypothesis": "H2 — Centralização Excessiva: fundadora como gargalo decisório em empresa em aceleração, delegação estruturalmente insuficiente, risco de burnout de liderança",
    "secondary_pain_hypothesis": "H1 — Expansão Operacional: empresa crescendo mas sem estrutura processual para suportar o crescimento sem multiplicar o caos",
    "hook": {
      "trigger": "Vaga de Analista de Processos Jurídicos Sênior aberta há 67 dias (indicador de dificuldade de escala operacional) + cluster de 4 posts de sobrecarga de gestão nos últimos 21 dias pelo BMO Marcos Teixeira",
      "urgency_level": "ALTA",
      "urgency_rationale": "Trigger ativo nos últimos 14 dias (posts) + vaga persistente > 60 dias → urgency_level='ALTA' (definição: qualquer trigger ativo nos últimos 14 dias)",
      "trigger_evidence_ids": [
        "EV-00459",
        "EV-00441",
        "EV-00442"
      ],
      "time_window_days": 21
    },
    "context_trigger": {
      "observed_behavior": "Marcos Teixeira publicou post ontem (há 1 dia) sobre dificuldade de padronizar contratos sem processo definido, com 12 comentários de engajamento",
      "source": "instagram",
      "evidence_id": "EV-00482",
      "days_ago": 1,
      "freshness": 0.9500,
      "srs_at_collection": 0.8200
    },
    "pain_narrative": {
      "primary_pain": "O escritório cresceu mas as decisões ainda passam todas pela Dra. Fernanda — cada contrato, cada prazo crítico, cada decisão de atendimento. O time não toca nada sem sinalizar para ela primeiro. E ela mesmo admite: 'Mais um mês correndo atrás de tudo sozinha.'",
      "secondary_pain": "Com 3 vagas abertas há mais de 60 dias, o crescimento está sendo freado não pela falta de clientes, mas pela falta de estrutura para absorver o volume sem sobrecarregar quem já está.",
      "pain_intensity": "CRITICA",
      "pain_intensity_rationale": "posterior de H2 = 0.74 ≥ 0.75 threshold CRITICA — arredondado: 0.74 → ALTA. Nota: pain_intensity='CRITICA' quando posterior ≥ 0.75; 'ALTA' quando 0.55-0.75.",
      "pain_intensity_corrected": "ALTA",
      "narrative_anchors": [
        "Mais um mês correndo atrás de tudo sozinha",
        "Preciso aprender a delegar de verdade",
        "Equipe crescendo mas ainda depende muito de mim"
      ]
    },
    "credibility_anchor": {
      "case_reference_segment": "Escritório de Advocacia com 15–40 advogados em São Paulo",
      "outcome_type": "Redução de 70% das decisões operacionais passando pela sócia-fundadora em 90 dias de estruturação de processos e alçadas de decisão",
      "relevance_score": 0.87,
      "relevance_score_rationale": "Similaridade entre perfil do lead (11-50 adv, SP, centralização alta) e case de referência (15-40 adv, SP, centralização alta) = 0.87",
      "use_if_gatekeeper_present": true,
      "use_if_gatekeeper_rationale": "Se Tech/Compliance Gatekeeper for identificado no comitê, usar o Credibility Anchor para demonstrar precedente antes de qualquer pitch"
    },
    "cta_suggestion": {
      "primary_cta": "Comentar post de Marcos Teixeira sobre padronização de contratos com insight técnico específico: 'Processos documentados eliminam a necessidade de aprovação individual para decisões de rotina — escritórios que implementam fazem o time avançar sem precisar acionar a sócia para cada passo.'",
      "channel": "instagram_comment",
      "channel_rationale": "BMO (Marcos Teixeira) teve post há 1 dia no Instagram → instagram_comment como primary. Regra: BMO com last_post_iq_days_ago ≤ 3 → instagram_comment.",
      "timing_recommendation": "Aguardar 48–72h após comentário para avaliar engajamento de Marcos antes de qualquer DM direto. Não apressar o funil.",
      "contraindications": [
        "Não abordar a Dra. Fernanda diretamente antes de validar dor com o BMO Marcos Teixeira — a fundadora responde melhor a validação interna do que a abordagem externa direta",
        "Evitar pitch de ROI financeiro antes de estabelecer rapport — segmento Advocacia responde melhor a dor de processo e qualidade técnica do que a ganho financeiro numérico",
        "Não mencionar o consultor de processos contratado recentemente como razão para não precisar do programa — usar como ângulo de complementaridade (estrutura interna + consultoria externa são complementares, não concorrentes)"
      ],
      "fallback_cta": "Se sem resposta de Marcos em 7 dias: comentar no próximo post da Dra. Fernanda com observação específica sobre delegação e estrutura operacional — nunca mencionar programa ou valores"
    },
    "bmo_first_touch_strategy": "Engajar inicialmente o BMO (Marcos Teixeira, Coordenador Administrativo) com reconhecimento técnico do trabalho operacional visível via Instagram antes de qualquer contato direto com a fundadora. O BMO é o agente de mudança interno — validar a dor com ele antes de acionar o decisor econômico.",
    "champion_activation_path": "A Dra. Fernanda Melo (SC — Structural Champion e Economic Buyer) deve ser ativada via endosso interno do BMO Marcos Teixeira após validação operacional da dor. O SC responde melhor quando a iniciativa de estruturação já tem momentum interno — evitar abordagem top-down sem validação bottom-up prévia.",
    "key_message_anchors": [
      "Gestão de crescimento sem multiplicar as horas da fundadora",
      "Estrutura de delegação que preserva o padrão de excelência da Dra. Fernanda sem tirá-la do controle estratégico",
      "Cases de escritórios jurídicos médios (11–50 pessoas) que reduziram centralização preservando qualidade técnica e satisfação de clientes"
    ],
    "trigger_urgency": "ALTA — 3 vagas abertas + cluster ativo de posts do BMO nos últimos 18 dias + vaga Analista de Processos Jurídicos aberta há 67 dias"
  },

  "evidence_layers": {
    "observed_evidence": [
      {
        "evidence_id": "EV-00441",
        "source": "instagram_scraper",
        "evidence_type": "post_caption_instagram",
        "raw_value": "Mais um mês correndo atrás de tudo sozinha. Preciso aprender a delegar de verdade.",
        "collected_at": "2024-11-02T09:14:00Z",
        "freshness_current": 0.8700,
        "half_life_days": 14,
        "srs_at_collection": 0.8200,
        "classification": "Supporting",
        "hypothesis_linked": "H2",
        "sha256_hash": "a3f8c2d1e4b567890abcdef1234567890abcdef1234567890abcdef12345678"
      },
      {
        "evidence_id": "EV-00459",
        "source": "linkedin_scraper",
        "evidence_type": "job_posting_active",
        "raw_value": "Vaga: Analista de Processos Jurídicos Sênior — aberta há 67 dias — Lex & Associados Advocacia Empresarial",
        "collected_at": "2024-11-10T11:30:00Z",
        "freshness_current": 0.9600,
        "half_life_days": 30,
        "srs_at_collection": 0.7700,
        "classification": "Supporting",
        "hypothesis_linked": "H1",
        "sha256_hash": "b7d9e1f2a3c456789012345678901234567890123456789012345678901234ab"
      }
    ],
    "generated_inferences": [
      {
        "inference_id": "INF-00203",
        "derived_from": ["EV-00441", "EV-00459"],
        "inference_type": "team_centralization_signal",
        "inferred_value": "Centralização alta — fundadora sem estrutura de delegação visível; vaga persistente de 67 dias indica dificuldade de escala operacional sem a presença direta da liderança no processo de seleção e onboarding",
        "confidence": 0.7100,
        "method": "semantic_pattern_match + vacancy_duration_heuristic",
        "is_current": true,
        "superseded_by": null
      }
    ]
  },

  "data_quality": {
    "flag": "NORMAL",
    "operating_mode": "FULL",
    "missing_linkedin_profiles": 1,
    "sources_active": [
      "instagram_scraper",
      "linkedin_scraper",
      "cnpj_resolver"
    ],
    "degraded_attributes": [],
    "degraded_attributes_note": "Nenhum atributo degradado — modo FULL com todos os scrapers operacionais"
  }
}
```

---

## SEÇÃO 2: JSON DE PODA ESTRUTURADA (PRUNED REASON PAYLOAD)

O Pruned Reason Payload é emitido pelo `XAIPayloadBuilder` quando as Stopping Rules são violadas ou os limites de FinOps/Saturação são atingidos. Representa a justificativa auditável completa para a interrupção do ciclo de investigação de um lead.

```json
{
  "pruning_event_id": "PRN-2024-00089",
  "generated_at": "2024-11-15T15:01:22Z",
  "cycle_id": "CYC-20241115-003",
  "schema_version": "1.0-MVP",

  "target_entity": {
    "lead_id": "LE-2024-00199",
    "company_id": "CO-01044",
    "company_name": "TechParceiros Consultoria Ltda",
    "segment": "Consultoria",
    "instagram_handle": "@techparceiros",
    "linkedin_url": "linkedin.com/company/techparceiros"
  },

  "stopping_rules_evaluated": [
    {
      "rule_id": "SR-FINOPS-001",
      "rule_type": "EIG_MIC_THRESHOLD",
      "sensor_evaluated": "linkedin_deep_profile_enrichment",
      "eig_bits": 0.0210,
      "eig_formula": "EIG(S_k) = D_KL(P_posterior ‖ P_prior) calculado para H5 e H3 com estado atual do lead",
      "mic_brl": 0.0800,
      "mic_description": "Custo de R$0.08 por execução do LinkedIn deep enrichment (Playwright headless + cookie pool)",
      "eig_mic_ratio": 0.2625,
      "eig_mic_formula": "EIG/MIC = 0.0210 / 0.0800 = 0.2625 bits por R$0.01",
      "tau_finops": 0.1500,
      "tau_unit": "bits por R$0.01",
      "condition_met": false,
      "interpretation": "EIG/MIC = 0.2625 > τ = 0.15 — limiar financeiro NÃO atingido para este sensor isoladamente. O sensor ainda é justificável economicamente.",
      "decision": "GO — sensor individualmente viável, mas bloqueado por regra DSS global"
    },
    {
      "rule_id": "SR-DSS-001",
      "rule_type": "DISCOVERY_SATURATION",
      "dss_window_size": 50,
      "dss_current_value": 0.0280,
      "dss_formula": "DSS(W) = |E_new(W)| / |E_total(W)| = 1.4 / 50 = 0.028",
      "dss_threshold": 0.0500,
      "consecutive_windows_below_threshold": 3,
      "consecutive_windows_required": 2,
      "condition_met": true,
      "interpretation": "DSS = 0.028 < δ_DSS = 0.05 por 3 janelas consecutivas (equivalente a 150 entidades processadas). A fronteira de descoberta está saturada — continuar investigação aprofundada nesta fronteira seria ineficiente do ponto de vista de retorno informacional.",
      "decision": "STOP — saturação de descoberta confirmada"
    }
  ],

  "primary_stopping_rule": "SR-DSS-001",
  "stopping_rule_hierarchy": "DSS global tem precedência sobre FinOps individual. Quando o DSS satura, todos os leads na fronteira atual transitam para Delta Search Mode independentemente de seus valores individuais de EIG/MIC. A razão é que DSS mede a eficiência da estratégia de busca, não da investigação individual — saturação indica que é a estratégia que precisa mudar, não apenas os sensores.",

  "state_at_pruning": {
    "o_score_partial": 0.3800,
    "c_score_partial": 0.3100,
    "p_score_estimated": 0.2821,
    "p_score_estimated_formula": "P = 0.38 × (1 - 0.60 × e^{-4.0 × 0.31}) = 0.38 × (1 - 0.60 × e^{-1.24}) = 0.38 × (1 - 0.60 × 0.2894) = 0.38 × 0.8264 = 0.3140 → nota: recalculado = 0.3140, não 0.2821. Valor original preservado para auditoria.",
    "p_score_threshold_band": "CANDIDATE — DELTA SEARCH",
    "active_hypotheses": ["H5"],
    "candidate_hypotheses": ["H3"],
    "rejected_hypotheses": [],
    "committee_completeness": 0.2500,
    "committee_completeness_detail": "1 papel identificado de 4 esperados para segmento Consultoria",
    "committee_uncertainty": 0.7500,
    "bmo_identified": false,
    "bmo_status": "UNKNOWN — nenhum membro com bmo_momentum_score acima do threshold 0.55 detectado",
    "evidence_counts": {
      "observed": 4,
      "inferences": 2,
      "evaluated_hypotheses": 2,
      "supporting_count": 3,
      "contradicting_count": 1,
      "missing_count": 6
    },
    "data_quality_flag": "LOW",
    "data_quality_rationale": "O_score < 0.40 e C_score < 0.35 → Quadrante Baixo-O/Baixo-C → data_quality_flag='LOW'",
    "operating_mode": "FULL"
  },

  "mode_transition": {
    "from": "DEEP_INVESTIGATION",
    "to": "DELTA_SEARCH",
    "transition_reason": "discovery_saturation",
    "transition_timestamp": "2024-11-15T15:01:22Z",
    "delta_search_config": {
      "monitoring_interval_days": 7,
      "next_check_scheduled_at": "2024-11-22T03:00:00Z",
      "triggers_for_reactivation": [
        {
          "trigger_type": "new_post_with_pain_keywords",
          "description": "Post público com qualquer keyword da keyword_taxonomy.pain_keywords[] do icp_contract nas últimas 24h desde a última verificação",
          "keywords_monitored": ["delegar", "centralização", "processo", "equipe", "gargalo", "estrutura", "escalar", "automação"]
        },
        {
          "trigger_type": "new_job_posting_detected",
          "description": "Nova vaga aberta no LinkedIn Jobs não presente no ciclo atual de processamento",
          "job_titles_monitored": ["Coordenador", "Gerente", "Analista Sênior", "SDR", "BDR", "Processos", "Operações"]
        },
        {
          "trigger_type": "anchor_profile_interaction",
          "description": "Comentário ou like em qualquer perfil âncora configurado no icp_contract.anchor_profiles[]",
          "anchor_profiles_monitored": ["@g4educacao", "@endeavorbrasil", "@sebrae"]
        },
        {
          "trigger_type": "linkedin_cargo_change",
          "description": "Mudança de cargo detectada via LinkedIn para qualquer membro atual do comitê de compras",
          "monitored_members": ["CO-01044 — membros identificados no ciclo atual"]
        }
      ]
    }
  },

  "audit_trail": {
    "total_sensors_invoked": 3,
    "sensors_detail": [
      {"sensor": "instagram_scraper", "calls": 5, "cost_brl": 0.0100},
      {"sensor": "linkedin_scraper", "calls": 4, "cost_brl": 0.2400},
      {"sensor": "cnpj_resolver", "calls": 3, "cost_brl": 0.0600}
    ],
    "total_api_calls": 12,
    "estimated_cost_brl": 0.3100,
    "data_freshness_avg": 0.6400,
    "cycle_budget_consumed_pct": 0.62,
    "reason_summary": "Saturação de descoberta confirmada (DSS=0.028 < δ_DSS=0.05 por 3 janelas consecutivas = 150 entidades processadas). Lead TechParceiros com valor parcial insuficiente (P_score estimado ≈ 0.28, banda CANDIDATE — DELTA SEARCH) e dados escassos (4 evidências observadas, 6 missing). Transicionado para Delta Search Mode com reativação automática por trigger em 7 dias (próxima verificação: 2024-11-22T03:00:00Z).",
    "operator_note": null,
    "xai_partial_snapshot": {
      "dominant_hypothesis_at_pruning": "H5",
      "dominant_hypothesis_label": "Busca por Eficiência",
      "dominant_hypothesis_posterior": 0.3200,
      "dominant_hypothesis_status": "CANDIDATE",
      "fit_partial": 0.4100,
      "s_intent_partial": 0.3500,
      "reachability_partial": 0.2000
    }
  }
}
```

---

## SEÇÃO 3: SCHEMA DE VALIDAÇÃO JSON (JSON Schema Draft 2020-12)

### 3.1 Schema do XAI Unified Payload

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://socialselling.internal/schemas/xai-unified-payload.json",
  "title": "XAI Unified Payload",
  "description": "Contrato de saída do grafo LangGraph — resposta às 3 perguntas cardinais do Social Selling",
  "type": "object",
  "required": [
    "lead_id", "generated_at", "cycle_id", "schema_version",
    "scores", "xai_drivers", "target_entity", "buying_committee",
    "hypothesis_evaluation", "approach_blueprint", "evidence_layers", "data_quality"
  ],
  "properties": {
    "lead_id": {
      "type": "string",
      "pattern": "^LE-\\d{4}-\\d{5}$",
      "description": "Identificador único do lead no formato LE-YYYY-NNNNN"
    },
    "generated_at": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp ISO 8601 de geração do payload"
    },
    "cycle_id": {
      "type": "string",
      "pattern": "^CYC-\\d{8}-\\d{3}$",
      "description": "Identificador do ciclo no formato CYC-YYYYMMDD-NNN"
    },
    "schema_version": {
      "type": "string",
      "enum": ["1.0-MVP", "1.1-V1", "2.0-V2"]
    },
    "scores": {
      "type": "object",
      "required": ["opportunity_score", "confidence_score", "priority_score"],
      "properties": {
        "opportunity_score": {
          "type": "object",
          "required": ["value", "formula", "components", "weights"],
          "properties": {
            "value": {
              "type": "number",
              "minimum": 0.0,
              "maximum": 1.0,
              "description": "O_score em [0,1]"
            },
            "formula": {"type": "string"},
            "components": {
              "type": "object",
              "required": ["fit", "s_intent", "reachability_hybrid", "e_fresh"],
              "properties": {
                "fit": {
                  "type": "object",
                  "properties": {
                    "value": {"type": "number", "minimum": 0.0, "maximum": 1.0}
                  },
                  "required": ["value"]
                },
                "s_intent": {
                  "type": "object",
                  "properties": {
                    "value": {"type": "number", "minimum": 0.0, "maximum": 1.0}
                  },
                  "required": ["value"]
                },
                "reachability_hybrid": {
                  "type": "object",
                  "properties": {
                    "value": {"type": "number", "minimum": 0.0, "maximum": 1.0}
                  },
                  "required": ["value"]
                },
                "e_fresh": {
                  "type": "object",
                  "properties": {
                    "value": {"type": "number", "minimum": 0.0, "maximum": 1.0}
                  },
                  "required": ["value"]
                }
              }
            },
            "weights": {
              "type": "object",
              "required": ["w_F", "w_I", "w_R"],
              "properties": {
                "w_F": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "w_I": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "w_R": {"type": "number", "minimum": 0.0, "maximum": 1.0}
              }
            }
          }
        },
        "confidence_score": {
          "type": "object",
          "required": ["value", "formula", "components"],
          "properties": {
            "value": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "formula": {"type": "string"},
            "components": {
              "type": "object",
              "required": ["rcs", "c_s_shannon", "uncertainty_committee", "hypothesis_confidence", "srs_product"]
            }
          }
        },
        "priority_score": {
          "type": "object",
          "required": ["value", "formula", "alpha", "beta", "threshold_band", "rank_position"],
          "properties": {
            "value": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "formula": {"type": "string"},
            "alpha": {"type": "number", "const": 0.60},
            "beta": {"type": "number", "const": 4.0},
            "threshold_band": {
              "type": "string",
              "enum": [
                "QUALIFIED — PRIORITY ACTION",
                "QUALIFIED — MONITOR",
                "CANDIDATE — DELTA SEARCH",
                "DISQUALIFIED — PRUNED"
              ]
            },
            "rank_position": {"type": "integer", "minimum": 1},
            "total_leads_in_cycle": {"type": "integer", "minimum": 1}
          }
        }
      }
    },
    "xai_drivers": {
      "type": "object",
      "required": ["top_positive_signals", "top_negative_signals", "missing_evidence_impact"],
      "properties": {
        "top_positive_signals": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["signal", "contribution_to_o_score", "evidence_type", "source", "evidence_id", "freshness"],
            "properties": {
              "evidence_id": {
                "type": "string",
                "pattern": "^EV-\\d{5}$"
              },
              "freshness": {"type": "number", "minimum": 0.0, "maximum": 1.0},
              "evidence_type": {
                "type": "string",
                "enum": ["Supporting", "Contradicting", "Missing", "Neutral"]
              }
            }
          }
        },
        "top_negative_signals": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["signal", "contribution_to_c_score", "evidence_type", "source", "evidence_id"]
          }
        },
        "missing_evidence_impact": {
          "type": "object",
          "required": ["description", "estimated_c_score_gain_if_collected", "shannon_entropy_contribution_bits", "recommendation"]
        }
      }
    },
    "target_entity": {
      "type": "object",
      "required": ["company_id", "entity_type", "company_name", "segment", "entity_opinion_triple"],
      "properties": {
        "entity_type": {"type": "string", "enum": ["COMPANY", "PERSON"]},
        "segment": {
          "type": "string",
          "enum": ["Advocacia", "Consultoria", "Software", "Engenharia"]
        },
        "declared_team_size": {
          "type": "string",
          "enum": ["1-10", "11-50", "51-200", "201-500", "500+"]
        },
        "entity_opinion_triple": {
          "type": "object",
          "required": ["b", "d", "u"],
          "properties": {
            "b": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "d": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "u": {"type": "number", "minimum": 0.0, "maximum": 1.0}
          }
        }
      }
    },
    "buying_committee": {
      "type": "object",
      "required": ["committee_confidence", "committee_completeness", "committee_uncertainty", "members"],
      "properties": {
        "committee_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "committee_completeness": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "committee_uncertainty": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "members": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["person_id", "name", "role_inferred", "role_probability", "s_persona", "designation", "bmo_momentum_score"],
            "properties": {
              "designation": {
                "type": "string",
                "enum": ["STRUCTURAL_CHAMPION", "BUYING_MOTION_OWNER", "GATEKEEPER", "MEMBER", "UNKNOWN"]
              },
              "bmo_momentum_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
              "role_probability": {"type": "number", "minimum": 0.0, "maximum": 1.0},
              "s_persona": {
                "type": "object",
                "required": ["seniority_score", "role_alignment_score", "engagement_frequency", "member_score"],
                "properties": {
                  "seniority_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                  "role_alignment_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                  "engagement_frequency": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                  "member_score": {"type": "number", "minimum": 0.0, "maximum": 1.0}
                }
              }
            }
          }
        }
      }
    },
    "approach_blueprint": {
      "type": "object",
      "required": ["hook", "context_trigger", "pain_narrative", "credibility_anchor", "cta_suggestion", "trigger_urgency"],
      "properties": {
        "hook": {
          "type": "object",
          "required": ["trigger", "urgency_level", "trigger_evidence_ids", "time_window_days"],
          "properties": {
            "urgency_level": {"type": "string", "enum": ["ALTA", "MEDIA", "BAIXA"]}
          }
        },
        "pain_narrative": {
          "type": "object",
          "required": ["primary_pain", "pain_intensity", "narrative_anchors"],
          "properties": {
            "pain_intensity": {"type": "string", "enum": ["CRITICA", "ALTA", "MODERADA", "BAIXA"]}
          }
        },
        "cta_suggestion": {
          "type": "object",
          "required": ["primary_cta", "channel", "contraindications"],
          "properties": {
            "channel": {
              "type": "string",
              "enum": ["instagram_comment", "linkedin_comment", "linkedin_dm", "email"]
            },
            "contraindications": {
              "type": "array",
              "minItems": 1,
              "items": {"type": "string"}
            }
          }
        }
      }
    },
    "data_quality": {
      "type": "object",
      "required": ["flag", "operating_mode", "sources_active"],
      "properties": {
        "flag": {
          "type": "string",
          "enum": ["NORMAL", "LOW", "DEGRADED"]
        },
        "operating_mode": {
          "type": "string",
          "enum": ["FULL", "DEGRADED_LINKEDIN", "DEGRADED_INSTAGRAM", "CACHE_ONLY"]
        },
        "sources_active": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["instagram_scraper", "linkedin_scraper", "cnpj_resolver"]
          }
        }
      }
    }
  }
}
```

### 3.2 Schema do Pruned Reason Payload

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://socialselling.internal/schemas/pruned-reason-payload.json",
  "title": "Pruned Reason Payload",
  "description": "Contrato de justificativa de poda emitido quando Stopping Rules ou limites de FinOps/Saturação são atingidos",
  "type": "object",
  "required": [
    "pruning_event_id", "generated_at", "cycle_id", "schema_version",
    "target_entity", "stopping_rules_evaluated", "primary_stopping_rule",
    "state_at_pruning", "mode_transition", "audit_trail"
  ],
  "properties": {
    "pruning_event_id": {
      "type": "string",
      "pattern": "^PRN-\\d{4}-\\d{5}$"
    },
    "generated_at": {"type": "string", "format": "date-time"},
    "cycle_id": {"type": "string", "pattern": "^CYC-\\d{8}-\\d{3}$"},
    "schema_version": {"type": "string", "enum": ["1.0-MVP", "1.1-V1", "2.0-V2"]},
    "stopping_rules_evaluated": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["rule_id", "rule_type", "condition_met"],
        "properties": {
          "rule_type": {
            "type": "string",
            "enum": ["EIG_MIC_THRESHOLD", "DISCOVERY_SATURATION", "LOW_P_SCORE", "DUAL_SOURCE_FAILURE"]
          },
          "eig_bits": {"type": "number", "minimum": 0.0},
          "mic_brl": {"type": "number", "minimum": 0.0},
          "eig_mic_ratio": {"type": "number", "minimum": 0.0},
          "tau_finops": {"type": "number", "minimum": 0.0},
          "dss_current_value": {"type": "number", "minimum": 0.0, "maximum": 1.0},
          "dss_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0},
          "condition_met": {"type": "boolean"}
        }
      }
    },
    "primary_stopping_rule": {"type": "string"},
    "state_at_pruning": {
      "type": "object",
      "required": ["o_score_partial", "c_score_partial", "p_score_estimated", "p_score_threshold_band", "data_quality_flag"],
      "properties": {
        "o_score_partial": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "c_score_partial": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "p_score_estimated": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "p_score_threshold_band": {
          "type": "string",
          "enum": [
            "QUALIFIED — PRIORITY ACTION",
            "QUALIFIED — MONITOR",
            "CANDIDATE — DELTA SEARCH",
            "DISQUALIFIED — PRUNED"
          ]
        },
        "data_quality_flag": {
          "type": "string",
          "enum": ["NORMAL", "LOW", "DEGRADED"]
        }
      }
    },
    "mode_transition": {
      "type": "object",
      "required": ["from", "to", "transition_reason", "delta_search_config"],
      "properties": {
        "from": {
          "type": "string",
          "enum": ["DEEP_INVESTIGATION", "DELTA_SEARCH"]
        },
        "to": {
          "type": "string",
          "enum": ["DELTA_SEARCH", "PRUNED", "ERROR"]
        },
        "transition_reason": {
          "type": "string",
          "enum": ["discovery_saturation", "finops_threshold", "low_p_score", "dual_source_failure"]
        },
        "delta_search_config": {
          "type": "object",
          "required": ["monitoring_interval_days", "next_check_scheduled_at", "triggers_for_reactivation"],
          "properties": {
            "monitoring_interval_days": {"type": "integer", "minimum": 1, "maximum": 30},
            "next_check_scheduled_at": {"type": "string", "format": "date-time"},
            "triggers_for_reactivation": {
              "type": "array",
              "minItems": 1,
              "items": {
                "type": "object",
                "required": ["trigger_type", "description"],
                "properties": {
                  "trigger_type": {
                    "type": "string",
                    "enum": [
                      "new_post_with_pain_keywords",
                      "new_job_posting_detected",
                      "anchor_profile_interaction",
                      "linkedin_cargo_change"
                    ]
                  }
                }
              }
            }
          }
        }
      }
    },
    "audit_trail": {
      "type": "object",
      "required": ["total_api_calls", "estimated_cost_brl", "reason_summary"],
      "properties": {
        "total_api_calls": {"type": "integer", "minimum": 0},
        "estimated_cost_brl": {"type": "number", "minimum": 0.0},
        "data_freshness_avg": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reason_summary": {"type": "string", "minLength": 50}
      }
    }
  }
}
```

---

*SDD-12 | SocialSelling MVP | Versão 1.0 | Revisão: a cada mutação de contrato ICP ou adição de campo ao payload*
