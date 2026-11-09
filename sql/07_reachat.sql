-- Page 3 · Les fans reviennent-ils ? Taux de réachat à 90 et 180 jours, par trimestre de premier achat,
-- et part des fans « multi-drops » (achats dans au moins 2 collections différentes).
-- Un client n'entre dans le calcul à N jours que s'il a pu être observé N jours (pas de biais de censure).
WITH premiers AS (
    SELECT client_id, MIN(date_commande) AS premier
    FROM commandes
    WHERE client_id IN (SELECT client_id FROM clients WHERE client_avant_2025 = 0)
    GROUP BY client_id
),
second AS (
    SELECT p.client_id, p.premier, MIN(c.date_commande) AS deuxieme
    FROM premiers p
    LEFT JOIN commandes c ON c.client_id = p.client_id AND c.date_commande > p.premier
    GROUP BY p.client_id, p.premier
),
collections AS (
    SELECT c.client_id, COUNT(DISTINCT pr.collection) AS nb_collections
    FROM lignes li
    JOIN commandes c USING (order_id)
    JOIN produits pr USING (product_id)
    WHERE pr.collection NOT IN ('Accessoires') AND pr.famille <> 'service'
    GROUP BY c.client_id
)
SELECT STRFTIME(DATE_TRUNC('quarter', s.premier), '%Y') || '-T' || QUARTER(s.premier) AS trimestre_premier_achat,
       COUNT(*) AS nouveaux_clients,
       ROUND(AVG(CASE WHEN s.deuxieme <= s.premier + INTERVAL 90 DAY THEN 1.0 ELSE 0 END)
             FILTER (WHERE s.premier + INTERVAL 90 DAY <= DATE '2026-11-08'), 3) AS reachat_90j,
       ROUND(AVG(CASE WHEN s.deuxieme <= s.premier + INTERVAL 180 DAY THEN 1.0 ELSE 0 END)
             FILTER (WHERE s.premier + INTERVAL 180 DAY <= DATE '2026-11-08'), 3) AS reachat_180j,
       ROUND(AVG(CASE WHEN co.nb_collections >= 2 THEN 1.0 ELSE 0 END), 3) AS part_multi_drops
FROM second s
LEFT JOIN collections co USING (client_id)
GROUP BY 1
ORDER BY 1;
