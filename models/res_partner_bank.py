# -*- coding: utf-8 -*-
# Copyright 2024-2026 Your Company
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    swedbank_account_type = fields.Selection([
        ('iban', 'IBAN'),
        ('bban', 'BBAN (Swedish Account)'),
        ('bankgiro', 'Bankgiro'),
        ('plusgiro', 'Plusgiro'),
    ], string='Swedish Account Type',
        compute='_compute_swedbank_account_type',
        store=True,
        help='Account type for Swedbank payments',
    )
    swedbank_clearing_code = fields.Char(
        string='Clearing Code',
        size=5,
        help='Swedish clearing code (4-5 digits).',
    )
    swedbank_formatted_account = fields.Char(
        string='Formatted Account',
        compute='_compute_swedbank_formatted_account',
        help='Account number formatted for Swedbank XML',
    )

    @api.depends('acc_number', 'acc_type')
    def _compute_swedbank_account_type(self):
        for bank in self:
            if bank.acc_type == 'iban':
                bank.swedbank_account_type = 'iban'
            elif bank.acc_number:
                acc = bank.acc_number.replace(' ', '').replace('-', '')
                if re.match(r'^[0-9]{7,8}$', acc) and not bank.swedbank_clearing_code:
                    bank.swedbank_account_type = 'bankgiro'
                elif re.match(r'^[0-9]{1,10}$', acc) and bank.swedbank_clearing_code == '9960':
                    bank.swedbank_account_type = 'plusgiro'
                else:
                    bank.swedbank_account_type = 'bban'
            else:
                bank.swedbank_account_type = False

    @api.depends('acc_number', 'swedbank_clearing_code', 'swedbank_account_type')
    def _compute_swedbank_formatted_account(self):
        for bank in self:
            if not bank.acc_number:
                bank.swedbank_formatted_account = ''
                continue

            acc = bank.acc_number.replace(' ', '').replace('-', '')
            clearing = bank.swedbank_clearing_code or ''

            if bank.swedbank_account_type == 'iban':
                bank.swedbank_formatted_account = acc.upper()
            elif bank.swedbank_account_type == 'bankgiro':
                bank.swedbank_formatted_account = acc.zfill(8)[-8:]
            elif bank.swedbank_account_type == 'plusgiro':
                bank.swedbank_formatted_account = acc
            elif clearing.startswith('8'):
                clearing_5 = clearing.zfill(5)[:5]
                acc_padded = acc.zfill(10)[-10:]
                bank.swedbank_formatted_account = clearing_5 + acc_padded
            elif clearing.startswith('7'):
                clearing_4 = clearing[:4]
                acc_padded = acc.zfill(7)[-7:]
                bank.swedbank_formatted_account = clearing_4 + acc_padded
            else:
                bank.swedbank_formatted_account = clearing + acc

    @api.constrains('swedbank_clearing_code')
    def _check_swedbank_clearing_code(self):
        for bank in self:
            if bank.swedbank_clearing_code:
                if not re.match(r'^[0-9]{4,5}$', bank.swedbank_clearing_code):
                    raise ValidationError(_('Clearing code must be 4 or 5 digits.'))

    @api.onchange('swedbank_account_type')
    def _onchange_swedbank_account_type(self):
        if self.swedbank_account_type == 'bankgiro':
            self.swedbank_clearing_code = '9900'
        elif self.swedbank_account_type == 'plusgiro':
            self.swedbank_clearing_code = '9960'

    def _get_swedbank_creditor_agent_clearing(self):
        """Get clearing system member ID for Swedbank XML."""
        self.ensure_one()

        if self.swedbank_account_type == 'bankgiro':
            return ('SESBA', '9900')
        elif self.swedbank_account_type == 'plusgiro':
            return ('SESBA', '9960')
        elif self.swedbank_clearing_code:
            return ('SESBA', self.swedbank_clearing_code)
        else:
            return (None, None)
