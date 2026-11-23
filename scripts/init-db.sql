-- ============================================
-- CurrencyTracker - Database Initialization
-- ============================================
-- This script runs automatically when PostgreSQL container starts

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas if needed
-- CREATE SCHEMA IF NOT EXISTS currency_tracker;

-- Set timezone
SET timezone = 'America/Sao_Paulo';

-- ============================================
-- Initial Data: Currencies
-- ============================================
INSERT INTO currencies (code, name, symbol, symbol_native, decimal_places, is_base, is_active, category, priority, volatility)
VALUES
    ('BRL', 'Real Brasileiro', 'R$', 'R$', 4, true, true, 'base', 'base', 'medium'),
    ('USD', 'Dólar Americano', '$', 'US$', 4, false, true, 'major', 'high', 'low'),
    ('EUR', 'Euro', '€', '€', 4, false, true, 'major', 'high', 'low'),
    ('GBP', 'Libra Esterlina', '£', '£', 4, false, true, 'major', 'high', 'low'),
    ('JPY', 'Iene Japonês', '¥', '円', 2, false, true, 'major', 'high', 'low'),
    ('CHF', 'Franco Suíço', 'CHF', 'CHF', 4, false, true, 'major', 'high', 'low'),
    ('CAD', 'Dólar Canadense', '$', '$', 4, false, true, 'major', 'medium', 'low'),
    ('AUD', 'Dólar Australiano', '$', '$', 4, false, true, 'major', 'medium', 'low'),
    ('CNY', 'Yuan Chinês', '¥', '元', 4, false, true, 'brics', 'high', 'low'),
    ('INR', 'Rúpia Indiana', '₹', '₹', 2, false, true, 'brics', 'medium', 'medium'),
    ('ZAR', 'Rand Sul-Africano', 'R', 'R', 4, false, true, 'brics', 'medium', 'high'),
    ('ARS', 'Peso Argentino', '$', '$', 2, false, true, 'latam', 'high', 'very_high'),
    ('CLP', 'Peso Chileno', '$', '$', 0, false, true, 'latam', 'medium', 'medium'),
    ('COP', 'Peso Colombiano', '$', '$', 0, false, true, 'latam', 'medium', 'medium'),
    ('MXN', 'Peso Mexicano', '$', '$', 4, false, true, 'latam', 'high', 'medium'),
    ('RUB', 'Rublo Russo', '₽', '₽', 4, false, true, 'emerging', 'high', 'high')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    symbol = EXCLUDED.symbol,
    symbol_native = EXCLUDED.symbol_native,
    decimal_places = EXCLUDED.decimal_places,
    is_base = EXCLUDED.is_base,
    is_active = EXCLUDED.is_active,
    category = EXCLUDED.category,
    priority = EXCLUDED.priority,
    volatility = EXCLUDED.volatility,
    updated_at = NOW();

-- ============================================
-- Initial Data: Data Sources
-- ============================================
INSERT INTO data_sources (name, display_name, base_url, api_key_required, rate_limit_per_second, is_active, priority, config)
VALUES
    ('awesomeapi', 'AwesomeAPI', 'https://economia.awesomeapi.com.br', false, 10, true, 10, '{}'),
    ('exchangerate', 'ExchangeRate-API', 'https://v6.exchangerate-api.com/v6', true, 5, true, 8, '{}'),
    ('alphavantage', 'Alpha Vantage', 'https://www.alphavantage.co/query', true, 5, true, 7, '{}'),
    ('bcb', 'Banco Central do Brasil (PTAX)', 'https://api.bcb.gov.br/dados/serie/bcdata.sgs', false, 10, true, 9, '{}'),
    ('yahoo', 'Yahoo Finance', 'https://query1.finance.yahoo.com', false, 20, true, 5, '{}'),
    ('twelvedata', 'Twelve Data', 'https://api.twelvedata.com', true, 8, true, 6, '{}')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    base_url = EXCLUDED.base_url,
    api_key_required = EXCLUDED.api_key_required,
    rate_limit_per_second = EXCLUDED.rate_limit_per_second,
    is_active = EXCLUDED.is_active,
    priority = EXCLUDED.priority,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================
-- Indexes for Performance
-- ============================================
-- Additional indexes beyond what SQLAlchemy creates
CREATE INDEX IF NOT EXISTS ix_exchange_rates_collected_at ON exchange_rates(collected_at DESC);
CREATE INDEX IF NOT EXISTS ix_predictions_created_at ON predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_alert_history_triggered_at ON alert_history(triggered_at DESC);

-- ============================================
-- Useful Views
-- ============================================

