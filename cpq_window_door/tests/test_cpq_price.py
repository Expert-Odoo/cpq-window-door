from odoo.tests import TransactionCase
from odoo.exceptions import UserError


class TestCpqPrice(TransactionCase):
    """Tests de calcul de prix et validation du module cpq_window_door."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Produits Odoo
        cls.tmpl_m2 = cls.env['product.template'].create({
            'name': 'Test Fenetre CPQ', 'type': 'consu', 'sale_ok': True,
        })
        cls.tmpl_lm = cls.env['product.template'].create({
            'name': 'Test Barre CPQ', 'type': 'consu', 'sale_ok': True,
        })
        cls.tmpl_fixed = cls.env['product.template'].create({
            'name': 'Test Volet CPQ', 'type': 'consu', 'sale_ok': True,
        })

        # Produits CPQ
        cls.cpq_m2 = cls.env['cpq.product'].create({
            'name': 'Fenetre Test', 'product_tmpl_id': cls.tmpl_m2.id,
            'price_mode': 'fixed',
        })
        cls.cpq_lm = cls.env['cpq.product'].create({
            'name': 'Barre Test', 'product_tmpl_id': cls.tmpl_lm.id,
            'price_mode': 'per_lm', 'price_per_lm': 50.0,
        })
        cls.cpq_fixed = cls.env['cpq.product'].create({
            'name': 'Volet Test', 'product_tmpl_id': cls.tmpl_fixed.id,
            'price_mode': 'fixed',
        })

        # Attributs per_m2
        cls.attr_larg = cls.env['cpq.attribute'].create({
            'cpq_product_id': cls.cpq_m2.id, 'name': 'Largeur',
            'attribute_type': 'numeric', 'sequence': 10,
            'numeric_min': 40.0, 'numeric_max': 300.0,
            'numeric_default': 120.0, 'numeric_unit': 'cm', 'is_required': True,
        })
        cls.attr_haut = cls.env['cpq.attribute'].create({
            'cpq_product_id': cls.cpq_m2.id, 'name': 'Hauteur',
            'attribute_type': 'numeric', 'sequence': 20,
            'numeric_min': 40.0, 'numeric_max': 280.0,
            'numeric_default': 90.0, 'numeric_unit': 'cm', 'is_required': True,
        })
        cls.attr_mat = cls.env['cpq.attribute'].create({
            'cpq_product_id': cls.cpq_m2.id, 'name': 'Materiau',
            'attribute_type': 'list', 'sequence': 30, 'is_required': True,
        })
        cls.val_pvc = cls.env['cpq.attribute.value'].create({
            'attribute_id': cls.attr_mat.id, 'name': 'PVC',
            'price_per_m2': 180.0, 'sequence': 10,
        })
        cls.val_alu = cls.env['cpq.attribute.value'].create({
            'attribute_id': cls.attr_mat.id, 'name': 'Aluminium',
            'price_per_m2': 320.0, 'is_default': True, 'sequence': 20,
        })
        cls.attr_couleur = cls.env['cpq.attribute'].create({
            'cpq_product_id': cls.cpq_m2.id, 'name': 'Couleur',
            'attribute_type': 'list', 'sequence': 40, 'is_required': True,
        })
        cls.val_blanc = cls.env['cpq.attribute.value'].create({
            'attribute_id': cls.attr_couleur.id, 'name': 'Blanc',
            'surcharge': 0.0, 'is_default': True, 'sequence': 10,
        })
        cls.val_anthracite = cls.env['cpq.attribute.value'].create({
            'attribute_id': cls.attr_couleur.id, 'name': 'Anthracite',
            'surcharge': 40.0, 'sequence': 20,
        })
        cls.cpq_m2.write({
            'price_mode': 'per_m2',
            'price_per_m2': 300.0,
            'width_attribute_id':    cls.attr_larg.id,
            'height_attribute_id':   cls.attr_haut.id,
            'material_attribute_id': cls.attr_mat.id,
        })

        # Attributs per_lm
        cls.attr_longueur = cls.env['cpq.attribute'].create({
            'cpq_product_id': cls.cpq_lm.id, 'name': 'Longueur',
            'attribute_type': 'numeric', 'sequence': 10,
            'numeric_min': 50.0, 'numeric_max': 600.0,
            'numeric_default': 200.0, 'numeric_unit': 'cm', 'is_required': True,
        })
        cls.attr_profil = cls.env['cpq.attribute'].create({
            'cpq_product_id': cls.cpq_lm.id, 'name': 'Profil',
            'attribute_type': 'list', 'sequence': 20, 'is_required': True,
        })
        cls.val_profil_alu = cls.env['cpq.attribute.value'].create({
            'attribute_id': cls.attr_profil.id, 'name': 'Alu 60mm',
            'price_per_m2': 60.0, 'is_default': True, 'sequence': 10,
        })
        cls.val_profil_pvc = cls.env['cpq.attribute.value'].create({
            'attribute_id': cls.attr_profil.id, 'name': 'PVC 70mm',
            'price_per_m2': 35.0, 'sequence': 20,
        })
        cls.cpq_lm.write({
            'width_attribute_id':    cls.attr_longueur.id,
            'material_attribute_id': cls.attr_profil.id,
        })

        # Attributs fixed
        cls.attr_pose = cls.env['cpq.attribute'].create({
            'cpq_product_id': cls.cpq_fixed.id, 'name': 'Pose incluse',
            'attribute_type': 'boolean', 'sequence': 10,
            'bool_surcharge': 150.0, 'bool_default': False, 'is_required': False,
        })

        # Sale order
        cls.partner = cls.env['res.partner'].create({'name': 'Test CPQ Partner'})
        cls.order = cls.env['sale.order'].create({'partner_id': cls.partner.id})

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _make_line(self, tmpl):
        product = tmpl.product_variant_ids[0]
        return self.env['sale.order.line'].create({
            'order_id': self.order.id,
            'product_id': product.id,
            'name': product.name,
            'product_uom_qty': 1,
            'price_unit': 0,
        })

    def _make_wizard(self, cpq_product, sale_line):
        wiz = self.env['cpq.configurator.wizard'].create({
            'sale_line_id': sale_line.id,
            'cpq_product_id': cpq_product.id,
        })
        wiz._init_lines()
        return wiz

    def _set_numeric(self, wiz, attr, value):
        line = wiz.line_ids.filtered(lambda l: l.attribute_id == attr)
        line.value_numeric = value
        wiz._recompute_price()

    def _set_list(self, wiz, attr, value):
        line = wiz.line_ids.filtered(lambda l: l.attribute_id == attr)
        line.value_list_id = value
        wiz._recompute_price()

    # ── Tests per_m2 ─────────────────────────────────────────────────────────

    def test_per_m2_tarif_de_base(self):
        """Sans attribut materiau : utilise price_per_m2 du produit CPQ."""
        tmpl = self.env['product.template'].create({'name': 'Test Base', 'type': 'consu'})
        cpq = self.env['cpq.product'].create({
            'name': 'Base', 'product_tmpl_id': tmpl.id,
            'price_mode': 'per_m2', 'price_per_m2': 300.0,
        })
        al = self.env['cpq.attribute'].create({
            'cpq_product_id': cpq.id, 'name': 'L', 'attribute_type': 'numeric',
            'numeric_default': 120.0, 'sequence': 10,
        })
        ah = self.env['cpq.attribute'].create({
            'cpq_product_id': cpq.id, 'name': 'H', 'attribute_type': 'numeric',
            'numeric_default': 90.0, 'sequence': 20,
        })
        cpq.write({'width_attribute_id': al.id, 'height_attribute_id': ah.id})
        wiz = self._make_wizard(cpq, self._make_line(tmpl))
        # 1.20 * 0.90 * 300 = 324.0
        self.assertAlmostEqual(wiz.price_total, 324.0, places=2)
        self.assertAlmostEqual(wiz.surface_m2, 1.08, places=4)

    def test_per_m2_avec_materiau(self):
        """Materiau par defaut Alu 320 EUR/m2 : 1.20 * 0.90 * 320 = 345.6."""
        wiz = self._make_wizard(self.cpq_m2, self._make_line(self.tmpl_m2))
        self.assertAlmostEqual(wiz.price_total, 345.6, places=2)

    def test_per_m2_changement_materiau(self):
        """Passer de Alu a PVC : 1.20 * 0.90 * 180 = 194.4."""
        wiz = self._make_wizard(self.cpq_m2, self._make_line(self.tmpl_m2))
        self._set_list(wiz, self.attr_mat, self.val_pvc)
        self.assertAlmostEqual(wiz.price_total, 194.4, places=2)

    def test_per_m2_avec_surcout(self):
        """Alu 320 + Anthracite +40 : 345.6 + 40 = 385.6."""
        wiz = self._make_wizard(self.cpq_m2, self._make_line(self.tmpl_m2))
        self._set_list(wiz, self.attr_couleur, self.val_anthracite)
        self.assertAlmostEqual(wiz.price_total, 385.6, places=2)

    def test_per_m2_changement_dimensions(self):
        """150 x 100 cm, Alu 320 : 1.50 * 1.00 * 320 = 480."""
        wiz = self._make_wizard(self.cpq_m2, self._make_line(self.tmpl_m2))
        self._set_numeric(wiz, self.attr_larg, 150.0)
        self._set_numeric(wiz, self.attr_haut, 100.0)
        self.assertAlmostEqual(wiz.price_total, 480.0, places=2)

    # ── Tests per_lm ─────────────────────────────────────────────────────────

    def test_per_lm_tarif_de_base(self):
        """Sans materiau : price_per_lm du produit. 200 cm * 50 EUR/m = 100."""
        tmpl = self.env['product.template'].create({'name': 'Test LM Base', 'type': 'consu'})
        cpq = self.env['cpq.product'].create({
            'name': 'LM Base', 'product_tmpl_id': tmpl.id,
            'price_mode': 'per_lm', 'price_per_lm': 50.0,
        })
        al = self.env['cpq.attribute'].create({
            'cpq_product_id': cpq.id, 'name': 'Longueur',
            'attribute_type': 'numeric', 'numeric_default': 200.0, 'sequence': 10,
        })
        cpq.write({'width_attribute_id': al.id})
        wiz = self._make_wizard(cpq, self._make_line(tmpl))
        self.assertAlmostEqual(wiz.price_total, 100.0, places=2)

    def test_per_lm_avec_materiau(self):
        """Profil Alu 60 EUR/m par defaut : 200 cm * 60 EUR/m = 120."""
        wiz = self._make_wizard(self.cpq_lm, self._make_line(self.tmpl_lm))
        self.assertAlmostEqual(wiz.price_total, 120.0, places=2)

    def test_per_lm_changement_materiau(self):
        """PVC 35 EUR/m : 200 cm * 35 EUR/m = 70."""
        wiz = self._make_wizard(self.cpq_lm, self._make_line(self.tmpl_lm))
        self._set_list(wiz, self.attr_profil, self.val_profil_pvc)
        self.assertAlmostEqual(wiz.price_total, 70.0, places=2)

    def test_per_lm_longueur_differente(self):
        """350 cm, Alu 60 EUR/m : 3.50 * 60 = 210."""
        wiz = self._make_wizard(self.cpq_lm, self._make_line(self.tmpl_lm))
        self._set_numeric(wiz, self.attr_longueur, 350.0)
        self.assertAlmostEqual(wiz.price_total, 210.0, places=2)

    # ── Tests fixed ───────────────────────────────────────────────────────────

    def test_fixed_sans_option(self):
        """Mode fixe, aucune option cochee : prix 0."""
        wiz = self._make_wizard(self.cpq_fixed, self._make_line(self.tmpl_fixed))
        self.assertAlmostEqual(wiz.price_total, 0.0, places=2)

    def test_fixed_avec_booleen(self):
        """Pose incluse cochee : +150 EUR."""
        wiz = self._make_wizard(self.cpq_fixed, self._make_line(self.tmpl_fixed))
        pose_line = wiz.line_ids.filtered(lambda l: l.attribute_id == self.attr_pose)
        pose_line.value_boolean = True
        wiz._recompute_price()
        self.assertAlmostEqual(wiz.price_total, 150.0, places=2)

    # ── Tests validation ──────────────────────────────────────────────────────

    def test_validation_liste_required_vide(self):
        """Champ liste required non renseigne leve UserError."""
        wiz = self._make_wizard(self.cpq_m2, self._make_line(self.tmpl_m2))
        mat_line = wiz.line_ids.filtered(lambda l: l.attribute_id == self.attr_mat)
        mat_line.value_list_id = False
        with self.assertRaises(UserError):
            wiz.action_confirm()

    def test_validation_numerique_sous_minimum(self):
        """Largeur < 40 cm (min) leve UserError."""
        wiz = self._make_wizard(self.cpq_m2, self._make_line(self.tmpl_m2))
        self._set_numeric(wiz, self.attr_larg, 10.0)
        with self.assertRaises(UserError):
            wiz.action_confirm()

    def test_validation_numerique_dessus_maximum(self):
        """Largeur > 300 cm (max) leve UserError."""
        wiz = self._make_wizard(self.cpq_m2, self._make_line(self.tmpl_m2))
        self._set_numeric(wiz, self.attr_larg, 500.0)
        with self.assertRaises(UserError):
            wiz.action_confirm()

    def test_confirm_propage_prix_sur_ligne(self):
        """action_confirm ecrit price_unit sur la sale.order.line."""
        line = self._make_line(self.tmpl_m2)
        wiz = self._make_wizard(self.cpq_m2, line)
        wiz.action_confirm()
        # 1.20 * 0.90 * 320 = 345.6
        self.assertAlmostEqual(line.price_unit, 345.6, places=2)
        self.assertTrue(line.cpq_configuration_id)
    # ── Tests all_value_ids (bug corrigé : Add a line depuis Rates & Values) ──

    def test_all_value_ids_cpq_product_id_auto_rempli(self):
        """Valeur créée via all_value_ids : cpq_product_id doit être rempli auto."""
        val = self.env['cpq.attribute.value'].create({
            'attribute_id': self.attr_couleur.id,
            'name': 'Gris',
            'surcharge': 60.0,
        })
        self.assertEqual(val.cpq_product_id, self.cpq_m2,
            "cpq_product_id doit être rempli automatiquement via create()")

    def test_all_value_ids_ne_contient_que_list(self):
        """all_value_ids ne contient que les valeurs d'attributs de type list."""
        all_vals = self.cpq_m2.all_value_ids
        for val in all_vals:
            self.assertEqual(val.attribute_id.attribute_type, 'list',
                f"La valeur '{val.name}' appartient à un attribut non-list : {val.attribute_id.attribute_type}")

    def test_all_value_ids_exclut_numerique(self):
        """Les attributs numériques n'apparaissent pas dans all_value_ids."""
        all_attrs = self.cpq_m2.all_value_ids.mapped('attribute_id')
        self.assertNotIn(self.attr_larg, all_attrs,
            "L'attribut numérique 'Largeur' ne doit pas apparaître dans all_value_ids")
        self.assertNotIn(self.attr_haut, all_attrs,
            "L'attribut numérique 'Hauteur' ne doit pas apparaître dans all_value_ids")

    def test_boolean_attribute_ids_ne_contient_que_boolean(self):
        """boolean_attribute_ids ne contient que les attributs de type boolean."""
        for attr in self.cpq_fixed.boolean_attribute_ids:
            self.assertEqual(attr.attribute_type, 'boolean',
                f"L'attribut '{attr.name}' n'est pas de type boolean")

    def test_configurateur_sans_demo_data(self):
        """Un produit CPQ créé from scratch (sans demo) doit être configurable."""
        tmpl = self.env['product.template'].create({
            'name': 'Produit Test Sans Demo', 'type': 'consu', 'sale_ok': True,
        })
        cpq = self.env['cpq.product'].create({
            'name': 'Test Sans Demo',
            'product_tmpl_id': tmpl.id,
            'price_mode': 'per_m2',
            'price_per_m2': 200.0,
        })
        attr_l = self.env['cpq.attribute'].create({
            'cpq_product_id': cpq.id, 'name': 'Largeur',
            'attribute_type': 'numeric', 'numeric_default': 100.0, 'sequence': 10,
        })
        attr_h = self.env['cpq.attribute'].create({
            'cpq_product_id': cpq.id, 'name': 'Hauteur',
            'attribute_type': 'numeric', 'numeric_default': 100.0, 'sequence': 20,
        })
        attr_v = self.env['cpq.attribute'].create({
            'cpq_product_id': cpq.id, 'name': 'Vitrage',
            'attribute_type': 'list', 'sequence': 30, 'is_required': True,
        })
        # Créer une valeur via all_value_ids (comme depuis l'UI Rates & Values)
        val = self.env['cpq.attribute.value'].create({
            'attribute_id': attr_v.id,
            'name': 'Double vitrage',
            'surcharge': 40.0,
            'cpq_product_id': cpq.id,
        })
        cpq.write({
            'width_attribute_id': attr_l.id,
            'height_attribute_id': attr_h.id,
        })
        # Configurer et vérifier le prix : 1.0 * 1.0 * 200 + 40 = 240
        line = self._make_line(tmpl)
        wiz = self._make_wizard(cpq, line)
        v_line = wiz.line_ids.filtered(lambda l: l.attribute_id == attr_v)
        v_line.value_list_id = val
        wiz._recompute_price()
        self.assertAlmostEqual(wiz.price_total, 240.0, places=2)
    # ── Tests validation config pricing ───────────────────────────────────────

    # __ Tests pricing_warning ________________________________________________

    def test_pricing_warning_per_m2_sans_width(self):
        tmpl = self.env['product.template'].create({'name': 'Tw1', 'type': 'consu'})
        cpq = self.env['cpq.product'].create({
            'name': 'Warn m2', 'product_tmpl_id': tmpl.id, 'price_mode': 'per_m2',
        })
        self.assertTrue(cpq.pricing_warning)
        self.assertIn('Width', cpq.pricing_warning)

    def test_pricing_warning_per_m2_complet_vide(self):
        self.assertFalse(self.cpq_m2.pricing_warning)

    def test_pricing_warning_fixed_vide(self):
        self.assertFalse(self.cpq_fixed.pricing_warning)

    def test_pricing_warning_per_lm_sans_width(self):
        tmpl = self.env['product.template'].create({'name': 'Tw4', 'type': 'consu'})
        cpq = self.env['cpq.product'].create({
            'name': 'Warn lm', 'product_tmpl_id': tmpl.id,
            'price_mode': 'per_lm', 'price_per_lm': 50.0,
        })
        self.assertTrue(cpq.pricing_warning)
        self.assertIn('Width', cpq.pricing_warning)
