# -*- coding: utf-8 -*-
# Copyright 2024-2026 Your Company
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import base64
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    is_swedbank = fields.Boolean(
        string='Swedbank Payment',
        compute='_compute_is_swedbank',
        help='Indicates if this batch uses Swedbank ISO 20022 format',
    )

    @api.depends('journal_id', 'journal_id.swedbank_agreement_id')
    def _compute_is_swedbank(self):
        for batch in self:
            batch.is_swedbank = bool(
                batch.journal_id and batch.journal_id.swedbank_agreement_id
            )

    def validate_batch(self):
        """Override to add Swedbank-specific validation."""
        for batch in self:
            if batch.is_swedbank:
                batch._swedbank_validate_batch()
        return super().validate_batch()

    def _swedbank_validate_batch(self):
        """Swedbank-specific batch validation."""
        self.ensure_one()

        if not self.journal_id.swedbank_agreement_id:
            raise UserError(_(
                'Swedbank Agreement ID is not configured on journal "%s".'
            ) % self.journal_id.name)

        if not self.journal_id.bank_account_id:
            raise UserError(_(
                'Bank account is not configured on journal "%s".'
            ) % self.journal_id.name)

        for payment in self.payment_ids:
            if not payment.partner_id:
                raise UserError(_(
                    'Payment "%s" has no partner. All Swedbank payments require a partner.'
                ) % payment.name)

            if payment.amount <= 0:
                raise UserError(_(
                    'Payment "%s" has invalid amount. Amount must be positive.'
                ) % payment.name)

            if self.journal_id.swedbank_service_level == 'SEPA':
                if payment.currency_id.name != 'EUR':
                    raise UserError(_(
                        'SEPA Credit Transfer requires EUR currency. '
                        'Payment "%s" uses %s.'
                    ) % (payment.name, payment.currency_id.name))

                if payment.partner_bank_id:
                    if payment.partner_bank_id.acc_type != 'iban':
                        raise UserError(_(
                            'SEPA Credit Transfer requires IBAN. '
                            'Partner bank account for payment "%s" is not an IBAN.'
                        ) % payment.name)

    def _generate_export_file(self):
        """Override to generate Swedbank XML if applicable."""
        self.ensure_one()

        if self.is_swedbank and self.payment_method_id.code == 'swedbank_ct':
            return self._generate_swedbank_export_file()

        return super()._generate_export_file()

    def _generate_swedbank_export_file(self):
        """Generate Swedbank ISO 20022 pain.001.001.03 export file."""
        self.ensure_one()

        xml_content = self.journal_id.create_swedbank_credit_transfer_validated(self.payment_ids)

        filename = 'swedbank_pain001_%s_%s.xml' % (
            self.journal_id.code or 'payment',
            datetime.now().strftime('%Y%m%d_%H%M%S'),
        )

        file_data = base64.b64encode(xml_content)

        return {
            'file': file_data,
            'filename': filename,
        }

    def action_download_swedbank_xml(self):
        """Action to manually download Swedbank XML file."""
        self.ensure_one()

        if not self.is_swedbank:
            raise UserError(_('This batch is not configured for Swedbank payments.'))

        result = self._generate_swedbank_export_file()

        attachment = self.env['ir.attachment'].create({
            'name': result['filename'],
            'type': 'binary',
            'datas': result['file'],
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/xml',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
