from odoo import models, fields, api
from odoo.exceptions import UserError


class CpqConfiguratorWizard(models.TransientModel):
    _name = 'cpq.configurator.wizard'
    _description = 'CPQ Configurator'

    sale_line_id    = fields.Many2one('sale.order.line', required=True, ondelete='cascade')
    cpq_product_id  = fields.Many2one('cpq.product', required=True)
    line_ids        = fields.One2many('cpq.configurator.wizard.line', 'wizard_id')
    price_total     = fields.Float('Total Price (excl. tax)', digits=(16, 2), readonly=True)
    surface_m2      = fields.Float('Area (m²)', digits=(16, 4), readonly=True)
    price_breakdown = fields.Text('Price breakdown', readonly=True)

    def _init_lines(self):
        self.ensure_one()
        if self.line_ids:
            self.line_ids.unlink()
        existing = self.sale_line_id.cpq_configuration_id
        lines = []
        if existing:
            for cval in existing.value_ids.sorted(lambda v: v.attribute_id.sequence):
                lines.append((0, 0, {
                    'attribute_id':  cval.attribute_id.id,
                    'value_list_id': cval.value_list_id.id if cval.value_list_id else False,
                    'value_numeric': cval.value_numeric,
                    'value_boolean': cval.value_boolean,
                }))
        else:
            for attr in self.cpq_product_id.attribute_ids.sorted('sequence'):
                default_list = attr.value_ids.filtered('is_default')[:1]
                lines.append((0, 0, {
                    'attribute_id':  attr.id,
                    'value_list_id': default_list.id if attr.attribute_type == 'list' and default_list else False,
                    'value_numeric': attr.numeric_default if attr.attribute_type == 'numeric' else 0.0,
                    'value_boolean': attr.bool_default    if attr.attribute_type == 'boolean' else False,
                }))
        if lines:
            self.write({'line_ids': lines})
        self._recompute_price()

    @api.onchange('line_ids')
    def _onchange_lines(self):
        self._recompute_price()

    def _recompute_price(self):
        self.ensure_one()
        currency   = self.env.company.currency_id.name or 'EUR'
        product    = self.cpq_product_id
        price_mode = product.price_mode
        vals_by_attr = {wl.attribute_id.id: wl for wl in self.line_ids}

        width = height = material_price = 0.0
        material_name = ''
        surcharges = []

        # Dimensions
        if price_mode in ('per_m2', 'per_lm') and product.width_attribute_id:
            wl = vals_by_attr.get(product.width_attribute_id.id)
            if wl:
                width = wl.value_numeric

        if price_mode == 'per_m2' and product.height_attribute_id:
            wl = vals_by_attr.get(product.height_attribute_id.id)
            if wl:
                height = wl.value_numeric

        # Tarif materiau (per_m2 ET per_lm)
        if price_mode in ('per_m2', 'per_lm') and product.material_attribute_id:
            wl = vals_by_attr.get(product.material_attribute_id.id)
            if wl and wl.value_list_id:
                material_price = wl.value_list_id.price_per_m2
                material_name  = wl.value_list_id.name

        # Tarif de base si pas de materiau
        if not material_price:
            if price_mode == 'per_m2':
                material_price = product.price_per_m2
            elif price_mode == 'per_lm':
                material_price = product.price_per_lm
            material_name = product.name

        # Surcouts (exclure les attributs de calcul)
        skip_ids = {
            product.width_attribute_id.id    if product.width_attribute_id    else None,
            product.height_attribute_id.id   if product.height_attribute_id   else None,
            product.material_attribute_id.id if product.material_attribute_id else None,
        }
        skip_ids.discard(None)

        for wl in self.line_ids.sorted(lambda l: l.attribute_id.sequence):
            if wl.attribute_id.id in skip_ids:
                continue
            attr = wl.attribute_id
            if attr.attribute_type == 'list' and wl.value_list_id and wl.value_list_id.surcharge:
                surcharges.append((attr.name, wl.value_list_id.name, wl.value_list_id.surcharge))
            elif attr.attribute_type == 'boolean' and wl.value_boolean and attr.bool_surcharge:
                surcharges.append((attr.name, '', attr.bool_surcharge))

        # Calcul
        if price_mode == 'per_m2':
            surface = (width / 100.0) * (height / 100.0)
            base    = surface * material_price
        elif price_mode == 'per_lm':
            surface = 0.0
            base    = (width / 100.0) * material_price
        else:
            surface = base = 0.0

        total = base + sum(s[2] for s in surcharges)
        self.surface_m2  = surface
        self.price_total = total

        # Detail
        w_label = product.width_attribute_id.name  if product.width_attribute_id  else 'L'
        h_label = product.height_attribute_id.name if product.height_attribute_id else 'H'
        bd = []
        if price_mode == 'per_m2':
            bd += [
                '%s: %.0f  %s: %.0f' % (w_label, width, h_label, height),
                'Area: %.4f m²' % surface,
                '%s @ %.2f %s/m²  →  %.2f %s' % (material_name, material_price, currency, base, currency),
                '-' * 38,
            ]
        elif price_mode == 'per_lm':
            bd += [
                '%s: %.0f cm  (%.2f m)' % (w_label, width, width / 100.0),
                '%s @ %.2f %s/m  →  %.2f %s' % (material_name, material_price, currency, base, currency),
                '-' * 38,
            ]
        else:
            bd += ['Fixed price', '-' * 38]

        for name, val, amt in surcharges:
            label = ('%s %s' % (name, val)).strip()
            bd.append('%-30s +%.2f %s' % (label, amt, currency))
        bd += ['-' * 38, 'TOTAL (excl. tax)               %.2f %s' % (total, currency)]
        self.price_breakdown = '\n'.join(bd)

    # ── Validation ───────────────────────────────────────────────────────

    def _get_lines_to_validate(self):
        return self.line_ids

    def _validate_configuration(self):
        errors = []
        for wl in self._get_lines_to_validate():
            attr = wl.attribute_id
            if not attr.is_required:
                continue
            if attr.attribute_type == 'list' and not wl.value_list_id:
                errors.append("'%s' is required." % attr.name)
            elif attr.attribute_type == 'numeric':
                val = wl.value_numeric
                unit = (' ' + attr.numeric_unit) if attr.numeric_unit else ''
                if attr.numeric_min and val < attr.numeric_min:
                    errors.append("'%s': minimum value %.0f%s." % (attr.name, attr.numeric_min, unit))
                elif attr.numeric_max and val > attr.numeric_max:
                    errors.append("'%s': maximum value %.0f%s." % (attr.name, attr.numeric_max, unit))
        if errors:
            raise UserError('\n'.join(errors))

    def action_confirm(self):
        self.ensure_one()
        self._recompute_price()
        self._validate_configuration()
        line = self.sale_line_id
        if line.cpq_configuration_id:
            line.cpq_configuration_id.unlink()
        config = self.env['cpq.configuration'].create({
            'sale_line_id':   line.id,
            'cpq_product_id': self.cpq_product_id.id,
            'price_unit':     self.price_total,
            'surface_m2':     self.surface_m2,
        })
        for wl in self.line_ids:
            self.env['cpq.configuration.value'].create({
                'configuration_id': config.id,
                'attribute_id':     wl.attribute_id.id,
                'value_list_id':    wl.value_list_id.id if wl.value_list_id else False,
                'value_numeric':    wl.value_numeric,
                'value_boolean':    wl.value_boolean,
            })
        line.write({
            'cpq_configuration_id': config.id,
            'price_unit':           self.price_total,
            'name':                 (line.name or '').split('\n')[0].strip() +
                                    ('\n' + config.summary if config.summary else ''),
        })
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}


