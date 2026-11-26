from typing import Dict, List, Optional, Type
from currency_tracker.collector.sources import BaseSource, AwesomeAPISource, ExchangeRateAPISource, AlphaVantageSource, BCBSource, YahooFinanceSource, TwelveDataSource
from currency_tracker.config.settings import get_settings, get_currency_config

class SourceFactory:
    _source_classes: Dict[str, Type[BaseSource]] = {'awesomeapi': AwesomeAPISource, 'exchangerate': ExchangeRateAPISource, 'alphavantage': AlphaVantageSource, 'bcb': BCBSource, 'yahoo': YahooFinanceSource, 'twelvedata': TwelveDataSource}

    def __init__(self):
        self.settings = get_settings()
        self.currency_config = get_currency_config()
        self._instances: Dict[str, BaseSource] = {}

    def create_source(self, name: str) -> Optional[BaseSource]:
        if name in self._instances:
            return self._instances[name]
        source_class = self._source_classes.get(name.lower())
        if not source_class:
            return None
        api_key = ''
        if name == 'awesomeapi':
            api_key = self.settings.api_keys.awesome_api_key
        elif name == 'exchangerate':
            api_key = self.settings.api_keys.exchange_rate_api_key
        elif name == 'alphavantage':
            api_key = self.settings.api_keys.alpha_vantage_api_key
        elif name == 'twelvedata':
            api_key = self.settings.api_keys.twelve_data_api_key
        instance = source_class(api_key=api_key)
        self._instances[name] = instance
        return instance

    def get_sources_for_currency(self, currency: str) -> List[BaseSource]:
        sources = []
        currency_info = self.currency_config.get_currency(currency)
        if currency_info:
            source_names = currency_info.get('sources', [])
        else:
            source_names = list(self._source_classes.keys())
        for name in source_names:
            source = self.create_source(name)
            if source:
                sources.append(source)
        return sources

    def get_all_sources(self) -> List[BaseSource]:
        sources = []
        for name in self._source_classes:
            source = self.create_source(name)
            if source:
                sources.append(source)
        return sources

    def get_source(self, name: str) -> Optional[BaseSource]:
        return self._instances.get(name) or self.create_source(name)

    async def close_all(self):
        for source in self._instances.values():
            if hasattr(source, 'close'):
                await source.close()
        self._instances.clear()
source_factory = SourceFactory()
