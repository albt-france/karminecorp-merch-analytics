-- Calendrier (table de dates pour Power BI) avec les moments sportifs RÉELS de la KC
-- et les périodes commerciales (soldes, Black Friday : hypothèses du générateur).
WITH jours AS (
    SELECT CAST(d AS DATE) AS date
    FROM generate_series(DATE '2025-01-01', DATE '2026-11-08', INTERVAL 1 DAY) t(d)
),
matchs AS (
    SELECT date,
           STRING_AGG(competition || ' · ' || phase || ' · ' || resultat || ' ' || score_kc || '-' || score_adv
                      || ' contre ' || COALESCE(adversaire, ''), ' | ') AS match_kc,
           MAX(CASE WHEN enjeu LIKE 'Qualifiée%' THEN 1 ELSE 0 END) AS jour_qualification,
           MAX(CASE WHEN phase = 'Finale' THEN 1 ELSE 0 END) AS jour_finale
    FROM resultats
    WHERE phase NOT LIKE 'Fin de saison%'
    GROUP BY date
)
SELECT j.date,
       YEAR(j.date) AS annee,
       MONTH(j.date) AS mois,
       STRFTIME(j.date, '%Y-%m') AS annee_mois,
       ISODOW(j.date) AS jour_semaine,                      -- 1 = lundi
       CASE WHEN ISODOW(j.date) >= 6 THEN 1 ELSE 0 END AS week_end,
       CASE WHEN m.date IS NOT NULL THEN 1 ELSE 0 END AS jour_de_match_kc,
       m.match_kc,
       COALESCE(m.jour_qualification, 0) AS jour_qualification,
       COALESCE(m.jour_finale, 0) AS jour_finale,
       CASE WHEN j.date >= DATE '2026-11-02' THEN 1 ELSE 0 END AS black_friday,
       CASE WHEN j.date BETWEEN DATE '2026-03-01' AND DATE '2026-04-30' THEN 1 ELSE 0 END AS soldes
FROM jours j
LEFT JOIN matchs m USING (date)
ORDER BY j.date;
