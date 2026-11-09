-- Page 2 · La courbe de tailles commandée suit-elle la demande ?
-- Textile et maillots produits à l'avance (hors précommande).
-- RÉEL : part des variantes épuisées par taille dans le dernier relevé de la boutique.
-- SIMULÉ : production, ventes, ventes perdues (« vérité » du simulateur, inobservable en vrai)
--          et alertes « retour en stock » (le signal qu'on observerait vraiment).
WITH dernier AS (SELECT MAX(snapshot_date) AS d FROM releves_boutique),
reel AS (
    SELECT size AS taille, ROUND(AVG(1 - available), 3) AS part_variantes_epuisees_reel
    FROM releves_boutique, dernier
    WHERE snapshot_date = dernier.d AND size IS NOT NULL AND size <> ''
    GROUP BY size
),
al AS (SELECT variant_id, SUM(alertes) AS alertes FROM alertes GROUP BY variant_id),
sim AS (
    SELECT s.taille,
           SUM(s.stock_initial) AS production,
           SUM(s.unites_vendues) AS vendues,
           SUM(s.demande_non_servie_verite) AS ventes_perdues_verite,
           SUM(COALESCE(al.alertes, 0)) AS alertes_retour_stock
    FROM stock s
    JOIN produits p USING (product_id)
    LEFT JOIN al USING (variant_id)
    WHERE s.fabrique_a_la_commande = 0 AND p.famille IN ('maillot', 'textile') AND s.taille <> 'TU'
    GROUP BY s.taille
)
SELECT sim.taille,
       sim.production, sim.vendues, sim.ventes_perdues_verite, sim.alertes_retour_stock,
       ROUND(sim.vendues / sim.production, 3) AS taux_ecoulement,
       ROUND(sim.production / SUM(sim.production) OVER (), 3) AS part_production,
       ROUND((sim.vendues + sim.ventes_perdues_verite)
             / SUM(sim.vendues + sim.ventes_perdues_verite) OVER (), 3) AS part_demande,
       reel.part_variantes_epuisees_reel
FROM sim
LEFT JOIN reel USING (taille)
ORDER BY CASE sim.taille WHEN 'XS' THEN 1 WHEN 'S' THEN 2 WHEN 'M' THEN 3 WHEN 'L' THEN 4
                         WHEN 'XL' THEN 5 WHEN 'XXL' THEN 6 WHEN '3XL' THEN 7 ELSE 8 END;
