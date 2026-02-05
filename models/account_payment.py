# -*- coding: utf-8 -*-
# Copyright 2024-2026 Your Company
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import uuid

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    swedbank_end_to_end_id = fields.Char(
        string='End-to-End ID',
        size=35,
        help='Unique end-to-end identification for Swedbank payments.',
    )
    swedbank_instruction_id = fields.Char(
        string='Instruction ID',
        size=35,
        help='Instruction identification for Swedbank payments.',
    )
    swedbank_service_level = fields.Selection([
        ('NURG', 'NURG - Standard'),
        ('SEPA', 'SEPA - SEPA Credit Transfer'),
        ('URGP', 'URGP - Urgent'),
        ('SDVA', 'SDVA - Same Day Value'),
    ], string='Service Level',
        help='Override default service level from journal',
    )
    swedbank_category_purpose = fields.Selection([
        ('SUPP', 'SUPP - Supplier Payment'),
        ('CORT', 'CORT - Express Payment'),
        ('TREA', 'TREA - Treasury Payment'),
        ('INTC', 'INTC - Intra-Company Payment'),
    ], string='Category Purpose',
        help='Override default category purpose from journal',
    )
    swedbank_charge_bearer = fields.Selection([
        ('SHAR', 'SHAR - Shared'),
        ('SLEV', 'SLEV - Service Level'),
        ('DEBT', 'DEBT - Debtor'),
        ('CRED', 'CRED - Creditor'),
    ], string='Charge Bearer',
        help='Override default charge bearer from journal',
    )
    is_swedbank_payment = fields.Boolean(
        string='Is Swedbank Payment',
        compute='_compute_is_swedbank_payment',
    )

    @api.depends('journal_id', 'journal_id.swedbank_agreement_id')
    def _compute_is_swedbank_payment(self):
        for payment in self:
            payment.is_swedbank_payment = bool(
                payment.journal_id and payment.journal_id.swedbank_agreement_id
            )

    @api.constrains('swedbank_end_to_end_id')
    def _check_swedbank_end_to_end_id(self):
        """Validate End-to-End ID format per Swedbank requirements."""
        for payment in self:
            if payment.swedbank_end_to_end_id:
                e2e = payment.swedbank_end_to_end_id
                if e2e.startswith('/') or e2e.endswith('/'):
                    raise ValidationError(_(
                        'End-to-End ID must not start or end with "/".'
                    ))
                if '//' in e2e:
                    raise ValidationError(_(
                        'End-to-End ID must not contain "//".'
                    ))
                allowed = set(
                    'abcdefghijklmnopqrstuvwxyz'
                    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                    '0123456789'
                    '/-?:().,\'+ '
                )
                if not all(c in allowed for c in e2e):
                    raise ValidationError(_(
                        'End-to-End ID contains invalid characters.'
                    ))

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate End-to-End ID if not provided."""
        for vals in vals_list:
            if not vals.get('swedbank_end_to_end_id'):
                vals['swedbank_end_to_end_id'] = str(uuid.uuid4())[:35]
        return super().create(vals_list)
