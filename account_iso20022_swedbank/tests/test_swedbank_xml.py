# -*- coding: utf-8 -*-
from lxml import etree
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class TestSwedbankXML(TransactionCase):
    """Test cases for Swedbank ISO 20022 XML generation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env['res.company'].create({
            'name': 'Test Company AB',
            'country_id': cls.env.ref('base.se').id,
            'street': 'Testgatan 1',
            'city': 'Stockholm',
            'zip': '11122',
        })

        cls.company_bank = cls.env['res.partner.bank'].create({
            'acc_number': 'SE4550000000058398257466',
            'acc_type': 'iban',
            'partner_id': cls.company.partner_id.id,
        })

        cls.journal = cls.env['account.journal'].create({
            'name': 'Swedbank',
            'code': 'SWE',
            'type': 'bank',
            'company_id': cls.company.id,
            'bank_account_id': cls.company_bank.id,
            'swedbank_agreement_id': '123456789012A001',
            'swedbank_service_level': 'NURG',
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Supplier AB',
            'country_id': cls.env.ref('base.se').id,
            'street': 'Leverantorsgatan 5',
            'city': 'Goteborg',
            'zip': '41101',
        })

        cls.partner_bank_bg = cls.env['res.partner.bank'].create({
            'acc_number': '12345678',
            'partner_id': cls.partner.id,
            'swedbank_account_type': 'bankgiro',
            'swedbank_clearing_code': '9900',
        })

    def test_agreement_id_validation(self):
        """Test Swedbank Agreement ID format validation."""
        self.journal.swedbank_agreement_id = '123456789012B001'

        with self.assertRaises(ValidationError):
            self.journal.swedbank_agreement_id = 'invalid'

    def test_sanitize_text(self):
        """Test text sanitization for Swedbank character set."""
        result = self.journal._swedbank_sanitize_text('Foretag AB', allow_swedish=True)
        self.assertEqual(result, 'Foretag AB')

        result = self.journal._swedbank_sanitize_text('Test//Ref')
        self.assertNotIn('//', result)

    def test_xml_generation_basic(self):
        """Test basic XML generation structure."""
        payment = self.env['account.payment'].create({
            'partner_id': self.partner.id,
            'amount': 1000.00,
            'payment_type': 'outbound',
            'journal_id': self.journal.id,
            'partner_bank_id': self.partner_bank_bg.id,
            'ref': 'INV-001',
        })

        xml_content = self.journal.create_swedbank_credit_transfer(payment)
        root = etree.fromstring(xml_content)

        self.assertEqual(
            root.tag,
            '{urn:iso:std:iso:20022:tech:xsd:pain.001.001.03}Document'
        )

    def test_missing_agreement_id(self):
        """Test error when Agreement ID is missing."""
        self.journal.swedbank_agreement_id = False

        payment = self.env['account.payment'].create({
            'partner_id': self.partner.id,
            'amount': 100.00,
            'payment_type': 'outbound',
            'journal_id': self.journal.id,
        })

        with self.assertRaises(UserError):
            self.journal.create_swedbank_credit_transfer(payment)
