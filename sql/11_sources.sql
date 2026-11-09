-- Pages 1 et 3 · D'où viennent les commandes ? Attribution par source (dernier clic simulé),
-- en distinguant les jours de match RÉELS de la KC des autres jours.
WITH matchs AS (SELECT DISTINCT date FROM resultats WHERE phase NOT LIKE 'Fin de saison%'),
c AS (
    SELECT co.*, CASE WHEN m.date IS NOT NULL THEN 'Jour de match KC' ELSE 'Autre jour' END AS type_jour
    FROM commandes co
    LEFT JOIN matchs m ON m.date = co.date_commande
)
SELECT source, type_jour,
       COUNT(*) AS commandes,
       ROUND(SUM(montant_net_ht)) AS ca_ht,
       ROUND(AVG(1 - client_deja_acheteur), 3) AS part_nouveaux_clients,
       ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY type_jour), 3) AS part_des_commandes_du_type_de_jour
FROM c
GROUP BY source, type_jour
ORDER BY type_jour, commandes DESC;
