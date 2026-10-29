
-- Create views for dashboard reporting.

-- Recreate views on each run.
DROP VIEW IF EXISTS v_latest_values;
DROP VIEW IF EXISTS v_yearly_change;
DROP VIEW IF EXISTS v_indicator_coverage;
DROP VIEW IF EXISTS v_indicator_data;

-- Combine observations with indicator metadata and display values.
CREATE VIEW v_indicator_data AS
SELECT i.indicator_code,
       i.theme,
       i.short_label,
       i.unit,
       o.year,
       o.value             AS raw_value,
       o.value / i.divisor AS value
FROM observations o
JOIN indicators i ON i.indicator_code = o.indicator_code;

-- Calculate year-on-year changes where consecutive years are available.
CREATE VIEW v_yearly_change AS
WITH with_previous AS (
    SELECT indicator_code, theme, short_label, unit, year, value,
           LAG(year) OVER w AS prev_year,
           LAG(value) OVER w AS prev_value
    FROM v_indicator_data
    WINDOW w AS (PARTITION BY indicator_code ORDER BY year)
)
SELECT indicator_code, theme, short_label, unit, year, value,
       prev_year, prev_value,
       CASE
           WHEN year - prev_year = 1
           THEN value - prev_value
       END AS change_abs,
       CASE
           WHEN year - prev_year = 1 AND prev_value <> 0
           THEN (value - prev_value) / ABS(prev_value) * 100
       END AS change_pct
FROM with_previous;

-- Return the latest observation for each indicator.
CREATE VIEW v_latest_values AS
SELECT DISTINCT ON (indicator_code)
       indicator_code, theme, short_label, unit,
       year AS latest_year,
       value AS latest_value,
       change_abs,
       change_pct
FROM v_yearly_change
ORDER BY indicator_code, year DESC;

-- Summarize data coverage and indicator definitions.
CREATE VIEW v_indicator_coverage AS
SELECT i.indicator_code,
       i.theme,
       i.short_label,
       i.unit,
       i.official_name,
       i.source_organization,
       i.definition,
       MIN(o.year) AS first_year,
       MAX(o.year) AS last_year,
       COUNT(*) AS years_with_data,
       MAX(o.year) - MIN(o.year) + 1 - COUNT(*) AS gap_years
FROM indicators i
JOIN observations o ON o.indicator_code = i.indicator_code
GROUP BY i.indicator_code;
