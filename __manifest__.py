# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This module copyright (C) 2024 PT.Thinq Technology Milik Bersama
#    (<http://www.thinq-tech.id>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Thinq x Whatsapp',
    'version': '17.0.0.1.0',
    'author': "thinq-tech",
    'website': 'https://www.thinq-tech.id',
    'license': 'AGPL-3',
    'category': 'Customization',
    'summary': 'Base Module for EJIP',
    'support': 'thinqindonesia@gmail.com',
    'depends': [
        'base',
        'mail',
        'whatsapp', 'account'
    ],
    'description': """    
This module aims to manage :
================================================================
* Department
* Document Signatures
* etc.

""",
    'demo': [],
    'test': [],
    'data': [
        'data/whatsapp_chatbot_config.xml',
        'security/ir.model.access.csv',
        'views/res_company.xml',
        'views/whatsapp_chatbot_config.xml',
        # 'views/ticket_types_view.xml',
     ],
    'css': [],
    'js': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
