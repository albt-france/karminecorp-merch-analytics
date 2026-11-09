-- Page 4 · Comment se remplit un événement ?
-- Par événement : remplissage, part vendue le premier jour, délai avant complet, liste d'attente.
WITH v AS (
    SELECT b.event_id,
           SUM(b.billets) AS billets,
           SUM(b.ca_ttc) AS ca_ttc,
           SUM(b.billets) FILTER (WHERE b.date_vente = e.date_ouverture_ventes) AS billets_j0,
           SUM(b.billets) FILTER (WHERE b.date_vente <= e.date_ouverture_ventes + INTERVAL 1 DAY) AS billets_48h
    FROM billets b JOIN evenements e USING (event_id)
    GROUP BY b.event_id
),
w AS (SELECT event_id, SUM(inscrits_liste_attente) AS liste_attente FROM liste_attente GROUP BY event_id)
SELECT e.event_id, e.nom, e.date_evenement, e.lieu, e.capacite,
       v.billets, ROUND(v.billets / e.capacite, 3) AS taux_remplissage,
       ROUND(v.billets_j0 / e.capacite, 3) AS part_capacite_vendue_j0,
       ROUND(v.billets_48h / e.capacite, 3) AS part_capacite_vendue_48h,
       DATE_DIFF('day', e.date_ouverture_ventes, e.date_complet) AS jours_avant_complet,
       COALESCE(w.liste_attente, 0) AS liste_attente,
       ROUND(v.ca_ttc) AS ca_ttc,
       e.reporte_rembourse, e.info_reelle
FROM evenements e
JOIN v USING (event_id)
LEFT JOIN w USING (event_id)
ORDER BY e.date_evenement;
