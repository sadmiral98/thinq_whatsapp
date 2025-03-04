
from odoo import _, api, fields, models
from markupsafe import Markup
from datetime import datetime, timedelta
import json
from bs4 import BeautifulSoup
import re

import logging
_logger = logging.getLogger('ejip.tech-lab.space')

class Channel(models.Model):
    _inherit = 'discuss.channel'

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        res = super()._notify_thread(message, msg_vals , **kwargs)
        admin_user = self.env.company.whatsapp_user_id
        if admin_user.partner_id.id != message.author_id.id:
            session = self.env['whatsapp.chat.session'].search([
                ('partner_id', '=', message.author_id.id),
                ('write_date', '>=', datetime.now() - timedelta(minutes=30)),
                ('chat_state', 'not in', ['end']),
            ])
            if not session:
                session = self.env['whatsapp.chat.session'].create({
                    'partner_id': message.author_id.id,
                    'lang': 'indo',
                    'is_active': True,
                    'chat_state': 'greeting',
                })


            if session.chat_state != 'assigned_to_agent':
                msg_type = msg_vals.get('message_type',False)
                # self.process_whatsapp_message(message, msg_vals, admin_user, session)
                if msg_type == 'whatsapp_message':
                    self.process_whatsapp_message(message, msg_vals, admin_user, session)
        return res
    
    def process_whatsapp_message(self, message, msg_vals, admin_user, session):
        message_text = str(msg_vals['body'])
        message_text = BeautifulSoup(message_text, "html.parser").get_text() #clean html elements if exist

        msg_type = msg_vals.get('message_type',False)
        
        reply_data = {
            'type':'text',
            'header': '',
            'message': '',
            'action':''
        }
        if message_text.lower().startswith('hello') and session.chat_state == 'greeting' :
            reply_message = '''Thank you for contacting ELSA (EJIP Layanan Sistem Automatic). How may I assist you? For service in English, press English button.'
            '''
            reply_data['type'] = 'button'
            reply_data['header'] = 'Select Language'
            reply_data['message'] = reply_message
            reply_data['action'] = ['Indonesia','English']
        elif message_text.lower() in ('special-main-menu','special-agent','special-end'):
            if message_text.lower() == 'special-main-menu':
                reply_message = '''Thank you for contacting ELSA (EJIP Layanan Sistem Automatic). How may I assist you? For service in English, press English button.'
                '''
                reply_data['type'] = 'button'
                reply_data['header'] = 'Select Language'
                reply_data['message'] = reply_message
                reply_data['action'] = ['Indonesia','English']
                session.option_selected_json = "{}"
                session.chat_state = 'greeting'
            elif message_text.lower() == 'special-agent':
                if session.lang == 'indo':
                    reply_message = "Mohon menunggu, tim kami akan segera membalas pesan Anda."
                else:
                    reply_message = "Please wait, our team will reply your message soon."
                session.chat_state = 'assigned_to_agent'
                reply_data['message'] = reply_message
            else:
                if session.lang == 'indo':
                    reply_message = "Terima kasih telah menghubungi kami. Kami tutup percakapan ini. Semoga hari anda menyenangkan."
                else:
                    reply_message = "Thank you for contacting us. We will close this conversation. Have a great day"
                session.chat_state = 'end'
                reply_data['message'] = reply_message
        else:
            reply_message, reply_data = self.process_whatsapp_reply(message, msg_vals, message_text, admin_user, session)
        self.thinq_submit_reply(admin_user, reply_message, msg_type, reply_data)
        return True

    def thinq_submit_reply(self, user, reply_message, message_type, reply_data):
        subtype_xmlid = 'mail.mt_comment'
        reply_message = Markup(reply_message)
        self.with_user(user).with_context(reply_data=reply_data).message_post(body=reply_message, message_type=message_type, subtype_xmlid=subtype_xmlid)

        second_actions = reply_data.get('second_action',False)
        _logger.info("second_actions >>> %s", second_actions)
        if second_actions:
            for action in second_actions:
                self.with_user(user).with_context(reply_data=action).message_post(body='', message_type=message_type, subtype_xmlid=subtype_xmlid)


    def process_whatsapp_reply(self, message, msg_vals, message_text, admin_user, session):
        reply_message = 'Something wrong'
        reply_data = {
            'type':'text',
            'header': '',
            'message': '',
            'action':''
        }
        if session.chat_state == 'greeting':
            if 'indonesia' in message_text.lower():
                reply_data['type'] = 'list'
                reply_data['header'] = "Pilih Layanan"
                reply_data['action'] = [
                    {'id':'submit','description':'Submit tiket (laporan/pengaduan)'},
                    {'id':'ticket','description':'Lihat status tiket'},
                    {'id':'special-agent','description':'Terhubung dengan agent'}
                ]
                session.lang = 'indo'
                session.chat_state = 'service'
                reply_message = "Silahkan pilih 1 dari layanan yang tersedia"
            elif 'english' in message_text.lower():
                reply_data['type'] = 'list'
                reply_data['header'] = "Select Services"
                reply_data['action'] = [
                    {'id':'submit','description':'Submit ticket (report/complain)'},
                    {'id':'ticket','description':'Ticket status'},
                    {'id':'special-agent','description':'Connect with agent'}
                ]
                session.lang = 'english'    
                session.chat_state = 'service'
                reply_message = "Please select 1 from available services"
            else:
                reply_data['type'] = 'text'
                reply_message = "I'm sorry i don't understand, try start the message with 'hello !'"
            
            reply_data['message'] = reply_message

        elif session.chat_state == 'service':
            config = self.env['whatsapp.chatbot.config'].search([('lang','=',session.lang),('chat_state','=','service_selected'),('chat_type','=',message_text.lower())],limit=1)
            if message_text.lower().startswith(('submit', 'ticket')):
                selected_json = session.option_selected_json
                selected_json_dict = json.loads(selected_json)
                selected_json_dict['type_service'] = message_text[:6]
                selected_json = json.dumps(selected_json_dict)
                session.option_selected_json = selected_json

            if message_text.lower().startswith("submit"):
                if session.lang == 'indo':
                    reply_data['type'] = 'list'
                    reply_data['header'] = "Pilih Jenis Layanan"
                    ticket_types = self.env['helpdesk.ticket.type'].search([])
                    actions = []
                    for ticket_type in ticket_types:
                        actions.append({
                            'id': ticket_type.code,
                            'description': ticket_type.name
                        })
                    actions.append({
                        'id': "special-main-menu",
                        'description': "Kembali ke main menu"
                    })
                    reply_data['action'] = actions
                    reply_message = config.header_message
                    reply_message = self.update_reply_message(reply_message, "customer_name", message.author_id.name)
                else:
                    reply_data['type'] = 'list'
                    reply_data['header'] = "Select service type"
                    ticket_types = self.env['helpdesk.ticket.type'].search([])
                    actions = []
                    for ticket_type in ticket_types:
                        actions.append({
                            'id': ticket_type.code,
                            'description': ticket_type.name
                        })
                    actions.append({
                        'id': "special-main-menu",
                        'description': "Back to main menu"
                    })
                    reply_data['action'] = actions
                    reply_message = config.header_message
                    reply_message = self.update_reply_message(reply_message, "customer_name", message.author_id.name)

                reply_data['message'] = reply_message
            elif message_text.lower().startswith("ticket"):
                reply_message = config.header_message
                reply_data['type'] = 'text'
                reply_data['message'] = reply_message
            session.chat_state = 'service_selected'

        elif session.chat_state == 'service_selected':
            selected_json = session.option_selected_json
            selected_json_dict = json.loads(selected_json)
            selected_type_service = selected_json_dict.get('type_service')
            config = self.env['whatsapp.chatbot.config'].search([('lang','=',session.lang),('chat_state','=','customer_response'),('chat_type','=',selected_type_service)],limit=1)
            ticket_types = self.env['helpdesk.ticket.type'].search([])
            ticket_codes = ticket_types.mapped("code")

            if selected_type_service == 'submit':
                if message_text.startswith(tuple(ticket_codes)):    
                    selected_json_dict['service_category'] = message_text
                    selected_json = json.dumps(selected_json_dict)
                    session.option_selected_json = selected_json
                    session.chat_state = 'customer_response'

                    reply_message = config.header_message
                    reply_data['message'] = reply_message

            else:
                # ticket = self.env['helpdesk.ticket'].search([('name','=',message_text)],limit=1)
                ticket = self.env['helpdesk.ticket'].search([('number','=',message_text)],limit=1)
                if ticket:
                    selected_json_dict['ticket_id'] = ticket.id
                    selected_json = json.dumps(selected_json_dict)
                    session.option_selected_json = selected_json
                    session.chat_state = 'customer_response'

                    reply_message = config.header_message
                    reply_message = self.update_reply_message(reply_message, "ticket_status", ticket.stage_id.name)
                    reply_data['message'] = reply_message

                    reply_data['type'] = 'list'
                    if session.lang == 'indo':
                        actions = [{
                            'id': "special-main-menu",
                            'description': "Kembali ke menu awal"
                        },
                        {
                            'id': "detail-ticket",
                            'description': "Detail Status"
                        },
                        {
                            'id': "special-end",
                            'description': "Akhiri Percakapan"
                        }]
                        reply_data['action'] = actions
                    else:
                        actions = [{
                            'id': "special-main-menu",
                            'description': "Back to main menu"
                        },
                        {
                            'id': "detail-ticket",
                            'description': "Status Detail"
                        },
                        {
                            'id': "special-end",
                            'description': "End Conversation"
                        }]
                        reply_data['action'] = actions
                else:
                    if session.lang == 'indo':
                        reply_message = "Tiket anda tidak ditemukan, Cek kembali nomor tiket anda"
                        actions = [{
                            'id': "special-main-menu",
                            'description': "Kembali ke menu awal"
                        },
                        {
                            'id': "special-agent",
                            'description': "Terhubung dengan agent"
                        }]
                        reply_data['action'] = actions
                    else:
                        reply_message = "The ticket number you entered could not be found. Please check your ticket number"
                        actions = [{
                            'id': "special-main-menu",
                            'description': "Back to main menu"
                        },
                        {
                            'id': "special-agent",
                            'description': "Connect with our agent"
                        }]
                        reply_data['action'] = actions
                        
                    reply_data['type'] = 'list'
                    reply_data['message'] = reply_message

        elif session.chat_state == 'customer_response':
            selected_json = session.option_selected_json
            selected_json_dict = json.loads(selected_json)
            selected_type_service = selected_json_dict.get('type_service')
            config = self.env['whatsapp.chatbot.config'].search([('lang','=',session.lang),('chat_state','=','final_service'),('chat_type','=',selected_type_service)],limit=1)
            config_media = self.env['whatsapp.chatbot.config'].search([('lang','=',session.lang),('chat_state','=','customer_response'),('chat_type','=',selected_type_service)],limit=1)
            
            if selected_type_service == 'submit':
                if 'data' not in selected_json_dict:
                    selected_json_dict['data'] = message_text
                    selected_json = json.dumps(selected_json_dict)
                    session.option_selected_json = selected_json
                    reply_message = config_media.footer_message
                    button_text = "No"
                    if session.lang == 'indo':
                        button_text = "Tidak"
                    
                    reply_data['type'] = 'button'
                    reply_data['header'] = 'Send Document or Skip'
                    reply_data['message'] = reply_message
                    reply_data['action'] = [button_text]
                else:
                    ticket_type = self.env['helpdesk.ticket.type'].search([('code','=',selected_json_dict.get('service_category'))],limit=1)
                    ticket_subject = ticket_type.name
                    find_subject = False
                    if session.lang == 'indo':
                        find_subject = re.search(r'Detail keluhan:\s*(.*)', selected_json_dict['data'], re.DOTALL)
                    else:
                        find_subject = re.search(r'Complaint details:\s*(.*)', selected_json_dict['data'], re.DOTALL)

                    if find_subject:
                        ticket_subject = find_subject.group(1)

                    partner = message.author_id
                    # ticket_type = self.env['helpdesk.ticket.type'].search([('code','=','WA')],limit=1)
                    ticket_team = self.env['helpdesk.team'].browse(1)
                    ticket = self.env['helpdesk.ticket'].create({
                        'number':'New',
                        'name': ticket_subject,
                        'team_id': ticket_team.id,
                        'user_id': admin_user.id,
                        'ticket_type_id': ticket_type.id,
                        'partner_id':partner.id,
                        'partner_phone':partner.phone,
                        'description':selected_json_dict['data'],
                        'agent_pic_uid': admin_user.id
                    })
                    session.chat_state = 'final_service'

                    if msg_vals and msg_vals.get('attachment_ids') and msg_vals.get('message_type') == 'whatsapp_message':
                        attachment_ids = []
                        
                        # Extract the attachment IDs
                        for command in msg_vals['attachment_ids']:
                            # Handle command format (4, id) which is a link command
                            if isinstance(command, tuple) and command[0] == 4:
                                attachment_ids.append(command[1])
                        
                        if attachment_ids:
                            attachment_obj = self.env['ir.attachment']
                            attachments = attachment_obj.browse(attachment_ids)
                            
                            for attachment in attachments:
                                attachment.copy({
                                    'res_model': 'helpdesk.ticket',
                                    'res_id': ticket.id,
                                })
                                
                    reply_message = config.header_message
                    reply_message = self.update_reply_message(reply_message, "ticket_id", ticket.number)
                    # reply_message = self.update_reply_message(reply_message, "ticket_id", ticket.name)

                    reply_message += "{nl}{nl}"
                    reply_message += config.footer_message

                    reply_data['type'] = 'text'
                    reply_data['message'] = reply_message
            else:
                if message_text == 'detail-ticket':
                    ticket_id = selected_json_dict['ticket_id']
                    ticket = self.env['helpdesk.ticket'].browse(ticket_id)
                    attachments = self.env['ir.attachment'].search([
                        ('res_model','=','helpdesk.ticket'),
                        ('res_id','=',ticket.id)
                    ])
                    if session.lang == 'indo':
                        reply_message = f"Status tiket: {ticket.stage_id.name}, deskripsi = {ticket.description}"
                        actions = [{
                            'id': "special-main-menu",
                            'description': "Kembali ke menu awal"
                        },
                        {
                            'id': "special-end",
                            'description': "Akhiri Percakapan"
                        }]
                        reply_data['action'] = actions
                    else:
                        reply_message = f"Status ticket: {ticket.stage_id.name}, description = {ticket.description}"
                        actions = [{
                            'id': "special-main-menu",
                            'description': "Back to main menu"
                        },
                        {
                            'id': "special-end",
                            'description': "End Conversation"
                        }]
                        reply_data['action'] = actions

                    reply_data['second_action'] = []
                    for att in attachments:
                        reply_data['second_action'].append({
                            'type':'media',
                            'media': att.id
                        })
                else:
                    if session.lang == 'indo':
                        reply_message = "Maaf saya kurang mengerti"
                        actions = [{
                            'id': "special-main-menu",
                            'description': "Kembali ke menu awal"
                        },
                        {
                            'id': "detail-ticket",
                            'description': "Detail Status"
                        },
                        {
                            'id': "special-end",
                            'description': "Akhiri Percakapan"
                        }]
                        reply_data['action'] = actions
                    else:
                        reply_message = "I'm sorry i don't understand"
                        actions = [{
                            'id': "special-main-menu",
                            'description': "Back to main menu"
                        },
                        {
                            'id': "detail-ticket",
                            'description': "Status Detail"
                        },
                        {
                            'id': "special-end",
                            'description': "End Conversation"
                        }]
                        reply_data['action'] = actions
                reply_data['type'] = 'list'
                reply_data['message'] = reply_message

        elif session.chat_state == 'final_service':
            config = self.env['whatsapp.chatbot.config'].search([('lang','=',session.lang),('chat_state','=','customer_feedback')],limit=1)

            reply_message = config.header_message
            reply_data['type'] = 'text'
            reply_data['message'] = reply_message

            session.chat_state = 'end'
        
        return reply_message, reply_data
    
    def update_reply_message(self, reply_message, param, value_to_replace):
        result = reply_message.replace(f"{{{param}}}", value_to_replace)
        return result