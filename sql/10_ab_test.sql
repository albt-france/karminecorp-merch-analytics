-- Page 5 · Test A/B (fictif) sur la page produit du maillot Worlds 2026.
-- A = page actuelle ; B = guide des tailles avec la taille portée par les joueurs.
-- La significativité (test z, bootstrap) est calculée dans le notebook.
SELECT variante,
       COUNT(*) AS sessions,
       SUM(a_converti) AS commandes,
       ROUND(AVG(a_converti), 4) AS taux_conversion,
       ROUND(SUM(ca_ttc) / COUNT(*), 3) AS ca_par_session_ttc,
       ROUND(SUM(ca_ttc) / NULLIF(SUM(a_converti), 0), 2) AS panier_moyen_ttc
FROM ab_test
GROUP BY variante
ORDER BY variante;
