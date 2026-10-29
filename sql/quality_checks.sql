
-- Validate data quality in the Nepal economy database.

-- [MUST BE EMPTY] Indicators with no observations
SELECT i.indicator_code
FROM indicators i
LEFT JOIN observations o ON o.indicator_code = i.indicator_code
WHERE o.indicator_code IS NULL;

-- [MUST BE EMPTY] Duplicate indicator-year records
SELECT indicator_code, year, COUNT(*) AS times_found
FROM observations
GROUP BY indicator_code, year
HAVING COUNT(*) > 1;

-- [MUST BE EMPTY] Percentage values outside 0-100
SELECT indicator_code, year, value
FROM observations
WHERE indicator_code IN (
    'NV.AGR.TOTL.ZS', 'NV.IND.TOTL.ZS', 'NV.SRV.TOTL.ZS',
    'SP.URB.TOTL.IN.ZS', 'SL.UEM.TOTL.ZS',
    'EG.ELC.ACCS.ZS', 'IT.NET.USER.ZS'
)
AND (value < 0 OR value > 100);

-- [MUST BE EMPTY] Indicators expected to have positive values
SELECT indicator_code, year, value
FROM observations
WHERE indicator_code IN (
    'SP.POP.TOTL', 'NY.GDP.MKTP.CD', 'NY.GDP.PCAP.CD',
    'FI.RES.TOTL.CD', 'BX.TRF.PWKR.CD.DT', 'SP.DYN.LE00.IN'
)
AND value <= 0;

-- [MUST BE EMPTY] Values outside expected ranges
SELECT indicator_code, year, value
FROM observations
WHERE (indicator_code = 'SP.DYN.LE00.IN' AND (value < 30 OR value > 90))
   OR (indicator_code = 'FP.CPI.TOTL.ZG' AND (value < -20 OR value > 60))
   OR (indicator_code = 'NY.GDP.MKTP.KD.ZG' AND (value < -15 OR value > 25));

-- [MUST BE EMPTY] Observations dated in future years
SELECT indicator_code, year
FROM observations
WHERE year > EXTRACT(YEAR FROM CURRENT_DATE);

-- [MUST BE EMPTY] Remittance-to-GDP consistency
SELECT r.year,
       ROUND(r.value / g.value * 100, 2) AS calculated_pct,
       ROUND(p.value, 2) AS reported_pct
FROM observations r
JOIN observations g
    ON g.year = r.year
   AND g.indicator_code = 'NY.GDP.MKTP.CD'
JOIN observations p
    ON p.year = r.year
   AND p.indicator_code = 'BX.TRF.PWKR.DT.GD.ZS'
WHERE r.indicator_code = 'BX.TRF.PWKR.CD.DT'
  AND ABS(r.value / g.value * 100 - p.value) > 0.05;

-- [INFO] Missing years within each indicator's recorded history
WITH span AS (
    SELECT indicator_code,
           MIN(year) AS first_year,
           MAX(year) AS last_year
    FROM observations
    GROUP BY indicator_code
)
SELECT s.indicator_code, y.year AS missing_year
FROM span s
CROSS JOIN generate_series(s.first_year, s.last_year) AS y(year)
LEFT JOIN observations o
    ON o.indicator_code = s.indicator_code
   AND o.year = y.year
WHERE o.year IS NULL
ORDER BY s.indicator_code, y.year;

-- [INFO] Indicators lagging behind the latest available year
SELECT i.short_label,
       MAX(o.year) AS latest_year,
       (SELECT MAX(year) FROM observations) - MAX(o.year) AS years_behind
FROM observations o
JOIN indicators i ON i.indicator_code = o.indicator_code
GROUP BY i.short_label
HAVING MAX(o.year) < (SELECT MAX(year) FROM observations)
ORDER BY i.short_label;

-- [INFO] Sector shares for the latest six available years
SELECT year, ROUND(SUM(value), 1) AS total_pct
FROM observations
WHERE indicator_code IN (
    'NV.AGR.TOTL.ZS', 'NV.IND.TOTL.ZS', 'NV.SRV.TOTL.ZS'
)
GROUP BY year
HAVING COUNT(*) = 3
ORDER BY year DESC
LIMIT 6;
