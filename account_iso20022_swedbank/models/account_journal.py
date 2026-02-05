# -*- coding: utf-8 -*-
# Copyright 2024-2026 Your Company
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging
import os
import re
import uuid
from datetime import datetime
from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


# Swedbank character set for SEPA/ISO20022 messages
SWEDBANK_LATIN_CHARS = set(
    'abcdefghijklmnopqrstuvwxyz'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '0123456789'
    '/-?:().,\'+ '
)

# Additional Swedish characters allowed for domestic payments
SWEDISH_LOCAL_CHARS = set('åÅäÄöÖ')

# Character replacement map for sanitization
CHAR_REPLACEMENT_MAP = {
    'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'æ': 'ae',
    'ç': 'c', 'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
    'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
    'ñ': 'n', 'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o', 'ø': 'o',
    'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u', 'ý': 'y', 'ÿ': 'y',
    'ß': 'ss', 'œ': 'oe',
    'À': 'A', 'Á': 'A', 'Â': 'A', 'Ã': 'A', 'Ä': 'A', 'Æ': 'AE',
    'Ç': 'C', 'È': 'E', 'É': 'E', 'Ê': 'E', 'Ë': 'E',
    'Ì': 'I', 'Í': 'I', 'Î': 'I', 'Ï': 'I',
    'Ñ': 'N', 'Ò': 'O', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ö': 'O', 'Ø': 'O',
    'Ù': 'U', 'Ú': 'U', 'Û': 'U', 'Ü': 'U', 'Ý': 'Y',
    'Œ': 'OE',
}


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    swedbank_agreement_id = fields.Char(
        string='Swedbank Agreement ID',
        help='Swedbank Payment file agreement ID. '
             'Format: nnnnnnnnnnnnAnnn (e.g., 123456789123B001)',
        size=16,
    )
    swedbank_pain_version = fields.Selection([
        ('pain.001.001.03', 'pain.001.001.03 (Standard)'),
    ], string='Swedbank PAIN Version',
        default='pain.001.001.03',
        help='ISO 20022 XML format version for Swedbank payments',
    )
    swedbank_service_level = fields.Selection([
        ('NURG', 'NURG - Standard (Default)'),
        ('SEPA', 'SEPA - SEPA Credit Transfer (EUR)'),
        ('URGP', 'URGP - Urgent Payments'),
        ('SDVA', 'SDVA - Same Day Value'),
    ], string='Default Service Level',
        default='NURG',
        help='Default service level for Swedbank payments',
    )
    swedbank_category_purpose = fields.Selection([
        ('SUPP', 'SUPP - Supplier Payment (Default)'),
        ('CORT', 'CORT - Express Payment'),
        ('TREA', 'TREA - Treasury Payment'),
        ('INTC', 'INTC - Intra-Company Payment'),
    ], string='Default Category Purpose',
        default='SUPP',
        help='Default category purpose for Swedbank payments',
    )
    swedbank_charge_bearer = fields.Selection([
        ('SHAR', 'SHAR - Shared (Default for domestic)'),
        ('SLEV', 'SLEV - Service Level (Required for SEPA)'),
        ('DEBT', 'DEBT - Debtor'),
        ('CRED', 'CRED - Creditor'),
    ], string='Default Charge Bearer',
        default='SHAR',
        help='Default charge bearer for Swedbank payments',
    )

    @api.constrains('swedbank_agreement_id')
    def _check_swedbank_agreement_id(self):
        """Validate Swedbank Agreement ID format: nnnnnnnnnnnnAnnn"""
        pattern = r'^[0-9]{12}[A-Z][0-9]{3}$'
        for journal in self:
            if journal.swedbank_agreement_id:
                if not re.match(pattern, journal.swedbank_agreement_id):
                    raise ValidationError(_(
                        'Invalid Swedbank Agreement ID format. '
                        'Expected format: nnnnnnnnnnnnAnnn (e.g., 123456789123B001)'
                    ))

    def _swedbank_sanitize_text(self, text, max_length=140, allow_swedish=True):
        """Sanitize text according to Swedbank character set requirements."""
        if not text:
            return ''

        text = str(text)
        result = []
        allowed_chars = SWEDBANK_LATIN_CHARS
        if allow_swedish:
            allowed_chars = allowed_chars | SWEDISH_LOCAL_CHARS

        for char in text:
            if char in allowed_chars:
                result.append(char)
            elif char in CHAR_REPLACEMENT_MAP:
                result.append(CHAR_REPLACEMENT_MAP[char])
            elif char.lower() in CHAR_REPLACEMENT_MAP:
                replacement = CHAR_REPLACEMENT_MAP[char.lower()]
                if char.isupper():
                    replacement = replacement.upper()
                result.append(replacement)

        sanitized = ''.join(result)
        while '//' in sanitized:
            sanitized = sanitized.replace('//', '/')

        return sanitized[:max_length]

    def _swedbank_sanitize_id(self, text, max_length=35):
        """Sanitize ID fields (no leading/trailing '/', no '//', Latin only)."""
        if not text:
            return ''

        sanitized = self._swedbank_sanitize_text(text, max_length, allow_swedish=False)
        sanitized = sanitized.strip('/')
        while '//' in sanitized:
            sanitized = sanitized.replace('//', '/')

        return sanitized[:max_length]

    def create_swedbank_credit_transfer(self, payments):
        """Generate Swedbank-compliant ISO 20022 pain.001.001.03 XML."""
        self.ensure_one()

        if not self.swedbank_agreement_id:
            raise UserError(_(
                'Please configure the Swedbank Agreement ID on journal "%s".'
            ) % self.name)

        if not self.bank_account_id:
            raise UserError(_(
                'Please configure a bank account on journal "%s".'
            ) % self.name)

        self._swedbank_validate_payments(payments)

        nsmap = {
            None: 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        }

        root = etree.Element('Document', nsmap=nsmap)
        cstmr_cdt_trf_initn = etree.SubElement(root, 'CstmrCdtTrfInitn')

        grp_hdr = self._swedbank_get_grp_hdr(payments)
        cstmr_cdt_trf_initn.append(grp_hdr)

        payment_groups = self._swedbank_group_payments(payments)

        for group_key, group_payments in payment_groups.items():
            pmt_inf = self._swedbank_get_pmt_inf(group_payments, group_key)
            cstmr_cdt_trf_initn.append(pmt_inf)

        xml_declaration = b'<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_content = etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=False,
            encoding='UTF-8',
        )

        return xml_declaration + xml_content

    def _swedbank_validate_payments(self, payments):
        """Validate payments for Swedbank requirements."""
        for payment in payments:
            if not payment.partner_id:
                raise UserError(_(
                    'Payment "%s" has no partner defined.'
                ) % payment.name)

            if payment.amount <= 0:
                raise UserError(_(
                    'Payment "%s" has invalid amount. Amount must be positive.'
                ) % payment.name)

            if self.swedbank_service_level == 'SEPA' and payment.currency_id.name != 'EUR':
                raise UserError(_(
                    'SEPA Credit Transfer requires EUR currency. '
                    'Payment "%s" uses %s.'
                ) % (payment.name, payment.currency_id.name))

    def _swedbank_group_payments(self, payments):
        """Group payments by debtor account and execution date."""
        groups = {}
        for payment in payments:
            exec_date = payment.date or fields.Date.today()
            key = (self.bank_account_id.id, str(exec_date))
            if key not in groups:
                groups[key] = self.env['account.payment']
            groups[key] |= payment
        return groups

    def _swedbank_get_grp_hdr(self, payments):
        """Generate GroupHeader (GrpHdr) element."""
        grp_hdr = etree.Element('GrpHdr')

        msg_id = self._swedbank_sanitize_id(
            'MSG-%s-%s' % (self.company_id.id, datetime.now().strftime('%Y%m%d%H%M%S%f'))
        )
        etree.SubElement(grp_hdr, 'MsgId').text = msg_id
        etree.SubElement(grp_hdr, 'CreDtTm').text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        etree.SubElement(grp_hdr, 'NbOfTxs').text = str(len(payments))

        ctrl_sum = sum(payments.mapped('amount'))
        etree.SubElement(grp_hdr, 'CtrlSum').text = '%.2f' % ctrl_sum

        initg_pty = etree.SubElement(grp_hdr, 'InitgPty')
        initg_pty_id = etree.SubElement(initg_pty, 'Id')
        org_id = etree.SubElement(initg_pty_id, 'OrgId')
        othr = etree.SubElement(org_id, 'Othr')
        etree.SubElement(othr, 'Id').text = self.swedbank_agreement_id
        schme_nm = etree.SubElement(othr, 'SchmeNm')
        etree.SubElement(schme_nm, 'Cd').text = 'BANK'

        return grp_hdr

    def _swedbank_get_pmt_inf(self, payments, group_key):
        """Generate PaymentInformation (PmtInf) element."""
        pmt_inf = etree.Element('PmtInf')

        debtor_account_id, exec_date = group_key
        first_payment = payments[0]

        pmt_inf_id = self._swedbank_sanitize_id(
            'PMTINF-%s-%s' % (self.id, datetime.now().strftime('%Y%m%d%H%M%S%f'))
        )
        etree.SubElement(pmt_inf, 'PmtInfId').text = pmt_inf_id
        etree.SubElement(pmt_inf, 'PmtMtd').text = 'TRF'
        etree.SubElement(pmt_inf, 'BtchBookg').text = 'true'
        etree.SubElement(pmt_inf, 'NbOfTxs').text = str(len(payments))

        ctrl_sum = sum(payments.mapped('amount'))
        etree.SubElement(pmt_inf, 'CtrlSum').text = '%.2f' % ctrl_sum

        pmt_tp_inf = self._swedbank_get_pmt_tp_inf(first_payment)
        pmt_inf.append(pmt_tp_inf)

        etree.SubElement(pmt_inf, 'ReqdExctnDt').text = exec_date

        dbtr = self._swedbank_get_dbtr()
        pmt_inf.append(dbtr)

        dbtr_acct = self._swedbank_get_dbtr_acct()
        pmt_inf.append(dbtr_acct)

        dbtr_agt = self._swedbank_get_dbtr_agt()
        pmt_inf.append(dbtr_agt)

        charge_bearer = self.swedbank_charge_bearer or 'SHAR'
        if self.swedbank_service_level == 'SEPA':
            charge_bearer = 'SLEV'
        etree.SubElement(pmt_inf, 'ChrgBr').text = charge_bearer

        for payment in payments:
            cdt_trf_tx_inf = self._swedbank_get_cdt_trf_tx_inf(payment)
            pmt_inf.append(cdt_trf_tx_inf)

        return pmt_inf

    def _swedbank_get_pmt_tp_inf(self, payment):
        """Generate PaymentTypeInformation (PmtTpInf) element."""
        pmt_tp_inf = etree.Element('PmtTpInf')

        svc_lvl = etree.SubElement(pmt_tp_inf, 'SvcLvl')
        service_level = self.swedbank_service_level or 'NURG'
        etree.SubElement(svc_lvl, 'Cd').text = service_level

        ctgy_purp = etree.SubElement(pmt_tp_inf, 'CtgyPurp')
        category_purpose = self.swedbank_category_purpose or 'SUPP'
        etree.SubElement(ctgy_purp, 'Cd').text = category_purpose

        return pmt_tp_inf

    def _swedbank_get_dbtr(self):
        """Generate Debtor (Dbtr) element."""
        dbtr = etree.Element('Dbtr')
        company = self.company_id

        name = self._swedbank_sanitize_text(company.name, max_length=140)
        etree.SubElement(dbtr, 'Nm').text = name

        pstl_adr = etree.SubElement(dbtr, 'PstlAdr')
        if company.country_id:
            etree.SubElement(pstl_adr, 'Ctry').text = company.country_id.code
        if company.street:
            street = self._swedbank_sanitize_text(company.street, max_length=70)
            etree.SubElement(pstl_adr, 'AdrLine').text = street
        if company.city:
            city = self._swedbank_sanitize_text(company.city, max_length=35)
            etree.SubElement(pstl_adr, 'TwnNm').text = city
        if company.zip:
            zip_code = self._swedbank_sanitize_text(company.zip, max_length=16)
            etree.SubElement(pstl_adr, 'PstCd').text = zip_code

        return dbtr

    def _swedbank_get_dbtr_acct(self):
        """Generate DebtorAccount (DbtrAcct) element."""
        dbtr_acct = etree.Element('DbtrAcct')
        acct_id = etree.SubElement(dbtr_acct, 'Id')

        bank_account = self.bank_account_id

        if bank_account.acc_type == 'iban' and bank_account.acc_number:
            iban = bank_account.acc_number.replace(' ', '').upper()
            etree.SubElement(acct_id, 'IBAN').text = iban
        else:
            othr = etree.SubElement(acct_id, 'Othr')
            acc_number = (bank_account.acc_number or '').replace(' ', '').replace('-', '')
            etree.SubElement(othr, 'Id').text = acc_number

            schme_nm = etree.SubElement(othr, 'SchmeNm')
            if len(acc_number) <= 8 and acc_number.isdigit():
                etree.SubElement(schme_nm, 'Prtry').text = 'BGNR'
            else:
                etree.SubElement(schme_nm, 'Cd').text = 'BBAN'

        if bank_account.currency_id:
            etree.SubElement(dbtr_acct, 'Ccy').text = bank_account.currency_id.name
        elif self.currency_id:
            etree.SubElement(dbtr_acct, 'Ccy').text = self.currency_id.name
        else:
            etree.SubElement(dbtr_acct, 'Ccy').text = self.company_id.currency_id.name

        return dbtr_acct

    def _swedbank_get_dbtr_agt(self):
        """Generate DebtorAgent (DbtrAgt) element - Swedbank."""
        dbtr_agt = etree.Element('DbtrAgt')
        fin_instn_id = etree.SubElement(dbtr_agt, 'FinInstnId')

        etree.SubElement(fin_instn_id, 'BIC').text = 'SWEDSESS'

        pstl_adr = etree.SubElement(fin_instn_id, 'PstlAdr')
        etree.SubElement(pstl_adr, 'Ctry').text = 'SE'

        return dbtr_agt

    def _swedbank_get_cdt_trf_tx_inf(self, payment):
        """Generate CreditTransferTransactionInformation (CdtTrfTxInf) element."""
        cdt_trf_tx_inf = etree.Element('CdtTrfTxInf')

        pmt_id = etree.SubElement(cdt_trf_tx_inf, 'PmtId')

        instr_id = self._swedbank_sanitize_id(
            payment.name or 'PMT-%s' % payment.id, max_length=35
        )
        etree.SubElement(pmt_id, 'InstrId').text = instr_id

        end_to_end_id = self._swedbank_sanitize_id(
            payment.ref or payment.name or str(uuid.uuid4())[:35], max_length=35
        )
        etree.SubElement(pmt_id, 'EndToEndId').text = end_to_end_id

        amt = etree.SubElement(cdt_trf_tx_inf, 'Amt')
        instd_amt = etree.SubElement(amt, 'InstdAmt', Ccy=payment.currency_id.name)
        instd_amt.text = '%.2f' % payment.amount

        cdtr_agt = self._swedbank_get_cdtr_agt(payment)
        if cdtr_agt is not None:
            cdt_trf_tx_inf.append(cdtr_agt)

        cdtr = self._swedbank_get_cdtr(payment)
        cdt_trf_tx_inf.append(cdtr)

        cdtr_acct = self._swedbank_get_cdtr_acct(payment)
        if cdtr_acct is not None:
            cdt_trf_tx_inf.append(cdtr_acct)

        rmt_inf = self._swedbank_get_rmt_inf(payment)
        if rmt_inf is not None:
            cdt_trf_tx_inf.append(rmt_inf)

        return cdt_trf_tx_inf

    def _swedbank_get_cdtr_agt(self, payment):
        """Generate CreditorAgent (CdtrAgt) element."""
        partner_bank = payment.partner_bank_id
        if not partner_bank:
            return None

        cdtr_agt = etree.Element('CdtrAgt')
        fin_instn_id = etree.SubElement(cdtr_agt, 'FinInstnId')

        if partner_bank.bank_id and partner_bank.bank_id.bic:
            etree.SubElement(fin_instn_id, 'BIC').text = partner_bank.bank_id.bic

        clearing_system = None
        clearing_member = None

        if hasattr(partner_bank, '_get_swedbank_creditor_agent_clearing'):
            clearing_system, clearing_member = partner_bank._get_swedbank_creditor_agent_clearing()
        else:
            clearing_code = getattr(partner_bank, 'swedbank_clearing_code', None)
            account_type = getattr(partner_bank, 'swedbank_account_type', None)

            if account_type == 'bankgiro':
                clearing_system = 'SESBA'
                clearing_member = '9900'
            elif account_type == 'plusgiro':
                clearing_system = 'SESBA'
                clearing_member = '9960'
            elif clearing_code:
                clearing_system = 'SESBA'
                clearing_member = clearing_code

        if clearing_member:
            clr_sys_mmb_id = etree.SubElement(fin_instn_id, 'ClrSysMmbId')
            clr_sys_id = etree.SubElement(clr_sys_mmb_id, 'ClrSysId')
            etree.SubElement(clr_sys_id, 'Cd').text = clearing_system or 'SESBA'
            etree.SubElement(clr_sys_mmb_id, 'MmbId').text = clearing_member

        pstl_adr = etree.SubElement(fin_instn_id, 'PstlAdr')
        country = 'SE'
        if partner_bank.bank_id and partner_bank.bank_id.country:
            country = partner_bank.bank_id.country.code
        elif payment.partner_id.country_id:
            country = payment.partner_id.country_id.code
        etree.SubElement(pstl_adr, 'Ctry').text = country

        return cdtr_agt

    def _swedbank_get_cdtr(self, payment):
        """Generate Creditor (Cdtr) element."""
        cdtr = etree.Element('Cdtr')
        partner = payment.partner_id

        name = self._swedbank_sanitize_text(partner.name, max_length=70)
        etree.SubElement(cdtr, 'Nm').text = name

        pstl_adr = etree.SubElement(cdtr, 'PstlAdr')

        if partner.street:
            street = self._swedbank_sanitize_text(partner.street, max_length=35)
            etree.SubElement(pstl_adr, 'StrtNm').text = street

        if partner.zip:
            zip_code = self._swedbank_sanitize_text(partner.zip, max_length=16)
            etree.SubElement(pstl_adr, 'PstCd').text = zip_code

        if partner.city:
            city = self._swedbank_sanitize_text(partner.city, max_length=35)
            etree.SubElement(pstl_adr, 'TwnNm').text = city

        if partner.country_id:
            etree.SubElement(pstl_adr, 'Ctry').text = partner.country_id.code

        return cdtr

    def _swedbank_get_cdtr_acct(self, payment):
        """Generate CreditorAccount (CdtrAcct) element."""
        partner_bank = payment.partner_bank_id
        if not partner_bank or not partner_bank.acc_number:
            return None

        cdtr_acct = etree.Element('CdtrAcct')
        acct_id = etree.SubElement(cdtr_acct, 'Id')

        acc_number = partner_bank.acc_number.replace(' ', '').replace('-', '')

        if partner_bank.acc_type == 'iban':
            etree.SubElement(acct_id, 'IBAN').text = acc_number.upper()
        else:
            othr = etree.SubElement(acct_id, 'Othr')
            etree.SubElement(othr, 'Id').text = acc_number

            schme_nm = etree.SubElement(othr, 'SchmeNm')

            account_type = getattr(partner_bank, 'swedbank_account_type', None)
            if account_type == 'bankgiro':
                etree.SubElement(schme_nm, 'Prtry').text = 'BGNR'
            elif account_type == 'plusgiro':
                etree.SubElement(schme_nm, 'Cd').text = 'BBAN'
            else:
                etree.SubElement(schme_nm, 'Cd').text = 'BBAN'

        return cdtr_acct

    def _swedbank_get_rmt_inf(self, payment):
        """Generate RemittanceInformation (RmtInf) element."""
        communication = payment.ref or payment.memo or ''
        if not communication:
            return None

        rmt_inf = etree.Element('RmtInf')

        ustrd = self._swedbank_sanitize_text(communication, max_length=140)
        etree.SubElement(rmt_inf, 'Ustrd').text = ustrd

        return rmt_inf

    def _swedbank_get_xsd_schema(self):
        """Load the Swedbank pain.001.001.03 XSD schema for validation."""
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        xsd_path = os.path.join(module_path, 'schemas', 'pain.001.001.03.xsd')

        if not os.path.exists(xsd_path):
            _logger.warning('Swedbank XSD schema not found at %s', xsd_path)
            return None

        try:
            with open(xsd_path, 'rb') as xsd_file:
                schema_doc = etree.parse(xsd_file)
                return etree.XMLSchema(schema_doc)
        except Exception as e:
            _logger.warning('Failed to load Swedbank XSD schema: %s', str(e))
            return None

    def swedbank_validate_xml(self, xml_content):
        """Validate XML content against Swedbank pain.001.001.03 schema."""
        self.ensure_one()

        schema = self._swedbank_get_xsd_schema()
        if not schema:
            return (True, ['Schema validation skipped - XSD not available'])

        try:
            xml_doc = etree.fromstring(xml_content)
            is_valid = schema.validate(xml_doc)

            if is_valid:
                return (True, [])
            else:
                errors = [str(error) for error in schema.error_log]
                return (False, errors)

        except etree.XMLSyntaxError as e:
            return (False, [f'XML Syntax Error: {str(e)}'])

    def create_swedbank_credit_transfer_validated(self, payments):
        """Generate and validate Swedbank XML."""
        self.ensure_one()

        xml_content = self.create_swedbank_credit_transfer(payments)

        is_valid, errors = self.swedbank_validate_xml(xml_content)

        if not is_valid:
            error_msg = _('Generated XML failed Swedbank schema validation:\n')
            error_msg += '\n'.join(errors[:10])
            if len(errors) > 10:
                error_msg += _('\n... and %d more errors') % (len(errors) - 10)
            raise UserError(error_msg)

        _logger.info('Swedbank XML validated successfully for %d payments', len(payments))
        return xml_content
