# -*- coding: utf-8 -*-
# © 2024 Thinq Technology
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from datetime import datetime

class WhatsappChatBotConfig(models.Model):
    _name = 'whatsapp.chatbot.config'
    _description = 'Whatsapp Chatbot Config'

    chat_id = fields.Char('Chat ID')
    lang = fields.Selection([
        ('indo', 'Indonesia'),
        ('english', 'English'),
    ], string='Language')
    # Notes : (A) -> Submit Tiket. (B) -> Informasi Tiket
    chat_state = fields.Selection([
        ('greeting', 'Greeting'), # Pilih Bahasa
        ('service', 'Service'), # Pilih Layanan
        ('assigned_to_agent', 'Assigned to Live Agent'), # Assigned ke Chat Agent
        ('service_selected', 'Service selected'),  # Response dari layanan yang dipilih
        ('customer_response', 'Customer Response'), # Customer telah memilih dari reponse, meminta input dari customer
        ('final_service', 'Final Service'), # (A) Tiket telah dibuat / (B) Detail dari tiket, note, document, foto
        ('customer_feedback', 'Customer Feedback'), # (A) Feedback customer telah diterima
        ('end', 'End Conversation'),
    ], string='Chat State')
    header_message = fields.Text('Header Message')
    footer_message = fields.Text('Footer Message')
    chat_type = fields.Selection([
        ('submit', 'Submit'),
        ('ticket', 'Ticket'),
    ], string='Chat Type')


    @api.depends('chat_id')
    def _compute_display_name(self):
        for chat in self:
            chat.display_name = chat.chat_id

    # def write(self, vals):
    #     context = self.env.context
    #     if 'chat_state' in vals:
    #         if self.parent_id and not context.get('bypass_write'):
    #             raise UserError(_("Not allowed to change state in the child. change on parent only!"))
    #     res = super(WhatsappChatBot, self).write(vals)

    #     childs = self.child_ids
    #     for child in childs:
    #         child.with_context(bypass_write=True).write({
    #             'chat_state':vals['chat_state']
    #         })

    #     return res