-- Page 3 · Qui sont les fans qui achètent ? Segmentation RFM au 08/11/2026.
-- R = jours depuis le dernier achat, F = nombre de commandes 2025-2026, M = CA HT 2025-2026.
-- F a des seuils fixes (la plupart des clients n'ont qu'une commande : des quintiles n'auraient pas de sens).
WITH base AS (
    SELECT client_id,
           DATE_DIFF('day', MAX(date_commande), DATE '2026-11-08') AS recence_jours,
           COUNT(*) AS frequence,
           SUM(montant_net_ht) AS montant_ht,
           MIN(date_commande) AS premiere_commande
    FROM commandes
    GROUP BY client_id
),
scores AS (
    SELECT *,
           6 - NTILE(5) OVER (ORDER BY recence_jours) AS r,
           CASE WHEN frequence >= 6 THEN 5 WHEN frequence >= 4 THEN 4 WHEN frequence = 3 THEN 3
                WHEN frequence = 2 THEN 2 ELSE 1 END AS f,
           NTILE(5) OVER (ORDER BY montant_ht) AS m
    FROM base
)
SELECT s.client_id, s.recence_jours, s.frequence, ROUND(s.montant_ht, 2) AS montant_ht,
       s.r, s.f, s.m, s.r || s.f || s.m AS code_rfm,
       CASE WHEN s.r >= 4 AND s.f >= 4 THEN '1. Noyau dur'
            WHEN s.f >= 3 AND s.r >= 3 THEN '2. Fidèles'
            WHEN s.f >= 3 AND s.r <= 2 THEN '3. Fidèles à réactiver'
            WHEN s.f = 2 AND s.r >= 3 THEN '4. En train de s''attacher'
            WHEN s.f = 1 AND s.r >= 4 THEN '5. Nouveaux'
            WHEN s.f <= 2 AND s.r = 3 THEN '6. À relancer'
            ELSE '7. Endormis' END AS segment,
       c.pays, c.source_acquisition, c.client_avant_2025
FROM scores s
JOIN clients c USING (client_id)
ORDER BY s.montant_ht DESC;
