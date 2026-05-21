"""
globalshop_bi.mongo_queries
============================
Pipelines de agregação MongoDB que exploram o Aggregation Framework do servidor.
Cada função recebe uma ``pymongo.Collection`` e devolve um resultado Python nativo.

Padrões demonstrados:
    • ``$facet``  — multi-pipeline numa única round-trip ao servidor
    • ``$unwind`` — explode arrays de keywords para análise textual
    • ``$bucket`` — distribuição de ratings em intervalos configuráveis
    • ``$geoNear``— proximidade esférica via índice 2dsphere
    • double-group — padrão para séries temporais com ``$push`` + ``$arrayElemAt``
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# $FACET — Resumo Executivo numa única query
# ──────────────────────────────────────────────────────────────

def run_facet_executive(collection: Any) -> dict:
    """
    Executa uma única agregação ``$facet`` que devolve em simultâneo:

    - distribuição de sentimento global
    - performance média por categoria
    - tendência de nota mensal
    - top-10 keywords negativas (via ``$unwind``)

    Demonstra que o MongoDB serve como motor analítico completo,
    não apenas como camada de armazenamento.
    """
    pipeline = [
        {
            "$facet": {
                "sentimentDistribution": [
                    {"$group": {
                        "_id": "$metrics.sentiment",
                        "count": {"$sum": 1},
                    }},
                    {"$sort": {"count": -1}},
                ],
                "categoryPerformance": [
                    {"$group": {
                        "_id": "$product.category",
                        "avgRating": {"$avg": "$metrics.rating"},
                        "total":     {"$sum": 1},
                        "positivos": {"$sum": {"$cond": [{"$eq": ["$metrics.sentiment", "Positive"]}, 1, 0]}},
                        "negativos": {"$sum": {"$cond": [{"$eq": ["$metrics.sentiment", "Negative"]}, 1, 0]}},
                    }},
                    {"$project": {
                        "category":  "$_id",
                        "avgRating": {"$round": ["$avgRating", 2]},
                        "total": 1,
                        "nss": {
                            "$subtract": [
                                {"$multiply": [{"$divide": ["$positivos", "$total"]}, 100]},
                                {"$multiply": [{"$divide": ["$negativos", "$total"]}, 100]},
                            ]
                        },
                        "_id": 0,
                    }},
                    {"$sort": {"avgRating": -1}},
                ],
                "monthlyTrend": [
                    {"$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m", "date": "$metadata.timestamp"}},
                        "avgRating": {"$avg": "$metrics.rating"},
                        "total":     {"$sum": 1},
                    }},
                    {"$sort": {"_id": 1}},
                    {"$project": {"month": "$_id", "avgRating": {"$round": ["$avgRating", 3]}, "total": 1, "_id": 0}},
                ],
                "topNegativeKeywords": [
                    {"$match": {"metrics.sentiment": "Negative"}},
                    {"$unwind": "$content.keywords"},
                    {"$group": {
                        "_id":   "$content.keywords",
                        "count": {"$sum": 1},
                        "avgRating": {"$avg": "$metrics.rating"},
                    }},
                    {"$sort": {"count": -1}},
                    {"$limit": 10},
                    {"$project": {"keyword": "$_id", "count": 1, "avgRating": {"$round": ["$avgRating", 2]}, "_id": 0}},
                ],
            }
        }
    ]
    try:
        result = list(collection.aggregate(pipeline))
        logger.info("$facet executive: carregado com sucesso.")
        return result[0] if result else {}
    except Exception as exc:
        logger.warning("$facet executive falhou: %s", exc)
        return {}


# ──────────────────────────────────────────────────────────────
# $BUCKET — Distribuição de Ratings
# ──────────────────────────────────────────────────────────────

def run_rating_buckets(collection: Any) -> list[dict]:
    """
    Usa ``$bucket`` para agrupar reviews em intervalos de rating,
    calculando NSS dentro de cada intervalo.

    Demonstra operadores de acumulador condicional (``$cond``) dentro de ``$bucket``.
    """
    pipeline = [
        {
            "$bucket": {
                "groupBy":    "$metrics.rating",
                "boundaries": [1, 2, 3, 4, 5, 6],
                "default":    "Outro",
                "output": {
                    "count":     {"$sum": 1},
                    "positivos": {"$sum": {"$cond": [{"$eq": ["$metrics.sentiment", "Positive"]}, 1, 0]}},
                    "negativos": {"$sum": {"$cond": [{"$eq": ["$metrics.sentiment", "Negative"]}, 1, 0]}},
                    "avgRating": {"$avg": "$metrics.rating"},
                },
            }
        },
        {
            "$project": {
                "rating":    "$_id",
                "count":     1,
                "avgRating": {"$round": ["$avgRating", 2]},
                "nss": {
                    "$subtract": [
                        {"$multiply": [{"$divide": ["$positivos", "$count"]}, 100]},
                        {"$multiply": [{"$divide": ["$negativos", "$count"]}, 100]},
                    ]
                },
                "_id": 0,
            }
        },
    ]
    try:
        result = list(collection.aggregate(pipeline))
        logger.info("$bucket ratings: %d intervalos.", len(result))
        return result
    except Exception as exc:
        logger.warning("$bucket ratings falhou: %s", exc)
        return []


# ──────────────────────────────────────────────────────────────
# $UNWIND + KCI — Keyword Correlation Index
# ──────────────────────────────────────────────────────────────

def run_kci_pipeline(collection: Any, min_freq: int = 2) -> list[dict]:
    """
    Calcula o Keyword Correlation Index (KCI) no servidor MongoDB:

        KCI(k) = (ocorrências de k em reviews Negative / total ocorrências de k) × 100

    Pipeline: ``$unwind`` → ``$group`` → ``$project`` (calculando KCI inline).
    O índice composto ``(sentiment, keywords)`` é activado pelo ``$match`` inicial.
    """
    pipeline = [
        {"$unwind": "$content.keywords"},
        {
            "$group": {
                "_id":        "$content.keywords",
                "frequencia": {"$sum": 1},
                "avgRating":  {"$avg": "$metrics.rating"},
                "negCount":   {"$sum": {"$cond": [{"$eq": ["$metrics.sentiment", "Negative"]}, 1, 0]}},
            }
        },
        {"$match": {"frequencia": {"$gte": min_freq}}},
        {
            "$project": {
                "keyword":    "$_id",
                "frequencia": 1,
                "nota_media": {"$round": ["$avgRating", 2]},
                "kci": {
                    "$multiply": [
                        {"$divide": ["$negCount", "$frequencia"]},
                        100,
                    ]
                },
                "_id": 0,
            }
        },
        {"$sort": {"kci": -1}},
        {"$limit": 20},
    ]
    try:
        result = list(collection.aggregate(pipeline))
        logger.info("KCI pipeline: %d keywords.", len(result))
        return result
    except Exception as exc:
        logger.warning("KCI pipeline falhou: %s", exc)
        return []


# ──────────────────────────────────────────────────────────────
# DOUBLE-GROUP — Quality Decay Rate
# ──────────────────────────────────────────────────────────────

def run_quality_decay(collection: Any) -> list[dict]:
    """
    Padrão "double-group": identifica produtos em decaimento de qualidade.

    Estágio 1 — ``$group`` mensal por produto.
    Estágio 2 — ``$group`` consolidador: empurra histórico para array via ``$push``.
    Extrai último e penúltimo mês com ``$arrayElemAt`` e calcula a queda percentual.
    """
    pipeline = [
        {
            "$group": {
                "_id": {
                    "produto": "$product.name",
                    "mes":     {"$dateToString": {"format": "%Y-%m", "date": "$metadata.timestamp"}},
                },
                "notaMedia": {"$avg": "$metrics.rating"},
            }
        },
        {"$sort": {"_id.produto": 1, "_id.mes": 1}},
        {
            "$group": {
                "_id":      "$_id.produto",
                "historico": {"$push": {"mes": "$_id.mes", "nota": "$notaMedia"}},
            }
        },
        {
            "$project": {
                "produto":      "$_id",
                "ultimoMes":    {"$arrayElemAt": ["$historico", -1]},
                "penultimoMes": {"$arrayElemAt": ["$historico", -2]},
                "_id": 0,
            }
        },
        {
            "$project": {
                "produto":    1,
                "ultimoMes":  1,
                "penultimoMes": 1,
                "quedaPct": {
                    "$cond": {
                        "if":   {"$gt": ["$penultimoMes.nota", 0]},
                        "then": {
                            "$multiply": [
                                {"$divide": [
                                    {"$subtract": ["$penultimoMes.nota", "$ultimoMes.nota"]},
                                    "$penultimoMes.nota",
                                ]},
                                100,
                            ]
                        },
                        "else": 0,
                    }
                },
            }
        },
        {"$match": {"penultimoMes": {"$exists": True}, "quedaPct": {"$gte": 0}}},
        {"$sort": {"quedaPct": -1}},
    ]
    try:
        result = list(collection.aggregate(pipeline))
        logger.info("Quality decay: %d produtos analisados.", len(result))
        return result
    except Exception as exc:
        logger.warning("Quality decay pipeline falhou: %s", exc)
        return []


# ──────────────────────────────────────────────────────────────
# $GEONEAR — NSS por Proximidade
# ──────────────────────────────────────────────────────────────

def run_geo_nss(collection: Any, center_lon: float = -9.1393, center_lat: float = 38.7223,
                max_distance_m: float = 600_000) -> list[dict]:
    """
    Usa ``$geoNear`` (requer índice 2dsphere) para calcular NSS por cidade,
    ordenando as cidades por distância ao ponto de referência dado.

    O operador ``$geoNear`` é obrigatoriamente o **primeiro estágio** da pipeline
    e activa o R-tree esférico do índice 2dsphere para filtro geográfico.

    Parameters
    ----------
    center_lon, center_lat : ponto de referência (padrão: Lisboa)
    max_distance_m         : raio máximo em metros (padrão: 600 km, cobre Portugal)
    """
    pipeline = [
        {
            "$geoNear": {
                "near":          {"type": "Point", "coordinates": [center_lon, center_lat]},
                "distanceField": "distancia_m",
                "maxDistance":   max_distance_m,
                "spherical":     True,
                "key":           "customer.location.coordinates",
            }
        },
        {
            "$group": {
                "_id":       "$customer.location.city",
                "total":     {"$sum": 1},
                "notaMedia": {"$avg": "$metrics.rating"},
                "positivos": {"$sum": {"$cond": [{"$eq": ["$metrics.sentiment", "Positive"]}, 1, 0]}},
                "negativos": {"$sum": {"$cond": [{"$eq": ["$metrics.sentiment", "Negative"]}, 1, 0]}},
                "distancia_m": {"$avg": "$distancia_m"},
                "lat": {"$first": {"$arrayElemAt": ["$customer.location.coordinates.coordinates", 1]}},
                "lon": {"$first": {"$arrayElemAt": ["$customer.location.coordinates.coordinates", 0]}},
            }
        },
        {
            "$project": {
                "cidade":     "$_id",
                "total":      1,
                "notaMedia":  {"$round": ["$notaMedia", 2]},
                "distancia_km": {"$round": [{"$divide": ["$distancia_m", 1000]}, 1]},
                "nss": {
                    "$subtract": [
                        {"$multiply": [{"$divide": ["$positivos", "$total"]}, 100]},
                        {"$multiply": [{"$divide": ["$negativos", "$total"]}, 100]},
                    ]
                },
                "lat": 1, "lon": 1,
                "_id": 0,
            }
        },
        {"$sort": {"distancia_km": 1}},
    ]
    try:
        result = list(collection.aggregate(pipeline))
        logger.info("$geoNear NSS: %d cidades.", len(result))
        return result
    except Exception as exc:
        logger.warning("$geoNear pipeline falhou: %s", exc)
        return []
