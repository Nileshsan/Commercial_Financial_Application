# Tally Data Extraction Guide for CFA AI System

## Overview

This guide explains how to extract the specific client transaction data required for CFA calculations and features. The data includes:

1. **Transaction details of all clients** (Sundry Debtors/Creditors)
2. **Transaction history** with dates, names, amounts
3. **Opening balances** of clients
4. **CR/DR information** for proper accounting analysis

## Required Data Structure

### Client Information
- Client Name
- Client Group (Sundry Debtors/Sundry Creditors)
- Opening Balance
- Opening Balance Type (DR/CR)
- Closing Balance
- Closing Balance Type (DR/CR)

### Transaction Details
- Transaction Date
- Voucher Type (Sales, Purchase, Receipt, Payment, Journal)
- Voucher Number
- Amount
- Debit Amount
- Credit Amount
- Running Balance
- Balance Type (DR/CR)
- Narration/Description

## Methods to Extract Data

### Method 1: Using Enhanced Tally Connector (Recommended)

The `enhanced_tally_connector.py` provides specialized functions for extracting client data:

#### Key Functions:

1. **`fetch_client_ledgers()`**
   - Extracts all client ledgers (Sundry Debtors/Creditors)
   - Returns opening and closing balances with DR/CR types

2. **`fetch_specific_client_ledger(client_name, start_date, end_date)`**
   - Gets detailed ledger for a specific client
   - Includes all transactions with running balances

3. **`fetch_comprehensive_client_data(start_date, end_date)`**
   - Comprehensive data extraction for all clients
   - Combines ledger info with transaction details

#### Usage Example:
```python
from enhanced_tally_connector import fetch_comprehensive_client_data

# Fetch data for the last 3 months
data = fetch_comprehensive_client_data("20241001", "20250131")

# Export to JSON
import json
with open('client_data.json', 'w') as f:
    json.dump(data, f, indent=2)
```

### Method 2: Using TDL Files

The `CFA_Client_Export.tdl` file provides a specialized TDL for data extraction:

#### Installation:
1. Copy `CFA_Client_Export.tdl` to Tally's TDL folder
2. Restart Tally
3. Access via Gateway of Tally → CFA Client Export

#### Data Structure:
```xml
<CFACLIENTDATA>
    <COMPANYINFO>
        <COMPANYNAME>Your Company Name</COMPANYNAME>
        <FINANCIALYEARFROM>2024-04-01</FINANCIALYEARFROM>
        <FINANCIALYEARTO>2025-03-31</FINANCIALYEARTO>
        <EXPORTDATE>2025-01-15</EXPORTDATE>
        <EXPORTTIME>14:30:25</EXPORTTIME>
        <DATEFROM>2024-10-01</DATEFROM>
        <DATETO>2025-01-31</DATETO>
    </COMPANYINFO>
    <CLIENTS>
        <CLIENT>
            <CLIENTNAME>ABC Company Ltd</CLIENTNAME>
            <CLIENTGROUP>Sundry Debtors</CLIENTGROUP>
            <OPENINGBALANCE>50000.00</OPENINGBALANCE>
            <OPENINGBALANCETYPE>DR</OPENINGBALANCETYPE>
            <CLOSINGBALANCE>75000.00</CLOSINGBALANCE>
            <CLOSINGBALANCETYPE>DR</CLOSINGBALANCETYPE>
            <TRANSACTIONS>
                <TRANSACTION>
                    <TRANSACTIONDATE>2024-10-15</TRANSACTIONDATE>
                    <VOUCHERTYPE>Sales</VOUCHERTYPE>
                    <VOUCHERNUMBER>1</VOUCHERNUMBER>
                    <AMOUNT>25000.00</AMOUNT>
                    <DEBITAMOUNT>25000.00</DEBITAMOUNT>
                    <CREDITAMOUNT>0.00</CREDITAMOUNT>
                    <BALANCE>75000.00</BALANCE>
                    <BALANCETYPE>DR</BALANCETYPE>
                    <NARRATION>Sale of goods</NARRATION>
                </TRANSACTION>
            </TRANSACTIONS>
        </CLIENT>
    </CLIENTS>
</CFACLIENTDATA>
```

### Method 3: Direct XML Requests

For advanced users, direct XML requests can be sent to Tally:

#### Ledger List Request:
```xml
<ENVELOPE>
    <HEADER>
        <TALLYREQUEST>Export Data</TALLYREQUEST>
    </HEADER>
    <BODY>
        <EXPORTDATA>
            <REQUESTDESC>
                <REPORTNAME>List of Accounts</REPORTNAME>
                <STATICVARIABLES>
                    <ACCOUNTTYPE>Ledger</ACCOUNTTYPE>
                </STATICVARIABLES>
            </REQUESTDESC>
        </EXPORTDATA>
    </BODY>
</ENVELOPE>
```

#### Specific Ledger Request:
```xml
<ENVELOPE>
    <HEADER>
        <TALLYREQUEST>Export Data</TALLYREQUEST>
    </HEADER>
    <BODY>
        <EXPORTDATA>
            <REQUESTDESC>
                <REPORTNAME>Ledger</REPORTNAME>
                <STATICVARIABLES>
                    <SVFROMDATE>20241001</SVFROMDATE>
                    <SVTODATE>20250131</SVTODATE>
                    <SVLEDGERNAME>Client Name</SVLEDGERNAME>
                    <EXPLODEFLAG>Yes</EXPLODEFLAG>
                </STATICVARIABLES>
            </REQUESTDESC>
        </EXPORTDATA>
    </BODY>
</ENVELOPE>
```

## Data Processing for CFA Features

