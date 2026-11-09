-- Page 1 · L'international : part du CA hors de France, par trimestre.
SELECT STRFTIME(DATE_TRUNC('quarter', date_commande), '%Y') || '-T' || QUARTER(date_commande) AS trimestre,
       pays,
       COUNT(*) AS commandes,
       ROUND(SUM(montant_net_ht)) AS ca_ht,
       ROUND(SUM(montant_net_ht) / SUM(SUM(montant_net_ht)) OVER (PARTITION BY DATE_TRUNC('quarter', date_commande)), 3)
           AS part_ca_trimestre
FROM commandes
GROUP BY DATE_TRUNC('quarter', date_commande), trimestre, pays
ORDER BY trimestre, ca_ht DESC;
