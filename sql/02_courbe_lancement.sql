-- Page 2 · À quoi ressemble un lancement ?
-- Ventes par jour depuis le lancement (J0 à J55), par collection, et part cumulée des 8 semaines.
-- Seules les collections lancées pendant la période ET observées 8 semaines entières sont gardées
-- (sinon les lancements récents paraîtraient plus « rapides » qu'ils ne le sont : biais de censure).
WITH coll AS (
    SELECT collection, MIN(date_lancement) AS lancement
    FROM produits
    WHERE famille <> 'service'
    GROUP BY collection
    HAVING MIN(date_lancement) >= DATE '2025-01-01'
       AND MIN(date_lancement) + INTERVAL 55 DAY <= DATE '2026-11-08'
),
jours AS (SELECT CAST(range AS INTEGER) AS jour FROM range(0, 56)),
v AS (
    SELECT p.collection, DATE_DIFF('day', co.lancement, c.date_commande) AS jour,
           SUM(li.quantite) AS unites, SUM(li.montant_ht) AS ca_ht
    FROM lignes li
    JOIN commandes c USING (order_id)
    JOIN produits p USING (product_id)
    JOIN coll co USING (collection)
    GROUP BY 1, 2
),
grille AS (
    SELECT co.collection, co.lancement, j.jour, COALESCE(v.unites, 0) AS unites, COALESCE(v.ca_ht, 0) AS ca_ht
    FROM coll co CROSS JOIN jours j
    LEFT JOIN v ON v.collection = co.collection AND v.jour = j.jour
)
SELECT collection, lancement, jour, unites, ROUND(ca_ht, 2) AS ca_ht,
       ROUND(SUM(unites) OVER (PARTITION BY collection ORDER BY jour)
             / SUM(unites) OVER (PARTITION BY collection), 4) AS part_cumulee_8_semaines
FROM grille
ORDER BY collection, jour;
