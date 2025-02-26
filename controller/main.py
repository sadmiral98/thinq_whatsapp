# -*- coding: utf-8 -*-
# Copyright 2022 IZI PT Solusi Usaha Mudah
from odoo import http, fields
from datetime import datetime, timedelta
from odoo.http import request
from bs4 import BeautifulSoup
from odoo.addons.whatsapp.controller.main import Webhook
import requests
import threading
import json
import base64

from odoo import _
from odoo.exceptions import RedirectWarning
from odoo.addons.whatsapp.tools.whatsapp_api import WhatsAppApi
from odoo.addons.whatsapp.tools.whatsapp_exception import WhatsAppError

import logging
_logger = logging.getLogger('dke.iziapp.id')


DEFAULT_ENDPOINT = "https://graph.facebook.com/v17.0"

# R: monkey patching
original_send_whatsapp = WhatsAppApi._send_whatsapp

def custom_api_request(self, request_type, url, auth_type="", params=False, headers=None, data=False, files=False, endpoint_include=False):
    if getattr(threading.current_thread(), 'testing', False):
        raise WhatsAppError("API requests disabled in testing.")

    headers = headers or {}
    params = params or {}
    if not all([self.token, self.phone_uid]):
        action = self.wa_account_id.env.ref('whatsapp.whatsapp_account_action')
        raise RedirectWarning(_("To use WhatsApp Configure it first"), action=action.id, button_text=_("Configure Whatsapp Business Account"))
    if auth_type == 'oauth':
        headers.update({'Authorization': f'OAuth {self.token}'})
    if auth_type == 'bearer':
        headers.update({'Authorization': f'Bearer {self.token}'})
    call_url = (DEFAULT_ENDPOINT + url) if not endpoint_include else url

    try:
        res = requests.request(request_type, call_url, params=params, headers=headers, data=data, files=files, timeout=10)
    except requests.exceptions.RequestException:
        raise WhatsAppError(failure_type='network')

    # raise if json-parseable and 'error' in json
    try:
        if 'error' in res.json():
            raise WhatsAppError(*self.custom_prepare_error_response(res.json()))
    except ValueError:
        if not res.ok:
            raise WhatsAppError(failure_type='network')

    return res

def custom_prepare_error_response(self, response):
    """
        This method is used to prepare error response
        :return tuple[str, int]: (error_message, whatsapp_error_code | -1)
    """
    if response.get('error'):
        error = response['error']
        desc = error.get('message')
        code = error.get('code', 'odoo')
        return (desc if desc else _("{error_code} - Non-descript Error", code), code)
    return (_("Something went wrong when contacting WhatsApp, please try again later. If this happens frequently, contact support."), -1)

# def get_media_id(self, file_content, file_name, mimetype):
#     files = {
#         'file': (file_name, file_content, mimetype),
#         'type': (None, mimetype),                    # Non-file field
#         'messaging_product': (None, 'whatsapp')
#     }
#     url = f"{DEFAULT_ENDPOINT}/{self.phone_uid}/media"
#     headers={
#         # 'Content-Type': 'application/json',
#         'Authorization': f'Bearer {self.token}'
#     }
#     response = requests.post(url, headers=headers, files=files)

#     if response.status_code == 200:
#         media_id = response.json().get('id')
#         return media_id
#     return media_id

# def custom_process_image(self, data, send_vals):
#     attachment = self.wa_account_id.env['ir.attachment'].sudo().browse(1341)
#     file_content = base64.b64decode(attachment.datas)
#     file_name = attachment.name
#     mimetype = attachment.mimetype
#     media_id = self.get_media_id(file_content, file_name, mimetype)
#     data.update({
#         'type': 'image',
#         'image': {
#             'id' : media_id,
#             'caption': send_vals.get('body'),
#         }
#     })
#     return data

