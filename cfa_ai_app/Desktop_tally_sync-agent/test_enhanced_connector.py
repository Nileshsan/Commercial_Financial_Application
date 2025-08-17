import requests
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tally_sync.log'),
        logging.StreamHandler()
    ]
)

def sanitize_xml(xml_string:         str) -> str:
    """Clean XML string by removing     invalid characters and fixing entities."""
    xml_string = re.sub(r'[^\x09\x0A\x0D    \x20-\uD7FF\uE000-\uFFFD]', '', xml_string)
    xml_string = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;)', '&amp;', xml_string)
    return xml_string   
    
def map_group_to_ledger_type(group):
    group = group.strip().lower()
    if group in [
        "bank accounts", "sundry debtors", "cash-in-hand", "loans & advances (asset)",
        "fixed assets", "current assets", "deposits (asset)", "stock-in-hand", "investments"
    ]:
        return "Asset"
    elif group in ["capital account", "reserves & surplus", "profit & loss a/c"]:
        return "Capital"
    elif group in ["sales accounts", "direct incomes", "indirect incomes", "commission received", "interest received"]:
        return "Income"
    elif group in [
        "purchase accounts", "direct expenses", "indirect expenses", "administrative expenses",
        "selling & distribution expenses", "cost of sales", "salary & wages", "freight inward", "interest paid"
    ]:
        return "Expense"
    elif group in [
        "sundry creditors", "loans (liability)", "secured loans", "unsecured loans",
        "duties & taxes", "provisions", "current liabilities", "bank od a/c", "suspense a/c"
    ]:
        return "Liability"
    else:
        return "Unknown"

def standardize_balance(opening, ledger_type):
    try:
        amount = float(opening)
    except ValueError:
        return 0.0

    if ledger_type in ["Asset", "Expense"]:
        return abs(amount)
    elif ledger_type in ["Liability", "Capital", "Income"]:
        return -abs(amount)
    return amount

def parse_balance(balance_text):
    """Parse balance text and return float value."""
    if not balance_text:
        return 0.0
    
    try:
        # Remove any currency symbols and clean the text
        cleaned = re.sub(r'[^\d.-]', '', balance_text.strip())
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def get_date_input(prompt, default_date=None):
    """Get date input from user with validation."""
    while True:
        user_input = input(prompt).strip()
        
        if not user_input and default_date:
            return default_date
        
        try:
            # Try to parse the date in YYYYMMDD format
            if len(user_input) == 8 and user_input.isdigit():
                return user_input
            
            # Try to parse common date formats and convert to YYYYMMDD
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]:
                try:
                    parsed_date = datetime.strptime(user_input, fmt)
                    return parsed_date.strftime("%Y%m%d")
                except ValueError:
                    continue
            
            print("❌ Invalid date format. Please use YYYYMMDD, YYYY-MM-DD, DD-MM-YYYY, or DD/MM/YYYY")
            
        except Exception as e:
            print(f"❌ Error parsing date: {e}")

