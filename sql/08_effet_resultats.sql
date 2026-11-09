-- Page 5 · Les résultats font-ils vendre ? Étude d'événement autour des moments sportifs RÉELS.
-- Pour chaque moment (qualification, finale, victoire ou défaite en playoffs/international), on compare
-- le CA HT des jours J-3 à J+7 à une référence : la médiane du CA des jours J-24 à J-4 (hors promotions).
-- Pour ne pas mélanger les effets, un moment est EXCLU de l'étude (retenu_etude = 0) s'il suit un autre
-- moment de moins de 3 jours, ou s'il tombe près du lancement d'une collection (de J-7 à J+3).
WITH jour AS (
    SELECT c.date_commande AS date,
           SUM(li.montant_ht) AS ca_ht,
           SUM(li.montant_ht) FILTER (WHERE p.famille = 'maillot') AS ca_maillots_ht
    FROM lignes li JOIN commandes c USING (order_id) JOIN produits p USING (product_id)
    GROUP BY 1
),
cal AS (
    SELECT CAST(d AS DATE) AS date FROM generate_series(DATE '2025-01-01', DATE '2026-11-08', INTERVAL 1 DAY) t(d)
),
jour_complet AS (
    SELECT cal.date, COALESCE(j.ca_ht, 0) AS ca_ht, COALESCE(j.ca_maillots_ht, 0) AS ca_maillots_ht,
           CASE WHEN cal.date >= DATE '2026-11-02' OR cal.date BETWEEN DATE '2026-03-01' AND DATE '2026-04-30' THEN 1 ELSE 0 END AS periode_promo
    FROM cal LEFT JOIN jour j USING (date)
),
lancements AS (
    SELECT collection, MIN(date_lancement) AS date_lancement
    FROM produits WHERE famille <> 'service' GROUP BY collection
),
moments AS (
    SELECT date, competition, phase, resultat, adversaire,
           CASE WHEN enjeu LIKE 'Qualifiée%' THEN 'Qualification'
                WHEN phase = 'Finale' THEN 'Finale'
                WHEN resultat = 'V' THEN 'Victoire'
                ELSE 'Défaite' END AS type_moment
    FROM resultats
    WHERE phase NOT LIKE 'Fin de saison%'
      AND date BETWEEN DATE '2025-01-25' AND DATE '2026-11-01'
),
moments_flag AS (
    SELECT m.*,
           CASE WHEN EXISTS (SELECT 1 FROM moments o WHERE o.date BETWEEN m.date - INTERVAL 3 DAY AND m.date - INTERVAL 1 DAY)
                    THEN 'suit un autre moment de moins de 3 jours'
                WHEN EXISTS (SELECT 1 FROM lancements l WHERE l.date_lancement BETWEEN m.date - INTERVAL 7 DAY AND m.date + INTERVAL 3 DAY)
                    THEN 'proche du lancement d''une collection'
                ELSE NULL END AS raison_exclusion
    FROM moments m
),
reference AS (
    SELECT m.date AS date_moment,
           MEDIAN(j.ca_ht) AS ref_ca_ht, MEDIAN(j.ca_maillots_ht) AS ref_ca_maillots_ht
    FROM moments m
    JOIN jour_complet j ON j.date BETWEEN m.date - INTERVAL 24 DAY AND m.date - INTERVAL 4 DAY
    WHERE j.periode_promo = 0
    GROUP BY m.date
)
SELECT m.date AS date_moment, m.competition, m.phase, m.resultat, m.adversaire, m.type_moment,
       CASE WHEN m.raison_exclusion IS NULL THEN 1 ELSE 0 END AS retenu_etude,
       m.raison_exclusion,
       DATE_DIFF('day', m.date, j.date) AS jour_relatif,
       ROUND(j.ca_ht, 2) AS ca_ht,
       ROUND(r.ref_ca_ht, 2) AS ref_ca_ht,
       ROUND(j.ca_ht / NULLIF(r.ref_ca_ht, 0), 3) AS indice_ca,
       ROUND(j.ca_maillots_ht / NULLIF(r.ref_ca_maillots_ht, 0), 3) AS indice_ca_maillots
FROM moments_flag m
JOIN reference r ON r.date_moment = m.date
JOIN jour_complet j ON j.date BETWEEN m.date - INTERVAL 3 DAY AND m.date + INTERVAL 7 DAY
ORDER BY m.date, jour_relatif;
