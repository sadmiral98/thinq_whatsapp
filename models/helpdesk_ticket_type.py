# -*- coding: utf-8 -*-
# © 2024 Thinq Technology
from odoo import _, api, fields, models
from odoo.osv import expression
from odoo.exceptions import UserError
from datetime import datetime


class HelpdeskTicketTypes(models.Model):
    _inherit = 'helpdesk.ticket.type'
    
    code = fields.Char(required=True, string="Short Code")
    name = fields.Char(required=True, translate=True, string="Type Name")
    sequence_id = fields.Many2one('ir.sequence', 'Formatted Sequence Number', copy=False)
    active = fields.Boolean(default=True, help="Set active to false to hide the type without removing it.")
    
    _sql_constraints = [
        ('shortcode_uniq', 'unique (code)', "A shortcode with the same code already exists."),
    ]
    
    @api.depends('code', 'name')
    def _compute_display_name(self):
        # OVERRIDE
        for issue_type in self:
            issue_type.display_name = f"[{issue_type.code}] {issue_type.name}"

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if operator != 'ilike' or not (name or '').strip():
            # ignore 'ilike' with name containing only spaces
            domain = expression.AND([['|', ('name', operator, name), ('code', operator, name)], domain])
        return self._search(domain, limit=limit, order=order)

