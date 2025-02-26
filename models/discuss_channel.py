
from odoo import _, api, fields, models
from markupsafe import Markup
from datetime import datetime, timedelta
import json
from bs4 import BeautifulSoup

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
            'values': ''
        }
        if message_text.lower().startswith('hello') and session.chat_state in ('greeting') :
            reply_data['type'] = 'button'
            reply_data['values'] = ['Indonesia','English']
            reply_message = '''Thank you for contacting ELSA (EJIP Layanan Sistem Automatic). How may I assist you? For service in English, press English button.'
            '''
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
            'values':'',
        }
        if session.chat_state == 'greeting':
            if 'indonesia' in message_text.lower():
                session.lang = 'indo'
                session.chat_state = 'service'
                reply_message = '''
                    Silahkan Pilih Layanan : <br>
                    Ketik *1* : Submit tiket (laporan/pengaduan) <br>
                    Ketik *2* : Lihat status tiket <br>
                    Ketik *3* : Terhubung dengan agent
                '''
            elif 'english' in message_text.lower():
                session.lang = 'english'    
                session.chat_state = 'service'
                reply_message = '''
                    Please select type of service :  <br>
                    Type *1* : Submit ticket (report/complain) <br>
                    Type *2* : Ticket status <br>
                    Type *3* : Connect with agent
                '''
            else:
                reply_message = "I'm sorry i don't understand, try start the message with 'hello !'"
        elif session.chat_state == 'service':
            if message_text in ('1','2','3'):
                selected_json = session.option_selected_json
                selected_json_dict = json.loads(selected_json)
                selected_json_dict['type_service'] = message_text
                selected_json = json.dumps(selected_json_dict)
                session.option_selected_json = selected_json
            else:
                return "Your Input is invalid. Please select between 1 / 2 / 3"

            if message_text == "1":
                if session.lang == 'indo':
                    reply_message = f'''
                        Apa yang bisa kami bantu -{message.author_id.name}- ?  <br>
                        Ketik *1* : Maintenance & Infrastruktur <br>
                        Ketik *2* : Keamanan, Damkar & Lalu lintas <br>
                        Ketik *3* : Air & Limbah, RKL-RPL Rinci/Rintek  <br>
                        Ketik *4* : Laboratorium EJIP, Analisa, LHU <br>
                        Ketik *5* : Administrasi, Perizinan & Training <br>
                        Ketik *6* : Rental Factory/Office & Conference Room  <br>
                        Ketik *0* : Kembali ke menu utama <br>

                        Mohon maaf, jika dalam waktu 30 menit tidak ada respon yang kami terima, maka percakapan ini akan kami hentikan.
                    '''
                else:
                    reply_message = f'''
                        How may I assist you? -{message.author_id.name}- ?  <br>
                        Type *1* : Maintenance & Infrastructure <br>
                        Type *2* : Safety, Fire Fighting & Traffic <br>
                        Type *3* : Enviro. Management License, Waste & Industrial Water <br>
                        Type *4* : EJIP Laboratory, Analysis, Testing Report <br>
                        Type *5* : Administration, Approval & Training <br>
                        Type *6* : Rental Factory/Office & Conference Room <br>
                        Type *0* : Back to main menu <br>

                        If we receive no response within 30 minutes, this conversation will be automatically closed.
                    '''
                session.chat_state = 'service_selected'
        elif session.chat_state == 'service_selected':
            if message_text in ('1','2','3','4','5','6','0'):
                selected_json = session.option_selected_json
                selected_json_dict = json.loads(selected_json)
                selected_json_dict['service_category'] = message_text
                selected_json = json.dumps(selected_json_dict)
                session.option_selected_json = selected_json
                session.chat_state = 'customer_response'
            else:
                return "Your Input is invalid. Please select between 1 / 2 / 3 / 4 / 5 / 6 / 0"
            
            if message_text == "1":
                if session.lang == 'indo':
                    reply_message = f'''
                        Silahkan melengkapi data berikut ini :
                    '''
                else:
                    reply_message = f'''
                        Please complete the following data:
                    '''
        elif session.chat_state == 'customer_response':
            def is_valid_json(input_str):
                try:
                    json.loads(input_str)
                    return True
                except json.JSONDecodeError:
                    return False
            if is_valid_json(message_text):
                message_text_json = json.loads(message_text)
                data = message_text_json.get('data')

                selected_json = session.option_selected_json
                selected_json_dict = json.loads(selected_json)
                selected_json_dict['data'] = data
                selected_json = json.dumps(selected_json_dict)
                session.option_selected_json = selected_json
                session.chat_state = 'final_service'
            else:
                return "Your Input is invalid. Please follow the instruction!"
            
        #     if message_text == "1":

        # ticket_subject = message_text[len('ct: '):].strip()  
        # partner = message.author_id
        # ticket_type = self.env['helpdesk.ticket.type'].search([('code','=','WA')],limit=1)
        # ticket_team = self.env['helpdesk.team'].browse(1)
        # ticket = self.env['helpdesk.ticket'].create({
        #     'number':'New',
        #     'name': ticket_subject,
        #     'team_id': ticket_team.id,
        #     'user_id': admin_user.id,
        #     'ticket_type_id': ticket_type.id,
        #     'partner_id':partner.id,
        #     'partner_phone':partner.phone,
        #     'agent_pic_uid': admin_user.id
        # })
        return reply_message, reply_data