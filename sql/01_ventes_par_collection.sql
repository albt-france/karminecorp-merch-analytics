-- Page 2 · Quels drops vendent, et à quel prix ?
-- Par collection : ventes, marge, part vendue au prix plein, démarrage (J0-J3) et taux d'écoulement.
WITH l AS (
    SELECT li.*, c.date_commande, p.collection, p.date_lancement,
           DATE_DIFF('day', p.date_lancement, c.date_commande) AS jour
    FROM lignes li
    JOIN commandes c USING (order_id)
    JOIN produits p USING (product_id)
    WHERE p.famille <> 'service'
),
st AS (
    SELECT p.collection,
           SUM(s.stock_initial) AS stock_initial,
           SUM(CASE WHEN s.fabrique_a_la_commande = 0 THEN s.unites_vendues END) AS vendues_sur_stock,
           SUM(s.stock_final) AS stock_final,
           SUM(s.stock_final * p.cout_unitaire_ht) AS valeur_stock_final_ht
    FROM stock s JOIN produits p USING (product_id)
    GROUP BY p.collection
)
SELECT l.collection,
       MIN(l.date_lancement) AS premier_lancement,
       SUM(l.quantite) AS unites,
       ROUND(SUM(l.montant_ht)) AS ca_ht,
       ROUND(SUM(l.marge_ht)) AS marge_ht,
       ROUND(SUM(l.marge_ht) / SUM(l.montant_ht), 3) AS taux_marge,
       ROUND(SUM(l.quantite) FILTER (WHERE l.remise_pct = 0) / SUM(l.quantite), 3) AS part_unites_prix_plein,
       ROUND(SUM(l.quantite * l.prix_plein_ttc * l.remise_pct) / SUM(l.quantite * l.prix_plein_ttc), 3) AS remise_moyenne,
       -- démarrage : part des 4 premières semaines vendue sur J0-J3 (lancements observés en entier)
       ROUND(SUM(l.quantite) FILTER (WHERE l.jour BETWEEN 0 AND 3)
             / NULLIF(SUM(l.quantite) FILTER (WHERE l.jour BETWEEN 0 AND 27), 0), 3) AS part_j0_j3_sur_4_semaines,
       ROUND(st.vendues_sur_stock / NULLIF(st.stock_initial, 0), 3) AS taux_ecoulement,
       st.stock_final,
       ROUND(st.valeur_stock_final_ht) AS valeur_stock_final_ht
FROM l
LEFT JOIN st USING (collection)
GROUP BY l.collection, st.stock_initial, st.vendues_sur_stock, st.stock_final, st.valeur_stock_final_ht
ORDER BY ca_ht DESC;