class CpqConfiguratorWizardLine(models.TransientModel):
    _name = 'cpq.configurator.wizard.line'
    _description = 'CPQ Configurator Line'
    _order = 'wizard_id, sequence'

    wizard_id       = fields.Many2one('cpq.configurator.wizard', required=True, ondelete='cascade')
    sequence        = fields.Integer(related='attribute_id.sequence', store=True)
    attribute_id    = fields.Many2one('cpq.attribute', required=True, ondelete='cascade')
    attribute_type  = fields.Selection(related='attribute_id.attribute_type', store=True)
    attribute_label = fields.Char(compute='_compute_attribute_label')

    @api.depends('attribute_id.name', 'attribute_id.numeric_unit', 'attribute_id.attribute_type')
    def _compute_attribute_label(self):
        for line in self:
            attr = line.attribute_id
            if attr.attribute_type == 'numeric' and attr.numeric_unit:
                line.attribute_label = '%s (%s)' % (attr.name, attr.numeric_unit)
            else:
                line.attribute_label = attr.name or ''

    numeric_min   = fields.Float(related='attribute_id.numeric_min')
    numeric_max   = fields.Float(related='attribute_id.numeric_max')
    numeric_unit  = fields.Char(related='attribute_id.numeric_unit')
    value_list_id = fields.Many2one('cpq.attribute.value',
                                     domain='[("attribute_id","=",attribute_id)]')
    value_numeric = fields.Float(digits=(10, 1))
    value_boolean = fields.Boolean()

    @api.onchange('value_list_id', 'value_numeric', 'value_boolean')
    def _onchange_value(self):
        if self.wizard_id:
            self.wizard_id._recompute_price()
