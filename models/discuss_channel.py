
from odoo import _, api, fields, models
from markupsafe import Markup
from datetime import datetime, timedelta
import json
from bs4 import BeautifulSoup
import re

import logging
# _logger = logging.getLogger('ejip.tech-lab.space')
_logger = logging.getLogger('dke.iziapp.id')

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
        if message_text.lower().startswith('hello') and session.chat_state in ('greeting') :
            reply_message = '''Thank you for contacting ELSA (EJIP Layanan Sistem Automatic). How may I assist you? For service in English, press English button.'
            '''
            reply_data['type'] = 'button'
            reply_data['header'] = 'Select Language'
            reply_data['message'] = reply_message
            reply_data['action'] = ['Indonesia','English']
        else:
            reply_message, reply_data = self.process_whatsapp_reply(message, msg_vals, message_text, admin_user, session)
        self.thinq_submit_reply(admin_user, reply_message, msg_type, reply_data)
        return True

    def thinq_submit_reply(self, user, reply_message, message_type, reply_data):
        subtype_xmlid = 'mail.mt_comment'
        reply_message = Markup(reply_message)
        self.with_user(user).with_context(reply_data=reply_data).message_post(body=reply_message, message_type=message_type, subtype_xmlid=subtype_xmlid)

    def process_whatsapp_reply(self, message, msg_vals, message_text, admin_user, session):
        reply_message = 'Something wrong'
        reply_data = {
            'type':'text',
            'header': '',
            'message': '',
            'action':''
        }
        _logger.info("MESSAGE_TEXT >>> %s", message_text)

        if session.chat_state == 'greeting':
            if 'indonesia' in message_text.lower():
                reply_data['type'] = 'list'
                reply_data['header'] = "Pilih Layanan"
                reply_data['action'] = [
                    {'id':'submit','description':'Submit tiket (laporan/pengaduan)'},
                    {'id':'ticket','description':'Lihat status tiket'},
                    {'id':'agents','description':'Terhubung dengan agent'}
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
                    {'id':'agents','description':'Connect with agent'}
                ]
                session.lang = 'english'    
                session.chat_state = 'service'
                reply_message = "Please select 1 from available services"
            else:
                reply_data['type'] = 'text'
                reply_message = "I'm sorry i don't understand, try start the message with 'hello !'"
            
            reply_data['message'] = reply_message

        elif session.chat_state == 'service':
            config = self.env['whatsapp.chatbot.config'].search([('lang','=',session.lang),('chat_state','=','service_selected')],limit=1)
            if message_text.lower().startswith(('submit', 'ticket', 'agents')):
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
                        'id': "0",
                        'description': "Kembali ke main menu"
                    })
                    reply_data['action'] = actions
                    reply_message = config.header_message
                    reply_message = self.update_reply_message(reply_message, "customer_name", message.author_id.name)
                else:
                    reply_data['type'] = 'list'
                    reply_data['header'] = "Pilih Jenis Layanan"
                    reply_data['action'] = [
                        {'id':'1','description':'Maintenance & Infrastructure'},
                        {'id':'2','description':'Safety, Fire Fighting & Traffic'},
                        {'id':'3','description':'Enviro. Management License, Waste & Industrial Water'},
                        {'id':'4','description':'EJIP Laboratory, Analysis, Testing Report'},
                        {'id':'5','description':'Administration, Approval & Training'},
                        {'id':'6','description':'Rental Factory/Office & Conference Room'},
                        {'id':'0','description':'Back to main menu'},
                    ]
                    reply_message = f"How may I assist you -- ? "
                    # reply_message = f'''
                    #     How may I assist you? -{message.author_id.name}- ?  <br> \n
                    #     Type *1* : Maintenance & Infrastructure <br> \n
                    #     Type *2* : Safety, Fire Fighting & Traffic <br> \n
                    #     Type *3* : Enviro. Management License, Waste & Industrial Water <br> \n
                    #     Type *4* : EJIP Laboratory, Analysis, Testing Report <br> \n
                    #     Type *5* : Administration, Approval & Training <br> \n
                    #     Type *6* : Rental Factory/Office & Conference Room <br> \n
                    #     Type *0* : Back to main menu <br> \n

                    #     If we receive no response within 30 minutes, this conversation will be automatically closed.
                    # '''
                reply_data['message'] = reply_message
                session.chat_state = 'service_selected'
        elif session.chat_state == 'service_selected':
            config = self.env['whatsapp.chatbot.config'].search([('lang','=',session.lang),('chat_state','=','customer_response')],limit=1)
            ticket_types = self.env['helpdesk.ticket.type'].search([])
            ticket_codes = ticket_types.mapped("code")
            if message_text.startswith(tuple(ticket_codes)):
            # if message_text.startswith(('1','2','3','4','5','6','0')):
                selected_json = session.option_selected_json
                selected_json_dict = json.loads(selected_json)
                selected_json_dict['service_category'] = message_text
                selected_json = json.dumps(selected_json_dict)
                session.option_selected_json = selected_json
                session.chat_state = 'customer_response'

                reply_message = config.header_message

                reply_data['type'] = 'text'
                reply_data['message'] = reply_message

            # if message_text.startswith("1"):
                # if session.lang == 'indo':
                #     reply_message = f'''
                #         Silahkan melengkapi data berikut ini :
                #     '''
                # else:
                #     reply_message = f'''
                #         Please complete the following data:
                #     '''
                # reply_data['type'] = 'text'
                # reply_data['message'] = reply_message
        elif session.chat_state == 'customer_response':
            config = self.env['whatsapp.chatbot.config'].search([('lang','=',session.lang),('chat_state','=','final_service')],limit=1)
            

            selected_json = session.option_selected_json
            selected_json_dict = json.loads(selected_json)
            selected_json_dict['data'] = message_text
            # selected_json = json.dumps(selected_json_dict)
            # session.option_selected_json = selected_json

            # {"type_service": "submit", "service_category": "A", "data": "anjay"}
            ticket_type = self.env['helpdesk.ticket.type'].search([('code','=',selected_json_dict.get('service_category'))],limit=1)
            ticket_subject = ticket_type.name
            find_subject = re.search(r'Detail keluhan:\s*(.*)', message_text, re.DOTALL)
            if find_subject:
                ticket_subject = find_subject.group(1)

            partner = message.author_id
            ticket_type = self.env['helpdesk.ticket.type'].search([('code','=','WA')],limit=1)
            ticket_team = self.env['helpdesk.team'].browse(1)
            ticket = self.env['helpdesk.ticket'].create({
                'number':'New',
                'name': ticket_subject,
                'team_id': ticket_team.id,
                'user_id': admin_user.id,
                'ticket_type_id': ticket_type.id,
                'partner_id':partner.id,
                'partner_phone':partner.phone,
                'agent_pic_uid': admin_user.id
            })
            session.chat_state = 'final_service'

            reply_message = config.header_message , "{nl}{nl}", config.footer_message
            reply_message = self.update_reply_message(reply_message, "ticket_id", ticket.number)

            reply_data['type'] = 'text'
            reply_data['message'] = reply_message

        elif session.chat_state == 'final_service':
            config = self.env['whatsapp.chatbot.config'].search([('lang','=',session.lang),('chat_state','=','customer_feedback')],limit=1)

            reply_message = config.header_message
            reply_data['type'] = 'text'
            reply_data['message'] = reply_message
        
        return reply_message, reply_data
    
    def update_reply_message(self, reply_message, param, value_to_replace):
        result = reply_message.replace(f"{{{param}}}", value_to_replace)
        return result