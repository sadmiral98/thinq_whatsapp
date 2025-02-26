
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext
from markupsafe import Markup

import logging
# _logger = logging.getLogger('ejip.tech-lab.space')
_logger = logging.getLogger('dke.iziapp.id')

class ResCompany(models.Model):
    _inherit = 'res.company'

    whatsapp_user_id = fields.Many2one('res.users', string='Whatsapp Administrator User')
    
    def clean_session(self):
        sessions = self.env['whatsapp.chat.session'].search([])
        for ses in sessions:
            ses.unlink()