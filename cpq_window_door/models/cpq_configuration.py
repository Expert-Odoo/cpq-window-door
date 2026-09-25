from odoo import models, fields, api


class CpqConfiguration(models.Model):
    _name = 'cpq.configuration'
    _description = 'Saved CPQ Configuration'

    sale_line_id = fields.Many2one(
        'sale.order.line', string='Quotation Line',
        required=True, ondelete='cascade',
    )
    cpq_product_id = fields.Many2one(
        'cpq.product', string='CPQ Product', required=True,
    )
    value_ids = fields.One2many(
        'cpq.configuration.value', 'configuration_id',
        string='Values', copy=True,
    )
    price_unit = fields.Float('Unit Price (excl. tax)', digits=(16, 2))
    surface_m2 = fields.Float('Area (m²)', digits=(16, 4))
    summary = fields.Text('Summary', compute='_compute_summary', store=True)

    @api.depends('value_ids', 'value_ids.value_list_id',
                 'value_ids.value_numeric', 'value_ids.value_boolean',
                 'cpq_product_id.width_attribute_id',
                 'cpq_product_id.height_attribute_id',
                 'cpq_product_id.material_attribute_id')
    def _compute_summary(self):
        for config in self:
            product = config.cpq_product_id
            w_attr = product.width_attribute_id
            h_attr = product.height_attribute_id
            m_attr = product.material_attribute_id
            parts = []

            for val in config.value_ids.sorted(lambda v: v.attribute_id.sequence):
                attr = val.attribute_id
                if w_attr and attr == w_attr:
                    parts.append('L %d cm' % val.value_numeric)
                elif h_attr and attr == h_attr:
                    parts.append('H %d cm' % val.value_numeric)
                elif m_attr and attr == m_attr:
                    if val.value_list_id:
                        parts.append(val.value_list_id.name)
                elif attr.attribute_type == 'list' and val.value_list_id:
                    parts.append(val.value_list_id.name)
                elif attr.attribute_type == 'boolean' and val.value_boolean:
                    parts.append(attr.name)
                elif attr.attribute_type == 'numeric':
                    unit = attr.numeric_unit or ''
                    parts.append('%s: %d %s' % (attr.name, val.value_numeric, unit))
            config.summary = ' - '.join(parts)

    def get_pdf_breakdown(self):
        self.ensure_one()
        currency = self.env.company.currency_id.name or 'EUR'
        product = self.cpq_product_id
        w_attr = product.width_attribute_id
        h_attr = product.height_attribute_id
        m_attr = product.material_attribute_id
        price_mode = product.price_mode

        width = height = material_price = 0.0
        material_name = ''
        surcharges = []

        vals_by_attr = {v.attribute_id.id: v for v in self.value_ids}

        if w_attr:
            wv = vals_by_attr.get(w_attr.id)
            if wv:
                width = wv.value_numeric

        if h_attr:
            hv = vals_by_attr.get(h_attr.id)
            if hv:
                height = hv.value_numeric

        if m_attr:
            mv = vals_by_attr.get(m_attr.id)
            if mv and mv.value_list_id:
                material_price = mv.value_list_id.price_per_m2
                material_name = mv.value_list_id.name

        if not material_price:
            material_price = product.price_per_m2 if price_mode == 'per_m2' else product.price_per_lm
            material_name = product.name

        skip_ids = {a.id for a in [w_attr, h_attr, m_attr] if a}

        for val in self.value_ids.sorted(lambda v: v.attribute_id.sequence):
            if val.attribute_id.id in skip_ids:
                continue
            attr = val.attribute_id
            if attr.attribute_type == 'list' and val.value_list_id and val.value_list_id.surcharge:
                surcharges.append({
                    'label': '%s %s' % (attr.name, val.value_list_id.name),
                    'amount': val.value_list_id.surcharge,
                })
            elif attr.attribute_type == 'boolean' and val.value_boolean and attr.bool_surcharge:
                surcharges.append({'label': attr.name, 'amount': attr.bool_surcharge})

        lines = []
        if price_mode == 'per_m2':
            surface = (width / 100.0) * (height / 100.0)
            base = surface * material_price
            lines.append({'label': 'Dimensions: %d x %d cm  —  Area: %.4f m²' % (width, height, surface), 'amount': False})
            lines.append({'label': '%s: %.4f m² × %.2f %s/m²' % (material_name, surface, material_price, currency), 'amount': base})
        elif price_mode == 'per_lm':
            base = (width / 100.0) * material_price
            lines.append({'label': 'Length: %d cm' % width, 'amount': False})
            lines.append({'label': '%s: %.2f m × %.2f %s/m' % (material_name, width / 100.0, material_price, currency), 'amount': base})
        else:
            base = 0.0

        for s in surcharges:
            lines.append({'label': s['label'], 'amount': s['amount']})

        return lines


class CpqConfigurationValue(models.Model):
    _name = 'cpq.configuration.value'
    _description = 'CPQ Configuration Value'
    _order = 'configuration_id, attribute_id'

    configuration_id = fields.Many2one(
        'cpq.configuration', required=True, ondelete='cascade',
    )
    attribute_id = fields.Many2one(
        'cpq.attribute', required=True, ondelete='cascade',
    )
    attribute_type = fields.Selection(related='attribute_id.attribute_type', store=True)
    value_list_id = fields.Many2one('cpq.attribute.value', string='Value (list)')
    value_numeric = fields.Float('Value (numeric)')
    value_boolean = fields.Boolean('Value (yes/no)')