### 1. Opening Balance Analysis
```python
def analyze_opening_balances(client_data):
    for client in client_data['clients']:
        ledger_info = client['ledger_info']
        opening_balance = float(ledger_info['opening_balance'])
        opening_type = ledger_info['opening_balance_type']
        
        # Convert to standard format
        if opening_type == 'DR':
            opening_balance = opening_balance
        else:
            opening_balance = -opening_balance
            
        return opening_balance
```

### 2. Transaction History Processing
```python
def process_transactions(client_data):
    for client in client_data['clients']:
        detailed_ledger = client['detailed_ledger']
        
        for transaction in detailed_ledger['transactions']:
            # Process each transaction
            date = transaction['date']
            amount = float(transaction['amount'])
            debit = float(transaction['debit_amount'])
            credit = float(transaction['credit_amount'])
            balance = float(transaction['balance'])
            balance_type = transaction['balance_type']
            
            # Calculate net amount
            net_amount = debit - credit
```

### 3. CR/DR Analysis
```python
def analyze_balance_types(client_data):
    for client in client_data['clients']:
        detailed_ledger = client['detailed_ledger']
        
        # Opening balance analysis
        opening_balance = float(detailed_ledger['opening_balance'])
        opening_type = detailed_ledger['opening_balance_type']
        
        # Closing balance analysis
        closing_balance = float(detailed_ledger['closing_balance'])
        closing_type = detailed_ledger['closing_balance_type']
        
        # Determine if client owes money (DR) or is owed money (CR)
        if opening_type == 'DR':
            # Client owes money
            client_status = "Debtor"
        else:
            # Client is owed money
            client_status = "Creditor"
```

## Tally Configuration Requirements

### 1. Tally Server Setup
- Enable Tally Server (Gateway of Tally → Control Centre → Data Export)
- Set port to 9000 (default)
- Configure IP address if accessing remotely

### 2. Company Selection
- Ensure correct company is selected in Tally
- Verify financial year settings
- Check that all required ledgers are created

### 3. Ledger Structure
- Sundry Debtors group should contain all debtor ledgers
- Sundry Creditors group should contain all creditor ledgers
- Ensure proper naming conventions for easy identification

## Error Handling and Troubleshooting

### Common Issues:

1. **Connection Failed**
   - Check if Tally Server is running
   - Verify port 9000 is accessible
   - Check firewall settings

2. **No Data Returned**
   - Verify company selection in Tally
   - Check date range validity
   - Ensure ledgers exist in specified groups

3. **Invalid XML Response**
   - Check Tally version compatibility
   - Verify TDL file syntax
   - Review network connectivity

### Debug Steps:
```python
# Test basic connection
from enhanced_tally_connector import test_enhanced_connector
test_enhanced_connector()

# Check specific client
from enhanced_tally_connector import fetch_specific_client_ledger
client_data = fetch_specific_client_ledger("Client Name", "20241001", "20250131")
```

## Data Export Formats

### JSON Format (Recommended)
```json
{
  "company_name": "Your Company",
  "export_date": "2025-01-15",
  "export_time": "14:30:25",
  "date_range": {
    "from_date": "20241001",
    "to_date": "20250131"
  },
  "clients": [
    {
      "ledger_info": {
        "name": "ABC Company Ltd",
        "parent": "Sundry Debtors",
        "opening_balance": "50000.00",
        "opening_balance_type": "DR",
        "closing_balance": "75000.00",
        "closing_balance_type": "DR"
      },
      "detailed_ledger": {
        "client_name": "ABC Company Ltd",
        "opening_balance": "50000.00",
        "opening_balance_type": "DR",
        "closing_balance": "75000.00",
        "closing_balance_type": "DR",
        "transactions": [
          {
            "date": "2024-10-15",
            "voucher_type": "Sales",
            "voucher_number": "1",
            "amount": "25000.00",
            "debit_amount": "25000.00",
            "credit_amount": "0.00",
            "balance": "75000.00",
            "balance_type": "DR",
            "narration": "Sale of goods"
          }
        ]
      }
    }
  ]
}
```

### CSV Format (Alternative)
```csv
ClientName,ClientGroup,OpeningBalance,OpeningType,ClosingBalance,ClosingType,TransactionDate,VoucherType,Amount,DebitAmount,CreditAmount,Balance,BalanceType,Narration
ABC Company Ltd,Sundry Debtors,50000.00,DR,75000.00,DR,2024-10-15,Sales,25000.00,25000.00,0.00,75000.00,DR,Sale of goods
```

## Integration with CFA AI System

### 1. Data Import
```python
def import_client_data(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Process for CFA calculations
    for client in data['clients']:
        process_client_for_cfa(client)
```

### 2. Real-time Sync
```python
def sync_client_data():
    # Fetch latest data
    data = fetch_comprehensive_client_data()
    
    # Update CFA database
    update_cfa_database(data)
    
    # Trigger AI analysis
    trigger_ai_analysis(data)
```

### 3. Automated Scheduling
```python
import schedule
import time

def scheduled_sync():
    data = fetch_comprehensive_client_data()
    export_client_data_to_json(data)

# Schedule daily sync at 6 PM
schedule.every().day.at("18:00").do(scheduled_sync)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Best Practices

1. **Regular Data Extraction**: Extract data daily or weekly for accurate analysis
2. **Data Validation**: Always validate extracted data for completeness
3. **Backup**: Keep backups of extracted data
4. **Error Logging**: Maintain detailed logs for troubleshooting
5. **Security**: Ensure secure transmission of financial data
6. **Compliance**: Follow accounting and data protection regulations

## Support and Maintenance

- Monitor Tally Server connectivity
- Update TDL files as needed
- Maintain data extraction logs
- Regular testing of extraction functions
- Backup and recovery procedures

This guide provides comprehensive information for extracting the required client transaction data from Tally for CFA AI system integration. 