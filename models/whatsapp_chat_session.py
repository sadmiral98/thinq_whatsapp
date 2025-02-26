# -*- coding: utf-8 -*-
# © 2024 Thinq Technology
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from datetime import datetime

class WhatsappChatSession(models.Model):
    _name = 'whatsapp.chat.session'
    _description = 'Whatsapp Chat Session'

    partner_id = fields.Many2one('res.partner', string='partner')
    lang = fields.Selection([
        ('english', 'English'),
        ('indo', 'Indonesia'),
    ], string='lang')
    is_active = fields.Boolean('Is Active', default=False)
    option_selected_json = fields.Char('Option Selected', default='{}')
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
    ], string='chat_state')