-- View: Latest rates per pair per source
CREATE OR REPLACE VIEW latest_rates AS
SELECT DISTINCT ON (er.base_currency_id, er.quote_currency_id, er.source_id)
    er.*,
    bc.code as base_code,
    qc.code as quote_code,
    ds.name as source_name
FROM exchange_rates er
JOIN currencies bc ON er.base_currency_id = bc.id
JOIN currencies qc ON er.quote_currency_id = qc.id
JOIN data_sources ds ON er.source_id = ds.id
ORDER BY er.base_currency_id, er.quote_currency_id, er.source_id, er.rate_timestamp DESC;

-- View: Rate statistics (24h)
CREATE OR REPLACE VIEW rate_stats_24h AS
SELECT
    bc.code as base_currency,
    qc.code as quote_currency,
    ds.name as source,
    COUNT(*) as count,
    AVG(er.rate) as avg_rate,
    MIN(er.rate) as min_rate,
    MAX(er.rate) as max_rate,
    STDDEV(er.rate) as stddev_rate,
    AVG(er.spread) as avg_spread,
    MAX(er.rate_timestamp) as last_update
FROM exchange_rates er
JOIN currencies bc ON er.base_currency_id = bc.id
JOIN currencies qc ON er.quote_currency_id = qc.id
JOIN data_sources ds ON er.source_id = ds.id
WHERE er.rate_timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY bc.code, qc.code, ds.name;

-- View: Active alerts with current rates
CREATE OR REPLACE VIEW active_alerts_status AS
SELECT
    a.*,
    bc.code as base_currency,
    qc.code as quote_currency,
    er.rate as current_rate,
    er.rate_timestamp as rate_timestamp,
    CASE
        WHEN a.condition_type = 'above' AND er.rate > a.threshold_value THEN true
        WHEN a.condition_type = 'below' AND er.rate < a.threshold_value THEN false
        ELSE false
    END as currently_triggered
FROM alerts a
JOIN currencies bc ON a.base_currency_id = bc.id
JOIN currencies qc ON a.quote_currency_id = qc.id
LEFT JOIN LATERAL (
    SELECT rate, rate_timestamp
    FROM exchange_rates er
    WHERE er.base_currency_id = a.base_currency_id
      AND er.quote_currency_id = a.quote_currency_id
    ORDER BY er.rate_timestamp DESC
    LIMIT 1
) er ON true
WHERE a.is_active = true;

-- ============================================
-- Functions
-- ============================================

-- Function to clean old exchange rates (keep last 2 years)
CREATE OR REPLACE FUNCTION clean_old_rates()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM exchange_rates
    WHERE rate_timestamp < NOW() - INTERVAL '2 years'
    AND id NOT IN (
        -- Keep at least 1 rate per day per pair per source
        SELECT DISTINCT ON (base_currency_id, quote_currency_id, source_id, DATE(rate_timestamp))
        id
        FROM exchange_rates
        WHERE rate_timestamp < NOW() - INTERVAL '2 years'
        ORDER BY base_currency_id, quote_currency_id, source_id, DATE(rate_timestamp), rate_timestamp DESC
    );
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get rate change percentage
CREATE OR REPLACE FUNCTION get_rate_change_pct(
    p_base_currency VARCHAR(3),
    p_quote_currency VARCHAR(3),
    p_hours INTEGER DEFAULT 24
)
RETURNS DECIMAL AS $$
DECLARE
    v_current_rate DECIMAL;
    v_past_rate DECIMAL;
    v_change_pct DECIMAL;
BEGIN
    -- Current rate
    SELECT er.rate INTO v_current_rate
    FROM exchange_rates er
    JOIN currencies bc ON er.base_currency_id = bc.id
    JOIN currencies qc ON er.quote_currency_id = qc.id
    WHERE bc.code = p_base_currency
      AND qc.code = p_quote_currency
    ORDER BY er.rate_timestamp DESC
    LIMIT 1;

    -- Rate from p_hours ago
    SELECT er.rate INTO v_past_rate
    FROM exchange_rates er
    JOIN currencies bc ON er.base_currency_id = bc.id
    JOIN currencies qc ON er.quote_currency_id = qc.id
    WHERE bc.code = p_base_currency
      AND qc.code = p_quote_currency
      AND er.rate_timestamp <= NOW() - (p_hours || ' hours')::INTERVAL
    ORDER BY er.rate_timestamp DESC
    LIMIT 1;

    IF v_current_rate IS NOT NULL AND v_past_rate IS NOT NULL AND v_past_rate != 0 THEN
        v_change_pct := ((v_current_rate - v_past_rate) / v_past_rate) * 100;
        RETURN v_change_pct;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Grant Permissions (if using specific users)
-- ============================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO currency_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO currency_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO currency_user;