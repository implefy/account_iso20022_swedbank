# ISO 20022 Swedbank Payment Module for Odoo 19

Swedbank Sweden's MIG-compliant ISO 20022 pain.001.001.03 payment module.

## Features

- Swedbank-compliant pain.001.001.03 XML generation
- XML schema validation against official Swedbank XSD
- Swedish domestic payments (Bankgiro, Plusgiro, BBAN)
- SEPA Credit Transfers (EUR)
- International payments
- Agreement ID validation (format: nnnnnnnnnnnnAnnn)
- Swedish character set support (å Å ä Ä ö Ö)

## Service Levels

| Code | Description |
|------|-------------|
| NURG | Standard (default) |
| SEPA | SEPA Credit Transfer (EUR) |
| URGP | Urgent payments |
| SDVA | Same day value |

## Swedish Clearing Codes

| Code | Description |
|------|-------------|
| 9900 | Bankgiro |
| 9960 | Plusgiro |
| nnnn | Bank clearing number |

## Installation

1. Copy to Odoo addons directory
2. Update Apps List
3. Install "ISO 20022 Swedbank"

## Configuration

1. Go to Accounting > Configuration > Journals
2. Open bank journal > Swedbank ISO 20022 tab
3. Enter Swedbank Agreement ID
4. Set default service level and charge bearer

## License

LGPL-3.0