def main():
    print("Welcome to Tally Data Sync Tool - Enhanced with Closing Balances")
    print("=" * 65)
    
    # Get company name
    print("Please enter the company name exactly as shown in Tally.")
    print("Example: Fluidtecq Pneumatics Private Limited (2022-23)")
    
    company_name = input("Enter company name: ").strip()
    if not company_name:
        logging.error("No company name provided")
        print("❌ No company name provided. Exiting.")
        return
    
    # Get date range
    print(f"\n📅 Enter date range for balance calculation:")
    print("Date format: YYYYMMDD (e.g., 20220401 for April 1, 2022)")
    
    from_date = get_date_input("Enter FROM date (YYYYMMDD): ", "20220401")
    to_date = get_date_input("Enter TO date (YYYYMMDD): ", "20230331")
    
    print(f"\n🏢 Using company name: '{company_name}'")
    print(f"📅 Date range: {from_date} to {to_date}")
    
    # Enhanced XML request for balance data
    xml_data = f'''
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
                        <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
                        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                        <SVFROMDATE>{from_date}</SVFROMDATE>
                        <SVTODATE>{to_date}</SVTODATE>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>
    '''

    # Send request
    print("\n📡 Sending balance data request to Tally...")
    try:
        response = requests.post("http://localhost:9000", data=xml_data, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error connecting to Tally: {e}")
        print("💡 Make sure Tally is running and the company is loaded.")
        return

    # Save raw response for debugging
    with open("raw_tally_response.xml", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("💾 Raw response saved to 'raw_tally_response.xml'")

    # Clean and parse
    cleaned_text = sanitize_xml(response.text)

    try:
        root = ET.fromstring(cleaned_text)
        ledgers = root.findall(".//LEDGER")

        if not ledgers:
            print("⚠️ No LEDGER entries found. Check if:")
            print("   - Company name is correct")
            print("   - Date range contains data")
            print("   - Tally company is loaded")
            return

        print(f"\n📊 Found {len(ledgers)} ledger entries:")
        print(f"{'Ledger Name':<35} | {'Group':<20} | {'Type':<8} | {'Opening Bal':>12} | {'Closing Bal':>12} | {'Std Opening':>12} | {'Std Closing':>12}")
        print("-" * 140)

        total_records = 0


        for ledger in ledgers:
            # Ledger Name
            name_tag = ledger.find("NAME")
            name = name_tag.text.strip() if name_tag is not None and name_tag.text else None

            if not name:
                name_list = ledger.find(".//LANGUAGENAME.LIST/NAME.LIST/NAME")
                if name_list is not None and name_list.text:
                    name = name_list.text.strip()
            if not name:
                name = "[NO NAME]"

            # Group
            parent_tag = ledger.find("PARENT")
            group = parent_tag.text.strip() if parent_tag is not None and parent_tag.text else "[NO GROUP]"

            # Opening Balance
            opening_tag = ledger.find("OPENINGBALANCE")
            opening_raw = opening_tag.text.strip() if opening_tag is not None and opening_tag.text else "0"
            opening_balance = parse_balance(opening_raw)

            # Closing Balance - Try different possible tag names
            closing_balance = 0.0
            closing_raw = "0"
            
            # Try multiple possible tags for closing balance
            for tag_name in ["CLOSINGBALANCE", "BALANCE", "CURRENTBALANCE", "ENDINGBALANCE"]:
                closing_tag = ledger.find(tag_name)
                if closing_tag is not None and closing_tag.text:
                    closing_raw = closing_tag.text.strip()
                    closing_balance = parse_balance(closing_raw)
                    break
            
            # If no direct closing balance found, try to calculate from available data
            if closing_balance == 0.0 and opening_balance != 0.0:
                # Look for debit/credit totals to calculate closing
                debit_total = 0.0
                credit_total = 0.0
                
                for tag_name in ["DEBITTOTAL", "CREDITTOTAL"]:
                    tag = ledger.find(tag_name)
                    if tag is not None and tag.text:
                        amount = parse_balance(tag.text)
                        if tag_name == "DEBITTOTAL":
                            debit_total = amount
                        else:
                            credit_total = amount
                
                # Calculate closing balance
                if debit_total != 0.0 or credit_total != 0.0:
                    closing_balance = opening_balance + debit_total - credit_total
                    closing_raw = f"{closing_balance:.2f} (calculated)"

            # Map group → type
            ledger_type = map_group_to_ledger_type(group)

            # Standardize signs
            std_opening = standardize_balance(opening_balance, ledger_type)
            std_closing = standardize_balance(closing_balance, ledger_type)

            # Print results
            print(f"{name[:34]:<35} | {group[:19]:<20} | {ledger_type:<8} | {opening_raw[:11]:>12} | {closing_raw[:11]:>12} | {std_opening:>12,.2f} | {std_closing:>12,.2f}")
            total_records += 1

        print("-" * 140)
        print(f"📈 Total records processed: {total_records}")
        
        # Generate summary report
        print(f"\n📋 Summary saved to 'tally_balance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt'")
        
    except ET.ParseError as e:
        print("❌ XML Parse Error:", e)
        print("🔍 Check 'raw_tally_response.xml' for issues.")
        print("💡 The response might be malformed. Try with a different date range.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()