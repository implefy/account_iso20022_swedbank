# -*- coding: utf-8 -*-
# Copyright 2024-2026 Your Company
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    'name': 'ISO 20022 Swedbank',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Swedbank ISO 20022 pain.001.001.03 Credit Transfer',
    'description': """
ISO 20022 Swedbank Payment Module
=================================

This module extends Odoo's ISO 20022 payment functionality to comply with
Swedbank Sweden's Message Implementation Guide (MIG) for CustomerCreditTransferInitiation
(pain.001.001.03).

Features:
---------
* Swedbank-specific pain.001.001.03 XML generation
* XML schema validation against official Swedbank XSD
* Support for Swedish domestic payments (Bankgiro, Plusgiro, account transfers)
* Support for SEPA Credit Transfers (EUR)
* Support for international payments
* Swedbank Agreement ID validation
* Swedish character set support (å Å ä Ä ö Ö)
* Clearing system codes: SESBA (Swedish), USABA (US), CACPA (Canada)
* Service levels: NURG, SEPA, URGP, SDVA

Based on Swedbank Sweden's MIG for pain.001.001.03.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'account_batch_payment',
        'base_iban',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/account_payment_method_data.xml',
        'views/account_journal_views.xml',
        'views/res_partner_bank_views.xml',
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
