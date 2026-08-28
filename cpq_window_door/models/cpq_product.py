from odoo import models, fields, api


class CpqProduct(models.Model):
    _name = 'cpq.product'
    _description = 'Configurable CPQ Product'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    product_tmpl_id = fields.Many2one(
        'product.template', string='Odoo Product',
        required=True, ondelete='cascade',
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Internal Notes')

    # ── Pricing mode ─────────────────────────────────────────────────────────
    price_mode = fields.Selection([
        ('per_m2', 'Price per m²  (W x H x rate)'),
        ('per_lm', 'Price per linear meter  (W x rate)'),
        ('fixed',  'Fixed price  (surcharges only)'),
    ], string='Pricing Mode', required=True, default='per_m2')

    # ── Attribute mapping ────────────────────────────────────────────────────
    width_attribute_id = fields.Many2one(
        'cpq.attribute', string='Width Attribute',
        domain="[('cpq_product_id','=',id),('attribute_type','=','numeric')]",
        help="Numeric attribute used as width in the calculation.",
    )
    height_attribute_id = fields.Many2one(
        'cpq.attribute', string='Height Attribute',
        domain="[('cpq_product_id','=',id),('attribute_type','=','numeric')]",
        help="Numeric attribute used as height in the calculation.",
    )
    material_attribute_id = fields.Many2one(
        'cpq.attribute', string='Material Attribute',
        domain="[('cpq_product_id','=',id),('attribute_type','=','list')]",
        help="List attribute where each value can carry a per-m² rate.",
    )

    # ── Base rate ────────────────────────────────────────────────────────────
    price_per_m2 = fields.Float(
        'Base Rate (/m²)', digits=(10, 2), default=0.0,
        help="Used if no material attribute is designated.",
    )
    price_per_lm = fields.Float(
        'Base Rate (/m)', digits=(10, 2), default=0.0,
    )

    # ── Attributes ───────────────────────────────────────────────────────────
    attribute_ids = fields.One2many(
        'cpq.attribute', 'cpq_product_id',
        string='Attributes', copy=True,
    )

    # ── Vrais One2many (via cpq_product_id stocké sur les modèles enfants) ───
    all_value_ids = fields.One2many(
        'cpq.attribute.value', 'cpq_product_id',
        string='All Values',
        domain=[('attribute_id.attribute_type', '=', 'list')],
    )
    boolean_attribute_ids = fields.One2many(
        'cpq.attribute', 'cpq_product_id',
        string='Yes/No Options',
        domain=[('attribute_type', '=', 'boolean')],
    )

    @api.onchange('price_mode')
    def _onchange_price_mode(self):
        if self.price_mode == 'fixed':
            self.width_attribute_id = False
            self.height_attribute_id = False
            self.material_attribute_id = False
        elif self.price_mode == 'per_lm':
            self.height_attribute_id = False


    pricing_warning = fields.Char(compute='_compute_pricing_warning', store=False)

    @api.depends('price_mode', 'width_attribute_id', 'height_attribute_id',
                 'material_attribute_id', 'price_per_m2', 'price_per_lm')
    def _compute_pricing_warning(self):
        for p in self:
            msgs = []
            if p.price_mode == 'per_m2':
                if not p.width_attribute_id:
                    msgs.append("Width Attribute is required.")
                if not p.height_attribute_id:
                    msgs.append("Height Attribute is required.")
                if not p.material_attribute_id and not p.price_per_m2:
                    msgs.append("Set a Material Attribute or a Base Rate (/m2).")
            elif p.price_mode == 'per_lm':
                if not p.width_attribute_id:
                    msgs.append("Width Attribute is required.")
                if not p.material_attribute_id and not p.price_per_lm:
                    msgs.append("Set a Material Attribute or a Base Rate (/m).")
            p.pricing_warning = "  Warning: " + "  /  ".join(msgs) if msgs else False


class CpqAttribute(models.Model):
    _name = 'cpq.attribute'
    _description = 'CPQ Attribute'
    _order = 'cpq_product_id, sequence, id'

    cpq_product_id  = fields.Many2one('cpq.product', required=True, ondelete='cascade')
    name            = fields.Char(string='Name', required=True)
    sequence        = fields.Integer(default=10)
    attribute_type  = fields.Selection([
        ('list',    'Selection list'),
        ('numeric', 'Numeric'),
        ('boolean', 'Yes / No'),
    ], string='Type', required=True, default='list')
    is_required     = fields.Boolean(string='Required', default=True)

    numeric_min     = fields.Float('Min', default=1.0)
    numeric_max     = fields.Float('Max', default=9999.0)
    numeric_unit    = fields.Char('Unit', default='cm')
    numeric_default = fields.Float('Default', default=0.0)

    value_ids       = fields.One2many('cpq.attribute.value', 'attribute_id',
                                       string='Values', copy=True)
    bool_surcharge  = fields.Float('Surcharge if Yes', default=0.0)
    bool_default    = fields.Boolean('Default', default=False)


class CpqAttributeValue(models.Model):
    _name = 'cpq.attribute.value'
    _description = "CPQ Attribute Value"
    _order = 'attribute_id, sequence, id'

    attribute_id   = fields.Many2one('cpq.attribute', required=True, ondelete='cascade')
    # Clé pour le One2many direct depuis cpq.product
    cpq_product_id = fields.Many2one('cpq.product', store=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('cpq_product_id') and vals.get('attribute_id'):
                attr = self.env['cpq.attribute'].browse(vals['attribute_id'])
                vals['cpq_product_id'] = attr.cpq_product_id.id
        return super().create(vals_list)

    name           = fields.Char(string='Value', required=True)
    attribute_name = fields.Char(related='attribute_id.name', string='Attribute',
                                  store=True, readonly=True)
    sequence       = fields.Integer(default=10)
    surcharge      = fields.Float('Surcharge', default=0.0)
    price_per_m2   = fields.Float('Rate per m²', default=0.0,
                                   help="Active if the attribute is designated as material on the product.")
    is_default     = fields.Boolean('Default', default=False)

    # ── Unified display ──────────────────────────────────────────────────────
    is_material_value = fields.Boolean(compute='_compute_is_material_value', store=False)
    price_unit        = fields.Char(compute='_compute_price_unit')
    display_price     = fields.Float(compute='_compute_display_price',
                                      inverse='_set_display_price', digits=(10, 2))

    @api.depends('attribute_id.cpq_product_id.material_attribute_id')
    def _compute_is_material_value(self):
        for v in self:
            product = v.attribute_id.cpq_product_id
            v.is_material_value = bool(product.material_attribute_id
                                       and product.material_attribute_id == v.attribute_id)

    @api.depends('attribute_id.cpq_product_id.material_attribute_id',
                 'attribute_id.cpq_product_id.price_mode')
    def _compute_price_unit(self):
        currency = self.env.company.currency_id.name or 'EUR'
        for v in self:
            if v.is_material_value:
                mode = v.attribute_id.cpq_product_id.price_mode
                v.price_unit = f'{currency}/m' if mode == 'per_lm' else f'{currency}/m²'
            else:
                v.price_unit = currency

    @api.depends('price_per_m2', 'surcharge', 'attribute_id.cpq_product_id.material_attribute_id')
    def _compute_display_price(self):
        for v in self:
            v.display_price = v.price_per_m2 if v.is_material_value else v.surcharge

    def _set_display_price(self):
        for v in self:
            if v.is_material_value:
                v.price_per_m2 = v.display_price
            else:
                v.surcharge = v.display_price
