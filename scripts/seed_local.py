import asyncio
import math
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from currency_tracker.config.settings import get_settings
from currency_tracker.storage.models import (
    Base,
    Currency,
    DataSource,
    ExchangeRate,
    Alert,
    ModelRegistry,
    Prediction,
    AlertHistory,
)


CURRENCIES = [
    ('BRL', 'Real Brasileiro', 'R$', 'major'),
    ('USD', 'Dolar Americano', '$', 'major'),
    ('EUR', 'Euro', 'E', 'major'),
    ('GBP', 'Libra Esterlina', 'L', 'major'),
    ('JPY', 'Iene Japones', 'Y', 'major'),
]

SOURCES = [
    ('awesomeapi', 'AwesomeAPI', 'https://economia.awesomeapi.com.br', True),
    ('exchangerate', 'ExchangeRate-API', 'https://v6.exchangerate-api.com', False),
    ('bcb', 'Banco Central do Brasil', 'https://api.bcb.gov.br', False),
]

CURRENCY_IDS = {}


async def seed():
    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        await session.execute(AlertHistory.__table__.delete())
        await session.execute(Prediction.__table__.delete())
        await session.execute(ExchangeRate.__table__.delete())
        await session.execute(Alert.__table__.delete())
        await session.execute(ModelRegistry.__table__.delete())
        await session.execute(DataSource.__table__.delete())
        await session.execute(Currency.__table__.delete())
        await session.commit()

        for code, name, symbol, category in CURRENCIES:
            cur = Currency(code=code, name=name, symbol=symbol, symbol_native=symbol,
                           decimal_places=4, is_base=(code == 'BRL'), is_active=True,
                           category=category, priority='high')
            session.add(cur)
        await session.commit()

        result = await session.execute(select(Currency))
        for cur in result.scalars():
            CURRENCY_IDS[cur.code] = cur.id

        for name, display, url, key_required in SOURCES:
            session.add(DataSource(name=name, display_name=display, base_url=url,
                                   api_key_required=key_required, rate_limit_per_second=10,
                                   is_active=True, priority=1))
        await session.commit()

        source_result = await session.execute(select(DataSource))
        source_ids = {s.name: s.id for s in source_result.scalars()}

        base_id = CURRENCY_IDS['BRL']
        bom_source = source_ids['awesomeapi']
        rates_data = {'USD': 5.24, 'EUR': 5.71, 'GBP': 6.66, 'JPY': 3.45}

        now = datetime.utcnow()
        count = 0
        for quote, base_rate in rates_data.items():
            quote_id = CURRENCY_IDS[quote]
            for day in range(120, -1, -1):
                ts = now.replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=day)
                seasonal = 0.02 * math.sin((120 - day) / 9.0)
                mid = base_rate * (1 + seasonal + ((120 - day) * 0.00035))
                bid = round(mid - 0.012, 6)
                ask = round(mid + 0.012, 6)
                rate = round(mid, 6)
                spread = round((ask - bid) / bid * 100, 4)
                session.add(ExchangeRate(uuid=__import__('uuid').uuid4(),
                                         base_currency_id=base_id, quote_currency_id=quote_id,
                                         rate=Decimal(str(rate)), bid=Decimal(str(bid)),
                                         ask=Decimal(str(ask)), spread=Decimal(str(spread)),
                                         rate_type='commercial', source_id=bom_source,
                                         rate_timestamp=ts, collected_at=ts))
                count += 1
        await session.commit()
        print(f"Seeded {count} exchange rates")

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(seed())
    print("Local database seeded successfully")