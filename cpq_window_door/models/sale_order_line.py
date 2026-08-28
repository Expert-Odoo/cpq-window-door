from odoo import models, fields, api
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    cpq_product_id = fields.Many2one(
        'cpq.product', string='CPQ Product',
        compute='_compute_cpq_product_id', store=True,
    )
    cpq_configuration_id = fields.Many2one(
        'cpq.configuration', string='CPQ Configuration',
        ondelete='set null', copy=False,
    )
    cpq_summary = fields.Text(
        'CPQ Summary', related='cpq_configuration_id.summary',
        store=True,
    )
    is_cpq = fields.Boolean(
        compute='_compute_cpq_product_id', store=True,
    )

    @api.depends('product_id')
    def _compute_cpq_product_id(self):
        for line in self:
            if line.product_id:
                cpq = self.env['cpq.product'].search([
                    ('product_tmpl_id', '=', line.product_id.product_tmpl_id.id)
                ], limit=1)
                line.cpq_product_id = cpq
                line.is_cpq = bool(cpq)
            else:
                line.cpq_product_id = False
                line.is_cpq = False

    def _compute_display_name(self):
        if self.env.context.get('cpq_selector'):
            for line in self:
                qty = f"{line.product_uom_qty:.0f} \u00d7 " if line.product_uom_qty != 1 else ""
                status = " \u2713" if line.cpq_configuration_id else " \u25cb"
                line.display_name = f"{qty}{line.product_id.name}{status}"
        else:
            super()._compute_display_name()

    def action_configure_cpq(self):
        self.ensure_one()
        if not self.cpq_product_id:
            return
        if not self.id:
            raise UserError(
                "Please save the quotation before configuring the product."
            )
        wizard_vals = {
            'sale_line_id': self.id,
            'cpq_product_id': self.cpq_product_id.id,
        }
        wizard = self.env['cpq.configurator.wizard'].create(wizard_vals)
        wizard._init_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Configure Product',
            'res_model': 'cpq.configurator.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'dialog_size': 'medium'},
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cpq_line_count = fields.Integer(
        'CPQ Lines',
        compute='_compute_cpq_line_count',
    )
    cpq_unconfigured_count = fields.Integer(
        'Unconfigured CPQ Lines',
        compute='_compute_cpq_line_count',
    )

    @api.depends('order_line.is_cpq', 'order_line.cpq_configuration_id')
    def _compute_cpq_line_count(self):
        for order in self:
            cpq_lines = order.order_line.filtered('is_cpq')
            order.cpq_line_count = len(cpq_lines)
            order.cpq_unconfigured_count = len(
                cpq_lines.filtered(lambda l: not l.cpq_configuration_id)
            )

    def action_configure_cpq_lines(self):
        self.ensure_one()
        cpq_lines = self.order_line.filtered('is_cpq')
        if not cpq_lines:
            return
        if len(cpq_lines) == 1:
            return cpq_lines[0].action_configure_cpq()
        selector = self.env['cpq.line.selector'].create({
            'order_id': self.id,
            'line_id': cpq_lines.filtered(lambda l: not l.cpq_configuration_id)[:1].id
                       or cpq_lines[0].id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Choose a product to configure',
            'res_model': 'cpq.line.selector',
            'res_id': selector.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'cpq_selector': True},
        }


class CpqLineSelector(models.TransientModel):
    _name = 'cpq.line.selector'
    _description = 'CPQ Line Selection'

    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade')
    line_id = fields.Many2one(
        'sale.order.line',
        string='Product to configure',
        domain="[('order_id', '=', order_id), ('is_cpq', '=', True)]",
        required=True,
    )
    line_summary = fields.Text(
        related='line_id.cpq_summary', string='Current configuration', readonly=True,
    )

    def action_open_configurator(self):
        self.ensure_one()
        return self.line_id.action_configure_cpq()
