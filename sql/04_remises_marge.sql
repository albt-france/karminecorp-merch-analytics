-- Page 2 · Que coûtent les remises ?
-- Ventes et marge par tranche de remise, en distinguant les soldes 2026 et le Black Friday 2026 du reste de l'année.
SELECT CASE WHEN c.date_commande BETWEEN DATE '2026-03-01' AND DATE '2026-04-30' THEN 'Soldes 2026'
            WHEN c.date_commande >= DATE '2026-11-02' THEN 'Black Friday 2026 (en cours)'
            ELSE 'Reste de l''année' END AS periode,
       CASE WHEN li.remise_pct = 0 THEN '1. Prix plein'
            WHEN li.remise_pct < 0.30 THEN '2. Moins de 30 %'
            WHEN li.remise_pct < 0.50 THEN '3. 30 à 49 %'
            WHEN li.remise_pct < 0.70 THEN '4. 50 à 69 %'
            ELSE '5. 70 % et plus' END AS tranche_remise,
       SUM(li.quantite) AS unites,
       ROUND(SUM(li.montant_ht)) AS ca_ht,
       ROUND(SUM(li.marge_ht)) AS marge_ht,
       ROUND(SUM(li.marge_ht) / SUM(li.montant_ht), 3) AS taux_marge,
       ROUND(SUM(li.marge_ht) / SUM(li.quantite), 2) AS marge_par_piece_ht
FROM lignes li
JOIN commandes c USING (order_id)
JOIN produits p USING (product_id)
WHERE p.famille <> 'service'
GROUP BY 1, 2
ORDER BY 1, 2;
