# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import mimetypes
import markupsafe
from markupsafe import Markup

from odoo import api, fields, models, _, Command
from odoo.addons.whatsapp.tools.whatsapp_api import WhatsAppApi
from odoo.addons.whatsapp.tools.whatsapp_exception import WhatsAppError
from odoo.tools import groupby, plaintext2html
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger('ejip.tech-lab.space')


class WhatsAppAccount(models.Model):
    _inherit = 'whatsapp.account'

    def _process_messages(self, value):
        """
            This method is used for processing messages with the values received via webhook.
            If any whatsapp message template has been sent from this account then it will find the active channel or
            create new channel with last template message sent to that number and post message in that channel.
            And if channel is not found then it will create new channel with notify user set in account and post message.
            Supported Messages
             => Text Message
             => Attachment Message with caption
             => Location Message
             => Contact Message
             => Message Reactions
        """
        if 'messages' not in value and value.get('whatsapp_business_api_data', {}).get('messages'):
            value = value['whatsapp_business_api_data']

        wa_api = WhatsAppApi(self)

        for messages in value.get('messages', []):
            parent_id = False
            channel = False
            sender_name = value.get('contacts', [{}])[0].get('profile', {}).get('name')
            sender_mobile = messages['from']
            message_type = messages['type']
            if 'context' in messages:
                parent_whatsapp_message = self.env['whatsapp.message'].sudo().search([('msg_uid', '=', messages['context'].get('id'))])
                if parent_whatsapp_message:
                    parent_id = parent_whatsapp_message.mail_message_id
                if parent_id:
                    channel = self.env['discuss.channel'].sudo().search([('message_ids', 'in', parent_id.id)], limit=1)

            if not channel:
                channel = self._find_active_channel(sender_mobile, sender_name=sender_name, create_if_not_found=True)
            kwargs = {
                'message_type': 'whatsapp_message',
                'author_id': channel.whatsapp_partner_id.id,
                'subtype_xmlid': 'mail.mt_comment',
                'parent_id': parent_id.id if parent_id else None
            }
            _logger.warning("Message received process >>: %s", messages)
            if message_type == 'text':
                kwargs['body'] = plaintext2html(messages['text']['body'])
            elif message_type == 'button':
                kwargs['body'] = messages['button']['text']
            elif message_type in ('document', 'image', 'audio', 'video', 'sticker'):
                filename = messages[message_type].get('filename')
                mime_type = messages[message_type].get('mime_type')
                caption = messages[message_type].get('caption')
                datas = wa_api._get_whatsapp_document(messages[message_type]['id'])
                if not filename:
                    extension = mimetypes.guess_extension(mime_type) or ''
                    filename = message_type + extension
                kwargs['attachments'] = [(filename, datas)]
                if caption:
                    kwargs['body'] = plaintext2html(caption)
            elif message_type == 'location':
                url = Markup("https://maps.google.com/maps?q={latitude},{longitude}").format(
                    latitude=messages['location']['latitude'], longitude=messages['location']['longitude'])
                body = Markup('<a target="_blank" href="{url}"> <i class="fa fa-map-marker"/> {location_string} </a>').format(
                    url=url, location_string=_("Location"))
                if messages['location'].get('name'):
                    body += Markup("<br/>{location_name}").format(location_name=messages['location']['name'])
                if messages['location'].get('address'):
                    body += Markup("<br/>{location_address}").format(location_name=messages['location']['address'])
                kwargs['body'] = body
            elif message_type == 'contacts':
                body = ""
                for contact in messages['contacts']:
                    body += Markup("<i class='fa fa-address-book'/> {contact_name} <br/>").format(
                        contact_name=contact.get('name', {}).get('formatted_name', ''))
                    for phone in contact.get('phones'):
                        body += Markup("{phone_type}: {phone_number}<br/>").format(
                            phone_type=phone.get('type'), phone_number=phone.get('phone'))
                kwargs['body'] = body
            elif message_type == 'reaction':
                msg_uid = messages['reaction'].get('message_id')
                whatsapp_message = self.env['whatsapp.message'].sudo().search([('msg_uid', '=', msg_uid)])
                if whatsapp_message:
                    partner_id = channel.whatsapp_partner_id
                    emoji = messages['reaction'].get('emoji')
                    whatsapp_message.mail_message_id._post_whatsapp_reaction(reaction_content=emoji, partner_id=partner_id)
                    continue
            elif message_type == 'interactive':
                if messages['interactive']['type'] == 'list_reply':
                    kwargs['body'] = plaintext2html(messages['interactive']['list_reply']['title'])
                elif messages['interactive']['type'] == 'button_reply':
                    kwargs['body'] = plaintext2html(messages['interactive']['button_reply']['title'])
            else:
                _logger.warning("Unsupported whatsapp message type: %s", messages)
                continue
            channel.message_post(whatsapp_inbound_msg_uid=messages['id'], **kwargs)


