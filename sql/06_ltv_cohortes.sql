-- Page 3 · Combien rapporte un fan dans le temps ? CA HT cumulé par client, par cohorte de premier achat.
-- Seuls les clients dont le premier achat tombe dans la période (2025-2026) sont gardés.
-- Biais de censure : le mois k d'une cohorte n'est affiché que si TOUTE la cohorte a pu être observée
-- k mois entiers (fin du mois de cohorte + k mois <= date de fin des données).
WITH nouveaux AS (
    SELECT client_id, DATE_TRUNC('month', MIN(date_commande)) AS cohorte
    FROM commandes
    WHERE client_id IN (SELECT client_id FROM clients WHERE client_avant_2025 = 0)
    GROUP BY client_id
),
taille AS (SELECT cohorte, COUNT(*) AS clients FROM nouveaux GROUP BY cohorte),
mois AS (SELECT CAST(range AS INTEGER) AS k FROM range(0, 23)),
ca AS (
    SELECT n.cohorte, DATE_DIFF('month', n.cohorte, DATE_TRUNC('month', c.date_commande)) AS k,
           SUM(c.montant_net_ht) AS ca_ht
    FROM commandes c JOIN nouveaux n USING (client_id)
    GROUP BY 1, 2
),
grille AS (
    SELECT t.cohorte, t.clients, m.k, COALESCE(ca.ca_ht, 0) AS ca_ht
    FROM taille t CROSS JOIN mois m
    LEFT JOIN ca ON ca.cohorte = t.cohorte AND ca.k = m.k
    WHERE t.cohorte + INTERVAL 1 MONTH + m.k * INTERVAL 1 MONTH <= DATE '2026-11-08' + INTERVAL 1 DAY
)
SELECT cohorte, clients, k AS mois_depuis_premier_achat,
       ROUND(SUM(ca_ht) OVER (PARTITION BY cohorte ORDER BY k) / clients, 2) AS ca_cumule_par_client_ht
FROM grille
ORDER BY cohorte, k;