# def custom_process_document(self, data, send_vals, discuss_data):
#     attachment_id = discuss_data.get('discuss_attachment')
#     attachment = self.wa_account_id.env['ir.attachment'].sudo().browse(int(attachment_id))
#     file_content = base64.b64decode(attachment.datas)
#     file_name = attachment.name
#     mimetype = attachment.mimetype
#     media_id = self.get_media_id(file_content, file_name, mimetype)
#     data.update({
#         'type': 'document',
#         'document': {
#             'id' : media_id,
#             'caption': send_vals.get('body'),
#             'filename': f'{file_name}.pdf'
#         }
#     })
#     return data

def custom_process_flow(self, data, send_vals, reply_data):
    data.update({
        'type': 'interactive',
        'interactive': {
            'type': 'flow',
            'header': {
                'type': 'text',
                'text': 'Flow message header'
            },
            'body': {
                'text': 'Flow message body'
            },
            'footer': {
                'text': 'Flow message footer'
            },
            'action': {
                'name': 'flow',
                'parameters': {
                    'flow_message_version': '3',
                    'flow_token': 'AQAAAAACS5FpgQ_cAAAAAD0QI3s.',
                    'flow_id': '1',
                    'flow_cta': 'Book!',
                    'flow_action': 'navigate',
                    'flow_action_payload': {
                        'screen': '<SCREEN_NAME>',
                        'data': { 
                            'product_name': 'name',
                            'product_description': 'description',
                            'product_price': 100
                        }
                    }
                }
            }
        }
    })

def custom_process_list(self, data, send_vals, reply_data):
    actions = reply_data.get('action')
    header = reply_data.get('header','')
    body = reply_data.get('message','')
    sections = [{
            'title': header,
        }]
    section_rows = []
    for act in actions:
        section_rows.append(
            {
                'id': act.get('id'),
                'title': act.get('description'),
                'description': ''
            }
        )
    sections[0]['rows'] = section_rows

    data.update({
        'type': 'interactive',
        'interactive': {
            'type': 'list',
            'header': {
                'type':'text',
                'text': header
            },
            'body': {
                'text': body
            },
            'footer': {
                'text': 'Select 1 item'
            },
            'action': {
                'sections': sections,
                'button': 'button text~',
                # 'sections': [
                #     {
                #     'title': '<SECTION_TITLE_TEXT>',
                #     'rows': [
                #         {
                #         'id': '<ROW_ID>',
                #         'title': '<ROW_TITLE_TEXT>',
                #         'description': '<ROW_DESCRIPTION_TEXT>'
                #         }
                #         /* Additional rows would go here*/
                #     ]
                #     }
                #     /* Additional sections would go here */
                # ],
                # 'button': '<BUTTON_TEXT>',
            }
        }
    })
    return data

def custom_process_button(self, data, send_vals, reply_data):
    actions = reply_data.get('action')
    header = reply_data.get('header','')
    body = reply_data.get('message','')
    buttons = []
    for act in actions:
        buttons.append({
            'type': 'reply',
            'reply': {
                'id': f'reply-{act}',
                'title': act
            }
        })

    data.update({
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'header': {
                'type':'text',
                'text': header
            },
            'body': {
                'text': body
            },
            'action': {
                'buttons': buttons
            }
            # 'action': {
                # 'buttons': [
                #     {
                #     'type': 'reply',
                #     'reply': {
                #         'id': 'reply-yes',
                #         'title': 'Yeah !'
                #         }
                #     },
                #     {
                #     'type': 'reply',
                #     'reply': {
                #         'id': 'reply-no',
                #         'title': 'Nope ?!'
                #         }
                #     }
                # ]
            # }
        }
    })
    return data
