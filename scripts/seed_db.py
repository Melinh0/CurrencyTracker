#!/usr/bin/env python
# ============================================
# CurrencyTracker - Database Seeding Script
# ============================================

import asyncio
import yaml
from pathlib import Path
from decimal import Decimal

from currency_tracker.storage.repository import RateRepository
from currency_tracker.config.settings import get_currency_config


async def seed_database():
    """Popula banco com dados iniciais"""
    print("🌱 Iniciando seed do banco de dados...")

    repo = RateRepository()
    await repo.initialize()

    config = get_currency_config()

    # 1. Insere moedas
    print("\n📦 Inserindo moedas...")
    for currency_data in config.currencies:
        currency = await repo.upsert_currency(
            code=currency_data["code"],
            name=currency_data["name"],
            symbol=currency_data.get("symbol"),
            symbol_native=currency_data.get("symbol_native"),
            decimal_places=currency_data.get("decimal_places", 4),
            is_base=currency_data.get("is_base", False),
            category=currency_data.get("category", "other"),
            priority=currency_data.get("priority", "medium"),
            volatility=currency_data.get("volatility", "medium")
        )
        print(f"  ✓ {currency.code} - {currency.name}")

    # Garante que BRL existe como base
    base_config = config.currencies[-1] if config.currencies[-1].get("is_base") else None
    if base_config:
        await repo.upsert_currency(
            code=base_config["code"],
            name=base_config["name"],
            symbol=base_config.get("symbol"),
            symbol_native=base_config.get("symbol_native"),
            decimal_places=base_config.get("decimal_places", 4),
            is_base=True,
            category=base_config.get("category", "base"),
            priority=base_config.get("priority", "base"),
            volatility=base_config.get("volatility", "medium")
        )
        print(f"  ✓ {base_config['code']} (BASE)")

    # 2. Insere fontes de dados
    print("\n📡 Inserindo fontes de dados...")
    sources = [
        ("awesomeapi", "AwesomeAPI", "https://economia.awesomeapi.com.br", False, 10, 10),
        ("exchangerate", "ExchangeRate-API", "https://v6.exchangerate-api.com/v6", True, 5, 8),
        ("alphavantage", "Alpha Vantage", "https://www.alphavantage.co/query", True, 5, 7),
        ("bcb", "Banco Central do Brasil (PTAX)", "https://api.bcb.gov.br/dados/serie/bcdata.sgs", False, 10, 9),
        ("yahoo", "Yahoo Finance", "https://query1.finance.yahoo.com", False, 20, 5),
        ("twelvedata", "Twelve Data", "https://api.twelvedata.com", True, 8, 6),
    ]

    for name, display, url, key_req, rate_limit, priority in sources:
        source = await repo.upsert_source(
            name=name,
            display_name=display,
            base_url=url,
            api_key_required=key_req,
            rate_limit_per_second=rate_limit,
            priority=priority,
            is_active=True
        )
        print(f"  ✓ {source.name} - {source.display_name}")

    print("\n✅ Seed concluído com sucesso!")

    await repo.close()


if __name__ == "__main__":
    asyncio.run(seed_database())