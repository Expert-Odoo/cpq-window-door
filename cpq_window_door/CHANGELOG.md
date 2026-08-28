# Changelog — CPQ Menuiserie & Aluminium

## [1.0.0] — 2026-05-23

Première version publiable du module CPQ Menuiserie pour Odoo 19.

### Fonctionnalités
- **Wizard configurateur** : dimensions (L×H cm), matériau, options liste, booléens
- **Calcul prix au m²** en temps réel avec surcoûts par option
- **Smart button** sur le devis : compteur lignes CPQ + lignes non configurées
- **Sélecteur multi-lignes** : popup de choix si plusieurs produits CPQ sur le même devis
- **Rapport PDF enrichi** : détail de configuration injecté sous chaque ligne CPQ
- **Fiche produit CPQ** : onglet Attributs (structure) + onglet Tarifs & Valeurs (prix éditables)
- **4 produits de démo** représentatifs du métier menuisier aluminium :
  - Fenêtre oscillo-battante (9 attributs, 21 valeurs, 320 €/m² alu)
  - Porte-fenêtre 2 vantaux (9 attributs, 17 valeurs, 320 €/m² alu)
  - Baie vitrée coulissante (9 attributs, 15 valeurs, 380 €/m² alu)
  - Porte d'entrée (12 attributs, 29 valeurs, 420 €/m² alu)

### Technique
- Odoo 19.0 (testé sur 19.0-20260324)
- Dépendance : `sale_management` uniquement
- Licence : LGPL-3
- Branche git : `19.0_fouad_20260522`

### Scénario de démo (5 min)
1. Ouvrir un devis → ajouter "Fenêtre oscillo-battante aluminium"
2. Cliquer le smart button "1 Produit(s) CPQ"
3. Modifier Largeur → 140 cm, Hauteur → 120 cm, Matériau → Aluminium,
   Couleur → Anthracite RAL 7016, Vitrage → Double Argon, Pose incluse → Oui
4. Valider → prix = 807,60 € HT
5. Imprimer → PDF avec détail de configuration

### Roadmap v1.1 (Add-ons payants)
- Add-on 1 : Logique conditionnelle (masquer options selon matériau)
- Add-on 2 : Formules de prix avancées (remises, majorations)
- Add-on 3 : BOM fabrication (génération nomenclature depuis la config)