def custom_send_whatsapp(self, number, message_type, send_vals, parent_message_id=False, reply_data={}):
    """ Send WA messages for all message type using WhatsApp Business Account

    API Documentation:
        Normal        - https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages
        Template send - https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates
    """
    data = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': number
    }
    # if there is parent_message_id then we send message as reply
    if parent_message_id:
        data.update({
            'context': {
                'message_id': parent_message_id
            },
        })
    if message_type in ('template','document', 'image', 'audio', 'video'):
        data.update({
            'type': message_type,
            message_type: send_vals
        })
    if message_type == 'text':
        _logger.info("message ==>  %s ", message_type)
        if reply_data:
            if reply_data.get('type') == 'button':
                data = self.custom_process_button(data, send_vals, reply_data)

            elif reply_data.get('type') == 'list':
                data = self.custom_process_list(data, send_vals, reply_data)

            elif reply_data.get('type') == 'flow':
                data = self.custom_process_flow(data, send_vals, reply_data)

        #     elif discuss_data.get('discuss_type') == 'document':
        #         # document reply chat
        #         data = self.custom_process_document(data, send_vals, discuss_data)

        #     # Image reply chat
        #     # data = self.custom_process_image(data, send_vals)
        
            else: # R; if no records to button, set it as regular text reply
                data.update({
                    'type': message_type,
                    message_type: send_vals
                })
        else: # R; if no records to button, set it as regular text reply
            data.update({
                'type': message_type,
                message_type: send_vals
            })

        _logger.info("data ==>  %s ", data)
        
    json_data = json.dumps(data)
    _logger.info("Send %s message from account %s [%s]", message_type, self.wa_account_id.name, self.wa_account_id.id)
    response = self.custom_api_request(
        "POST",
        f"/{self.phone_uid}/messages",
        auth_type="bearer",
        headers={'Content-Type': 'application/json'},
        data=json_data
    )
    response_json = response.json()
    _logger.info("RESPONSE WHATSAPP API >>> %s", response_json)
    if response_json.get('messages'):
        msg_uid = response_json['messages'][0]['id']
        return msg_uid
    raise WhatsAppError(*self.custom_prepare_error_response(response_json))

WhatsAppApi.custom_api_request = custom_api_request
WhatsAppApi.custom_prepare_error_response = custom_prepare_error_response
# WhatsAppApi.get_media_id = get_media_id
# WhatsAppApi.custom_process_image = custom_process_image
# WhatsAppApi.custom_process_document = custom_process_document
WhatsAppApi.custom_process_flow = custom_process_flow
WhatsAppApi.custom_process_list = custom_process_list
WhatsAppApi.custom_process_button = custom_process_button
WhatsAppApi._send_whatsapp = custom_send_whatsapp
# class WebController(Webhook):
#     @http.route()
#     def webhookpost(self):
#         data = json.loads(request.httprequest.data)
        
#         # _logger.info("\n\ndke.iziapp.id : Webhook Data: %s", json.dumps(data, indent=4))
#         _logger.info("\n\ndke.iziapp.id : req :",request.env.company.id)
#         _logger.info("\n\ndke.iziapp.id : req :",request.env.company.name)
#         _logger.info("\n\ndke.iziapp.id : req :",request.env.company.ngrok_url)
        
#         if request.env.company.ngrok_url:
#             _logger.info("\n\ndke.iziapp.id : POST : ngrok url found!")
#             url = f"{request.env.company.ngrok_url}testwebhookpost"
#             response = requests.post(url, json=data)
#         else:
#             _logger.info("\n\ndke.iziapp.id : POST : ngrok url NOT found!")
#         super().webhookpost()
    # @http.route('/whatsapp/webhook/', methods=['POST'], type="json", auth="public")
    # def webhookpost(self):
        

    #     # Call the original method to ensure parent logic is executed
    #     super(WebController, self).webhookpost()

    
    # @http.route('/whatsapp/webhook/', methods=['GET'], type="http", auth="public", csrf=False)
    # def webhookget(self, **kwargs):
    #     _logger.info("Received GET webhook request with data: %s", kwargs)

    #     if request.env.company.ngrok_url:
    #         _logger.info("\n\n GET : ngrok url found!")
    #         url = request.env.company.ngrok_url
    #         response = requests.get(url, params=kwargs)
    #     else:
    #         _logger.info("\n\n GET : ngrok url not found!")
        
    #     super(WebController, self).webhookget(**kwargs)