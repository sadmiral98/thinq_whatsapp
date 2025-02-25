
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext
from markupsafe import Markup

import logging
_logger = logging.getLogger('ejip.tech-lab.space')

class Channel(models.Model):
    _inherit = 'discuss.channel'

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        res = super()._notify_thread(message, msg_vals , **kwargs)
        msg_type = msg_vals.get('message_type',False)
        self.process_whatsapp_message(message,msg_vals)
        # if msg_type == 'whatsapp_message':
        #     self.process_whatsapp_message(message,msg_vals)
        return res
    
    def process_whatsapp_message(self,message,msg_vals):
        _logger.info("message")
        _logger.info(message)
        _logger.info("msg_vals")
        _logger.info(msg_vals)
        return True