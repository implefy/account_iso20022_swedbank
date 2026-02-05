# Swedbank ISO 20022 Payment Module for Odoo 19

Odoo 19 module implementing Swedbank Sweden's MIG for ISO 20022 pain.001.001.03 Credit Transfers.

## Features

- Swedbank-compliant pain.001.001.03 XML generation
- XML schema validation against official Swedbank XSD
- Swedish domestic payments (Bankgiro, Plusgiro, BBAN)
- SEPA Credit Transfers (EUR)
- Agreement ID validation (format: nnnnnnnnnnnnAnnn)
- Swedish character set support (å Å ä Ä ö Ö)
- Service levels: NURG, SEPA, URGP, SDVA

## Installation

### Option 1: Add to addons_path

```bash
git clone https://github.com/implefy/account_iso20022_swedbank.git
```

Add the cloned directory to your `odoo.conf`:
```ini
addons_path = /path/to/odoo/addons,/path/to/account_iso20022_swedbank
```

### Option 2: Symlink to addons

```bash
cd /path/to/odoo/addons
git clone https://github.com/implefy/account_iso20022_swedbank.git /opt/custom_addons/account_iso20022_swedbank
ln -s /opt/custom_addons/account_iso20022_swedbank/account_iso20022_swedbank .
```

Then restart Odoo and install "ISO 20022 Swedbank" from Apps.

## Configuration

1. Go to **Accounting > Configuration > Journals**
2. Open your bank journal > **Swedbank ISO 20022** tab
3. Enter your **Swedbank Agreement ID** (format: 123456789012A001)
4. Set default service level and charge bearer

## License

LGPL-3.0