class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    def _send(self, force_send_by_cron=False):
        reply_data = self.env.context.get('reply_data',{})
        if len(self) <= 1 and not force_send_by_cron:
            self._send_message(reply_data=reply_data)
        else:
            self.env.ref('whatsapp.ir_cron_send_whatsapp_queue')._trigger()

    def _send_message(self, with_commit=False, reply_data={}):
        """ Prepare json data for sending messages, attachments and templates."""
        # init api
        message_to_api = {}
        for account, messages in groupby(self, lambda msg: msg.wa_account_id):
            if not account:
                messages = self.env['whatsapp.message'].concat(*messages)
                messages.write({
                    'failure_type': 'unknown',
                    'failure_reason': 'Missing whatsapp account for message.',
                    'state': 'error',
                })
                self -= messages
                continue
            wa_api = WhatsAppApi(account)
            for message in messages:
                message_to_api[message] = wa_api

        for whatsapp_message in self:
            wa_api = message_to_api[whatsapp_message]
            whatsapp_message = whatsapp_message.with_user(whatsapp_message.create_uid)
            if whatsapp_message.state != 'outgoing':
                _logger.info("Message state in %s state so it will not sent.", whatsapp_message.state)
                continue
            msg_uid = False
            try:
                parent_message_id = False
                body = whatsapp_message.body
                if isinstance(body, markupsafe.Markup):
                    # If Body is in html format so we need to remove html tags before sending message.
                    body = body.striptags()
                number = whatsapp_message.mobile_number_formatted
                if not number:
                    raise WhatsAppError(failure_type='phone_invalid')
                if self.env['phone.blacklist'].sudo().search([('number', 'ilike', number)]):
                    raise WhatsAppError(failure_type='blacklisted')
                if whatsapp_message.wa_template_id:
                    message_type = 'template'
                    if whatsapp_message.wa_template_id.status != 'approved' or whatsapp_message.wa_template_id.quality in ('red', 'yellow'):
                        raise WhatsAppError(failure_type='template')
                    whatsapp_message.message_type = 'outbound'
                    if whatsapp_message.mail_message_id.model != whatsapp_message.wa_template_id.model:
                        raise WhatsAppError(failure_type='template')

                    RecordModel = self.env[whatsapp_message.mail_message_id.model].with_user(whatsapp_message.create_uid)
                    from_record = RecordModel.browse(whatsapp_message.mail_message_id.res_id)
                    send_vals, attachment = whatsapp_message.wa_template_id._get_send_template_vals(
                        record=from_record, free_text_json=whatsapp_message.free_text_json,
                        attachment=whatsapp_message.mail_message_id.attachment_ids)
                    if attachment:
                        # If retrying message then we need to remove previous attachment and add new attachment.
                        if whatsapp_message.mail_message_id.attachment_ids and whatsapp_message.wa_template_id.header_type == 'document' and whatsapp_message.wa_template_id.report_id:
                            whatsapp_message.mail_message_id.attachment_ids.unlink()
                        if attachment not in whatsapp_message.mail_message_id.attachment_ids:
                            whatsapp_message.mail_message_id.attachment_ids = [Command.link(attachment.id)]
                elif whatsapp_message.mail_message_id.attachment_ids:
                    attachment_vals = whatsapp_message._prepare_attachment_vals(whatsapp_message.mail_message_id.attachment_ids[0], wa_account_id=whatsapp_message.wa_account_id)
                    message_type = attachment_vals.get('type')
                    send_vals = attachment_vals.get(message_type)
                    if whatsapp_message.body:
                        send_vals['caption'] = body
                else:
                    message_type = 'text'
                    send_vals = {
                        'preview_url': True,
                        'body': body,
                    }
                # Tagging parent message id if parent message is available
                if whatsapp_message.mail_message_id and whatsapp_message.mail_message_id.parent_id:
                    parent_id = whatsapp_message.mail_message_id.parent_id.wa_message_ids
                    if parent_id:
                        parent_message_id = parent_id[0].msg_uid
                msg_uid = wa_api._send_whatsapp(number=number, message_type=message_type, send_vals=send_vals, parent_message_id=parent_message_id, reply_data=reply_data)
            except WhatsAppError as we:
                whatsapp_message._handle_error(whatsapp_error_code=we.error_code, error_message=we.error_message,
                                               failure_type=we.failure_type)
            except (UserError, ValidationError) as e:
                whatsapp_message._handle_error(failure_type='unknown', error_message=str(e))
            else:
                if not msg_uid:
                    whatsapp_message._handle_error(failure_type='unknown')
                else:
                    if message_type == 'template':
                        whatsapp_message._post_message_in_active_channel()
                    whatsapp_message.write({
                        'state': 'sent',
                        'msg_uid': msg_uid
                    })
                if with_commit:
                    self._cr.commit()