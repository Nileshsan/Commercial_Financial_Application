import requests
import os
import sys
import json
import datetime
import time
import random
from typing import Optional, Dict, Any, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from tkinter import messagebox
import urllib.parse


class APIConnector:
    """Enhanced API Connector for Tally data synchronization with Django backend."""

    def normalize_transactions(self):
        """Request backend to normalize and match transactions after sync."""
        url = f"{self.backend_url}/api/transactions/normalize-transactions/"
        headers = {
            'Authorization': f'Token {self.api_key}',
            'Content-Type': 'application/json'
        }
        try:
            response = self.session.post(url, headers=headers)
            if response.status_code == 200:
                self.log(f"✅ Transactions normalized successfully")
                return True
            elif response.status_code == 405:
                self.log(f"⚠️ Normalize transactions endpoint not enabled on server")
                return True  # Return true to not block sync completion
            else:
                self.log(f"❌ Failed to normalize transactions: {response.text}")
                return False
        except Exception as e:
            self.log(f"❌ Error normalizing transactions: {str(e)}")
            return False
    
    def __init__(self):
        """Initialize the API connector with configuration and session setup."""
        self._setup_logging()  # Ensure log_file is set before any log calls
        self._load_environment()
        self._setup_session()  # Set up session with proper configuration
        
    def _load_environment(self):
        """Load environment variables from config.env."""
        dotenv_path = os.path.join(os.path.dirname(__file__), 'config.env')
        load_dotenv(dotenv_path)
        
        # Required environment variables
        self.api_key = os.getenv('API_KEY')
        self.tally_url = os.getenv('TALLY_URL')
        self.backend_url = os.getenv('BACKEND_URL')
        self.company_name = os.getenv('COMPANY_NAME')
        
        if not self.api_key:
            self.log_error("API_KEY not found in config.env")
            raise ValueError("API_KEY not found in config.env")
            
    def _setup_session(self):
        """Set up a requests session with retry logic and authentication."""
        self.session = requests.Session()
        
        # Set up retry logic with increased timeouts and retries
        retry_strategy = Retry(
            total=5,  # Increased total retries
            backoff_factor=0.5,  # Reduced backoff to retry faster
            status_forcelist=[500, 502, 503, 504, 408, 429],  # Added timeout and rate limit status codes
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            raise_on_status=False  # Don't raise exceptions on status
        )
        # Optimize connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,  # Reduced pool size to prevent overwhelming the server
            pool_maxsize=20,
            pool_block=True  # Block when pool is full instead of creating new connections
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default timeouts
        self.session.timeout = (30, 90)  # (connect timeout, read timeout)
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'CFA-Tally-Sync-Agent/1.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Set up authentication header if API key exists
        if hasattr(self, 'api_key') and self.api_key:
            if not self._validate_api_key(self.api_key):
                self.log("❌ Invalid API key in config.env")
            else:
                self.session.headers.update({
                    'Authorization': f'Bearer {self.api_key.strip()}'
                })
    

    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        self.log_file = os.path.join(os.path.dirname(__file__), 'sync_log.txt')
        
        # Ensure log directory exists
        log_dir = os.path.dirname(self.log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
    
    def log(self, msg: str, suppress_terminal: bool = False, level: str = 'INFO') -> None:
        """Enhanced logging with timestamp and error handling. Optionally suppress terminal output."""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {msg}\n"
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"[LOG ERROR] Failed to write to log file: {e}")
        if not suppress_terminal:
            print(f"[API_CONNECTOR] {msg}")
            
    def log_error(self, msg: str) -> None:
        """Log error messages."""
        self.log(msg, level='ERROR')
        
    def log_info(self, msg: str) -> None:
        """Log informational messages."""
        self.log(msg, level='INFO')
    
    def _validate_api_key(self, api_key: str) -> bool:
        """Validate API key format."""
        return bool(api_key and len(api_key) > 0)
        
    # Removed _get_company_id_from_config as company ID is now handled by token authentication
    
    def _save_payload(self, data_type: str, data: Union[dict, list, str], is_json: bool = False) -> None:
        """Save a copy of the data payload for debugging purposes."""
        try:
            # Format the payload for saving (robust to non-serializable objects)
            backend_dir = os.path.join(os.path.dirname(__file__), 'file_backend')
            os.makedirs(backend_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            try:
                if isinstance(data, (dict, list)):
                    pretty_payload = json.dumps(data, indent=2, ensure_ascii=False, default=str)
                    ext = 'json'
                else:
                    # Try to JSON encode anything reasonable, fall back to str()
                    try:
                        pretty_payload = json.dumps(data, indent=2, ensure_ascii=False, default=str)
                        ext = 'json'
                    except Exception:
                        pretty_payload = str(data)
                        ext = 'txt'
            except Exception:
                try:
                    pretty_payload = str(data)
                    ext = 'txt'
                except Exception:
                    pretty_payload = '<unserializable payload>'
                    ext = 'txt'

            backend_file = os.path.join(backend_dir, f'{data_type}_payload_{timestamp}.{ext}')
            with open(backend_file, 'w', encoding='utf-8') as f:
                f.write(pretty_payload)
            self.log(f"Backup saved to: {backend_file}", suppress_terminal=True)
        except Exception as e:
            # Ensure saving payload never raises a blocking exception
            try:
                self.log(f"Failed to save {data_type} payload backup: {e}")
            except Exception:
                print(f"[API_CONNECTOR] Failed to save {data_type} payload backup and failed to log: {e}")

    def _prepare_headers(self, api_key: str, is_json: bool = False) -> dict:
        """Prepare request headers with API key and content type."""
        if not self._validate_api_key(api_key):
            return False
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'CFA-Tally-Sync-Agent/1.0'
        }
        return headers
    
    def _sanitize_voucher(self, voucher: dict) -> dict:
        """Sanitize voucher data to prevent null values and ensure data validity."""
        if not isinstance(voucher, dict):
            self.log(f"❌ Invalid voucher type: {type(voucher)}")
            return {}
            
        safe_voucher = {}
        try:
            # Log original voucher structure for debugging
            self.log(f"Processing voucher: {json.dumps(voucher)[:200]}...", suppress_terminal=True)
            
            # Remove null system lists and clean up values
            voucher = {
                k: (v.strip() if isinstance(v, str) else v)
                for k, v in voucher.items()
                if not (k.endswith('.LIST') and v is None)
            }
            
            # Get party info from voucher with enhanced logging
            party_info = self._extract_party_info(voucher)
            if not party_info.get('party_name'):
                self.log("⚠️ No party name found in voucher")
            
            # Ensure critical fields have safe values with validation
            safe_voucher['party_name'] = party_info.get('party_name') or 'Unknown Party'
            safe_voucher['party_type'] = party_info.get('party_type') or 'other'
            
            # Extract and validate amount
            amount_str = str(voucher.get('AMOUNT', '') or '0').strip().replace(',', '')
            try:
                amount = float(amount_str)
            except (ValueError, TypeError):
                amount = 0.0
            safe_voucher['amount'] = amount
            
            # Get date from voucher
            date_str = voucher.get('DATE', '')
            safe_voucher['date'] = str(date_str).strip() if date_str else ''
            
            # Get voucher type
            voucher_type = str(voucher.get('VOUCHERTYPENAME', '') or '').strip().lower()
            safe_voucher['voucher_type'] = voucher_type or 'journal'
            
            # Handle ledger entries
            ledger_entries = voucher.get('ledger_entries', [])
            if not isinstance(ledger_entries, list):
                ledger_entries = []
                
            safe_entries = []
            for entry in ledger_entries:
                if not isinstance(entry, dict):
                    continue
                    
                safe_entry = {
                    'ledger_name': str(entry.get('ledger_name', '') or '').strip() or 'Unknown Ledger',
                    'amount': float(entry.get('amount', 0) or 0),
                    'group': str(entry.get('group', '') or '').strip() or 'Uncategorized',
                    'type': str(entry.get('type', '') or '').strip() or 'other'
                }
                safe_entries.append(safe_entry)
                
            safe_voucher['ledger_entries'] = safe_entries
            
            # Other optional fields with safe defaults
            safe_voucher['narration'] = str(voucher.get('narration', '') or '').strip()
            safe_voucher['reference_no'] = str(voucher.get('reference_no', '') or '').strip()
            safe_voucher['voucher_number'] = str(voucher.get('voucher_number', '') or '').strip()
            
        except Exception as e:
            self.log(f"Error sanitizing voucher: {str(e)}")
            return {}
            
        return safe_voucher
    
    def _extract_party_info(self, voucher: dict) -> dict:
        """Extract party information from a voucher."""
        party_info = {'party_name': '', 'party_type': 'other'}
        
        # Try direct party name fields
        party_fields = ['PARTYNAME', 'PARTYLEDGERNAME', 'LEDGERNAME']
        for field in party_fields:
            if voucher.get(field):
                party_info['party_name'] = str(voucher[field]).strip()
                break
                
        # Determine party type from voucher type
        voucher_type = str(voucher.get('VOUCHERTYPENAME', '')).strip().upper()
        if voucher_type in ['SALES', 'RECEIPT']:
            party_info['party_type'] = 'customer'
        elif voucher_type in ['PURCHASE', 'PAYMENT']:
            party_info['party_type'] = 'vendor'
            
        return party_info
        
    def _prepare_payload(self, data_type: str, data: Union[dict, str, list], is_json: bool = False) -> Union[dict, bool]:
        """Validate and prepare data payload for sending to backend."""
        try:
            # Parse JSON if needed
            working_data = json.loads(data) if isinstance(data, str) and is_json else data
            
            # Log the initial data structure
            self.log(f"Initial data type: {type(working_data)}")
            self.log(f"Data structure: {json.dumps(working_data)[:200]}..." if working_data else "Empty data")
            
            if isinstance(working_data, list):
                # Validate list is not empty
                if not working_data:
                    self.log("❌ Empty voucher list received")
                    return False
                    
                # Sanitize each voucher in the list
                safe_data = []
                for idx, voucher in enumerate(working_data):
                    sanitized = self._sanitize_voucher(voucher)
                    if sanitized and all(sanitized.get(k) for k in ['party_name', 'date', 'amount']):
                        safe_data.append(sanitized)
                    else:
                        self.log(f"⚠️ Skipping invalid voucher at index {idx}")
                
                if not safe_data:
                    self.log("❌ No valid transactions found after sanitization")
                    self.log("Original data had entries but none passed validation")
                    return False
                    
                # Log summary of valid transactions
                self.log(f"✅ Prepared {len(safe_data)} valid transactions from {len(working_data)} total entries")
                return safe_data
            elif isinstance(working_data, dict):
                # Try to extract voucher list from dictionary
                vouchers = working_data.get('vouchers', []) or working_data.get('transactions', [])
                if vouchers:
                    return self._prepare_payload(data_type, vouchers, is_json=False)
                else:
                    self.log("❌ No vouchers found in dictionary data")
                    return False
            else:
                self.log(f"❌ Invalid data format - expected list or dict, got {type(working_data)}")
                return False
        except Exception as e:
            self.log(f"❌ Error preparing payload: {e}")
            return False

        if is_json:
            working_data = json.loads(data) if isinstance(data, str) else data
        else:
            working_data = data.copy() if isinstance(data, (dict, list)) else data

            # Handle opening balances
        if data_type == "opening_balances":
            if isinstance(working_data, dict):
                # Extract either the list from opening_balances key or use the whole dict if it's a list
                ob_data = working_data.get("opening_balances", []) if "opening_balances" in working_data else []
            else:
                ob_data = working_data if isinstance(working_data, list) else []

            if not ob_data:
                self.log(f"❌ Opening balances payload is empty")
                messagebox.showerror("Data Error", "Opening balances data must be a non-empty list.")
                return False

            # Validate each balance entry
            processed_balances = []
            for idx, balance in enumerate(ob_data):
                if not isinstance(balance, dict):
                    self.log(f"❌ Invalid balance format at index {idx}")
                    return False

                # Check required fields (now only ledger_name is required as we'll use raw_balance)
                if "ledger_name" not in balance:
                    self.log(f"❌ Missing required field 'ledger_name' in balance")
                    return False

                # Create a clean balance entry with only required fields
                try:
                    # Always prefer raw_balance if available
                    if "raw_balance" in balance:
                        balance_value = str(balance["raw_balance"])  # Ensure it's a string first
                        self.log(f"Using raw_balance: {balance_value} for {balance['ledger_name']}")
                    elif "opening_balance" in balance:
                        balance_value = str(balance["opening_balance"])  # Convert to string to handle float values
                        self.log(f"Using opening_balance: {balance_value} for {balance['ledger_name']}")
                    else:
                        self.log(f"❌ No balance value found for {balance['ledger_name']}")
                        return False

                    # Clean and validate the balance value
                    # First remove any commas and extra whitespace
                    clean_balance_str = str(balance_value).strip().replace(',', '')
                    
                    # Handle negative values with parentheses (e.g., "(123.45)")
                    if clean_balance_str.startswith('(') and clean_balance_str.endswith(')'):
                        clean_balance_str = '-' + clean_balance_str[1:-1]
                    
                    # Convert to float for final validation
                    try:
                        opening_balance = float(clean_balance_str)
                    except ValueError:
                        self.log(f"❌ Invalid balance format for {balance['ledger_name']}: {balance_value}")
                        return False
                    
                    # Clean up ledger name - remove any HTML entities and extra whitespace
                    ledger_name = balance["ledger_name"].strip()
                    ledger_name = ledger_name.replace('&#13;', '').replace('&#10;', '')
                    
                    # Create the balance entry with only the required fields
                    # The backend will use the company info from the API token
                    clean_balance = {
                        "ledger_name": ledger_name,
                        "opening_balance": opening_balance,
                        "raw_balance": str(balance_value),
                    }
                    
                    # Log the company names being used for this entry
                    company_base_name = self.company_name.split('(')[0].strip() if self.company_name and '(' in self.company_name else self.company_name
                    company_full_name = self.company_name if self.company_name else ""
                    self.log(f"Using company names for {ledger_name}:")
                    self.log(f"  User Company: {company_base_name}")
                    self.log(f"  Company: {company_full_name}")
                    
                    # Add group information if provided
                    if "group" in balance:
                        group_name = balance["group"].strip()
                        clean_balance["group"] = group_name  # Using 'group' as per backend model
                        self.log(f"Added group '{group_name}' for ledger {ledger_name}")
                    
                    # Log the cleaned entry for verification
                    self.log(f"Processing ledger: {ledger_name}")
                    self.log(f"Opening balance: {opening_balance}")
                    # Use computed company variables (avoid KeyError on clean_balance)
                    self.log(f"User Company: {company_base_name}")
                    self.log(f"Company: {company_full_name}")
                    if "group" in clean_balance:
                        self.log(f"Group: {clean_balance['group']}")
                except Exception as e:
                    self.log(f"❌ Error processing balance for {balance.get('ledger_name', 'unknown ledger')}: {str(e)}")
                    return False

                # Log the cleaned entry for debugging
                self.log(f"Cleaned balance entry: {json.dumps(clean_balance, indent=2)}", suppress_terminal=True)
                
                processed_balances.append(clean_balance)

                # Use the processed balances directly as the payload
            self.log("Final payload structure:")
            self.log(f"Number of opening balances: {len(processed_balances)}")
            
            # Debug log the company names being used
            if self.company_name:
                user_company_name = self.company_name.split('(')[0].strip() if '(' in self.company_name else self.company_name
                company_name = self.company_name
                self.log(f"Using company names:")
                self.log(f"  User Company: {user_company_name}")
                self.log(f"  Company: {company_name}")
            
            # Log sample entry
            if processed_balances:
                self.log("Sample opening balance:")
                self.log(json.dumps(processed_balances[0], indent=2))
            
            return processed_balances            # Handle transactions or vouchers
        elif data_type in ["transactions", "vouchers"]:
            # Extract vouchers from the data
            if isinstance(working_data, dict):
                vouchers = working_data.get("vouchers", working_data.get("accounting_vouchers", working_data))
            else:
                vouchers = working_data

            if not isinstance(vouchers, list) or not vouchers:
                self.log("❌ No valid vouchers found in payload")
                messagebox.showerror("Data Error", "No valid vouchers found in data.")
                return False

            # Validate each voucher
            processed_vouchers = []
            for idx, voucher in enumerate(vouchers):
                if not isinstance(voucher, dict):
                    self.log(f"❌ Invalid voucher format at index {idx}")
                    return False

                # Format and validate voucher
                formatted_voucher = {}
                
                # Map required fields
                field_mapping = {
                    "date": ["date", "voucher_date"],
                    "voucher_type": ["voucher_type", "type"],
                    "voucher_number": ["voucher_number", "voucher_no", "number"],
                    "party_name": ["party_name", "party"],
                    "entries": ["entries", "ledger_entries"]
                }

                # Process each field with fallbacks
                for target, sources in field_mapping.items():
                    for source in sources:
                        if source in voucher:
                            formatted_voucher[target] = voucher[source]
                            break
                    if target not in formatted_voucher and target != "party_name":  # party_name is optional
                        self.log(f"❌ Missing required field '{target}' in voucher at index {idx}")
                        return False

                # Process entries
                entries = formatted_voucher.get("entries", [])
                if not isinstance(entries, list) or not entries:
                    self.log(f"❌ Invalid or empty entries in voucher at index {idx}")
                    return False

                processed_entries = []
                for entry_idx, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        self.log(f"❌ Invalid entry format in voucher {idx}, entry {entry_idx}")
                        return False

                    # Format entry
                    formatted_entry = {}
                    entry_fields = {
                        "ledger_name": ["ledger_name", "ledger", "name"],
                        "amount": ["amount", "value"],
                        "type": ["type", "entry_type", "dr_cr"]
                    }

                    for target, sources in entry_fields.items():
                        for source in sources:
                            if source in entry:
                                formatted_entry[target] = entry[source]
                                break
                        if target not in formatted_entry:
                            self.log(f"❌ Missing required field '{target}' in entry")
                            return False

                    # Convert amount to float
                    try:
                        formatted_entry["amount"] = float(str(formatted_entry["amount"]).replace(',', ''))
                    except (ValueError, TypeError):
                        self.log(f"❌ Invalid amount in entry: {formatted_entry.get('amount')}")
                        return False

                    processed_entries.append(formatted_entry)

                formatted_voucher["entries"] = processed_entries
                processed_vouchers.append(formatted_voucher)

            return {"vouchers": processed_vouchers}
    
    def _handle_response(self, response: requests.Response, data_type: str) -> bool:
        """Handle API response with detailed error reporting."""
        try:
            # Log response details
            self.log(f"Backend response: status={response.status_code}, "
                    f"headers={dict(response.headers)}, text={response.text[:200]}")
            
            if response.status_code in (200, 201):
                # Try to parse response as JSON for additional info
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict):
                        message = response_data.get('message', 'Data synced successfully')
                        self.log(f"✅ {data_type.capitalize()} sync successful: {message}")
                    else:
                        self.log(f"✅ {data_type.capitalize()} data synced successfully")
                except json.JSONDecodeError:
                    self.log(f"✅ {data_type.capitalize()} data synced successfully")
                
                return True
            
            elif response.status_code == 401:
                error_msg = "Authentication failed. Please check your API key."
                self.log(f"❌ Authentication error: {error_msg}")
                messagebox.showerror("Authentication Error", error_msg)
                return False
            
            elif response.status_code == 403:
                error_msg = "Access denied. You don't have permission to perform this action."
                self.log(f"❌ Authorization error: {error_msg}")
                messagebox.showerror("Authorization Error", error_msg)
                return False
            
            elif response.status_code == 413:
                error_msg = "Data payload too large. Please try with smaller date ranges."
                self.log(f"❌ Payload too large: {error_msg}")
                messagebox.showerror("Data Size Error", error_msg)
                return False
            
            elif response.status_code == 429:
                error_msg = "Rate limit exceeded. Please wait before retrying."
                self.log(f"❌ Rate limit error: {error_msg}")
                messagebox.showerror("Rate Limit Error", error_msg)
                return False
            
            elif 400 <= response.status_code < 500:
                # Try to extract error message from backend JSON
                try:
                    error_json = response.json()
                    error_detail = error_json.get('error', response.text)
                except Exception:
                    error_detail = response.text
                error_msg = f"Client error [{response.status_code}]: {error_detail}"
                self.log(f"❌ Client error: {error_msg}")
                messagebox.showerror("Client Error", error_msg)
                return False

            elif 500 <= response.status_code < 600:
                try:
                    error_json = response.json()
                    error_detail = error_json.get('error', response.text)
                except Exception:
                    error_detail = response.text
                error_msg = f"Server error [{response.status_code}]: {error_detail}"
                self.log(f"❌ Server error: {error_msg}")
                messagebox.showerror("Server Error", error_msg)
                return False
            
            else:
                error_msg = f"Unexpected response [{response.status_code}]: {response.text}"
                self.log(f"❌ Unexpected response: {error_msg}")
                messagebox.showerror("Unexpected Error", error_msg)
                return False
        
        except Exception as e:
            self.log(f"❌ Error handling response: {e}")
            messagebox.showerror("Response Error", f"Error processing server response: {e}")
            return False
    
    def test_backend_connection(self, api_key: str) -> bool:
        """Test connection to backend with health check endpoint."""
        if not self.backend_url:
            messagebox.showerror("Configuration Error", "Backend URL not configured.")
            self.log("❌ Backend URL not configured")
            return False
        
        if not self._validate_api_key(api_key):
            messagebox.showerror("Authentication Error", "Invalid API key.")
            return False
        
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            # Test connection using transactions endpoint since it requires auth
            test_url = f"{self.backend_url.rstrip('/')}/api/transactions/"
            
            self.log(f"Testing backend connection to: {test_url}")
            
            # Use POST with empty payload since we're just testing auth
            response = self.session.post(
                test_url,
                headers=headers,
                json={},  # Empty payload for test
                timeout=10
            )
            
            if response.status_code in (200, 201):
                self.log("✅ Backend connection test successful")
                return True
            elif response.status_code == 401:
                self.log("❌ Authentication failed - invalid token")
                messagebox.showerror("Authentication Error", "Invalid API token")
                return False
            else:
                self.log(f"❌ Backend connection test failed: {response.status_code}")
                return False
        
        except requests.exceptions.Timeout:
            self.log("❌ Backend connection test timed out")
            messagebox.showerror("Connection Error", "Backend connection test timed out.")
            return False
        
        except requests.exceptions.ConnectionError:
            self.log("❌ Backend connection test failed: Connection error")
            messagebox.showerror("Connection Error", "Cannot connect to backend server.")
            return False
        
        except Exception as e:
            self.log(f"❌ Backend connection test failed: {e}")
            messagebox.showerror("Connection Error", f"Backend connection test failed: {e}")
            return False
    
    def send_data_to_backend(self, data_type: str, data: Union[dict, str, list], is_json: bool = False, api_key: str = None) -> bool:
        """Send data to the backend with enhanced error handling and validation."""
        try:
            if not self.backend_url:
                messagebox.showerror("Configuration Error", "Backend URL not configured.")
                return False
            
            # Use instance api_key if none provided
            api_key = api_key or self.api_key
            
            if not self._validate_api_key(api_key):
                messagebox.showerror("Authentication Error", "Invalid API key.")
                return False

            # Parse data if it's JSON
            payload = json.loads(data) if is_json and isinstance(data, str) else data
            
            # Prepare headers. Prefer any Authorization already configured on the session
            # (e.g., from _setup_session), but fall back to Token auth if absent.
            session_auth = self.session.headers.get('Authorization') if hasattr(self, 'session') else None
            auth_value = session_auth if session_auth else f'Token {api_key}'
            headers = {
                'Authorization': auth_value,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'CFA-Tally-Sync-Agent/1.0'
            }
            
            # Log the API key being used (first 8 chars only)
            self.log(f"Using API key: {api_key[:8]}...")

            # Determine endpoint and format payload
            if data_type == "opening_balances":
                endpoint = f"{self.backend_url.rstrip('/')}/api/opening-balances/"
                # Initialize formatted_payload
                formatted_payload = None
                
                # Verify company name is available
                if not self.company_name:
                    self.log("❌ COMPANY_NAME not found in config.env")
                    messagebox.showerror("Configuration Error", "COMPANY_NAME must be set in config.env")
                    return False
                
                # Parse company names
                company_name = self.company_name.strip()
                user_company_name = company_name.split('(')[0].strip() if '(' in company_name else company_name
                
                self.log(f"Company names from config:")
                self.log(f"  Full company name: {company_name}")
                self.log(f"  User company name: {user_company_name}")
                
                # Log incoming payload for debugging (robust)
                try:
                    self.log(f"Raw payload type: {type(payload)}")
                    self.log(f"Raw payload content: {json.dumps(payload, indent=2, default=str)}")
                except Exception:
                    try:
                        self.log(f"Raw payload content: <unserializable payload type={type(payload)}>")
                    except Exception:
                        pass
                
                # Handle different payload formats
                if isinstance(payload, dict):
                    # Extract the list of balances
                    if "opening_balances" in payload:
                        formatted_payload = payload["opening_balances"]
                    elif "balances" in payload:
                        formatted_payload = payload["balances"]
                    elif "data" in payload:
                        formatted_payload = payload["data"]
                    else:
                        # If it's a single balance entry, wrap it
                        formatted_payload = [payload]
                elif isinstance(payload, list):
                    # Use the list directly
                    formatted_payload = payload
                else:
                    # Try to parse if it's a string
                    try:
                        parsed_data = json.loads(str(payload))
                        if isinstance(parsed_data, dict):
                            formatted_payload = parsed_data.get("opening_balances", parsed_data.get("data", [parsed_data]))
                        else:
                            formatted_payload = parsed_data
                    except json.JSONDecodeError:
                        self.log("❌ Failed to parse payload as JSON")
                        formatted_payload = []

                # If company_name is present anywhere, log it
                if isinstance(payload, dict) and "company_name" in payload:
                    self.log(f"Processing opening balances for company: {payload['company_name']}")
                
                # Validate the final payload
                if not formatted_payload or not isinstance(formatted_payload, list):
                    self.log("❌ Invalid payload format: expected a list of opening balances")
                    try:
                        self.log(f"Formatted payload type: {type(formatted_payload)}")
                        self.log(f"Formatted payload: {json.dumps(formatted_payload, indent=2, default=str)}")
                    except Exception:
                        try:
                            self.log(f"Formatted payload: <unserializable payload type={type(formatted_payload)}>")
                        except Exception:
                            pass
                    messagebox.showerror("Data Error", "Invalid payload format")
                    return False

                if len(formatted_payload) == 0:
                    self.log("❌ No opening balances found in payload")
                    messagebox.showerror("Data Error", "No opening balances found in payload")
                    return False
                
                # Log the payload structure for debugging
                self.log("Payload structure verification:")
                if isinstance(formatted_payload, list):
                    self.log(f"Number of opening balances: {len(formatted_payload)}")
                    if formatted_payload:
                        try:
                            self.log(f"Sample opening balance:")
                            self.log(json.dumps(formatted_payload[0], indent=2, default=str))
                        except Exception:
                            try:
                                self.log(f"Sample opening balance: <unserializable entry type={type(formatted_payload[0])}>")
                            except Exception:
                                pass

                # Log the final formatted payload
                self.log(f"Final payload structure:")
                if isinstance(formatted_payload, list):
                    self.log(f"Number of balances: {len(formatted_payload)}")
                    if formatted_payload:
                        try:
                            self.log(f"Sample balance entry:")
                            self.log(json.dumps(formatted_payload[0], indent=2, default=str))
                        except Exception:
                            try:
                                self.log(f"Sample balance entry: <unserializable entry type={type(formatted_payload[0])}>")
                            except Exception:
                                pass
                    
            elif data_type in ["transactions", "vouchers"]:
                endpoint = f"{self.backend_url.rstrip('/')}/api/transactions/"
                
                # Prepare the payload with proper structure
                if isinstance(payload, dict):
                    # If it's already in the correct format with a 'vouchers' key
                    if "vouchers" in payload and isinstance(payload["vouchers"], list):
                        formatted_payload = {"vouchers": payload["vouchers"]}
                    # If it's a single voucher
                    elif any(k in payload for k in ['date', 'voucher_type', 'entries']):
                        formatted_payload = {"vouchers": [payload]}
                    # If it has transactions or accounting_vouchers
                    else:
                        vouchers = (
                            payload.get("vouchers") or 
                            payload.get("accounting_vouchers") or 
                            payload.get("transactions", [])
                        )
                        if not vouchers:
                            self.log("❌ No vouchers found in payload")
                            return False
                        formatted_payload = {"vouchers": vouchers if isinstance(vouchers, list) else [vouchers]}
                elif isinstance(payload, list):
                    if not payload:
                        self.log("❌ Empty voucher list received")
                        return False
                    formatted_payload = {"vouchers": payload}
                else:
                    formatted_payload = {"vouchers": [payload]}
                    
                # Validate vouchers list
                if not formatted_payload.get("vouchers"):
                    self.log("❌ No vouchers in formatted payload")
                    return False
                
                # Log payload information
                self.log(f"Prepared {len(formatted_payload['vouchers'])} vouchers for sending")
                
                # Validate the final payload
                if not formatted_payload.get("vouchers"):
                    self.log("❌ No valid vouchers in formatted payload")
                    return False
                    
                # Log the payload structure
                self.log(f"Formatted payload structure:")
                self.log(f"Number of vouchers: {len(formatted_payload['vouchers'])}")
                if formatted_payload['vouchers']:
                    try:
                        self.log(f"Sample voucher: {json.dumps(formatted_payload['vouchers'][0], indent=2, default=str)}")
                    except Exception:
                        try:
                            self.log(f"Sample voucher: <unserializable voucher type={type(formatted_payload['vouchers'][0])}>")
                        except Exception:
                            pass
            else:
                self.log(f"❌ Unsupported data type: {data_type}")
                messagebox.showerror("Error", f"Unsupported data type: {data_type}")
                return False

            # Log request details
            self.log(f"Sending {data_type} to backend: {endpoint}")
            
            # Save payload for debugging
            self._save_payload(data_type, formatted_payload)

            # Log detailed request information for debugging
            self.log(f"Sending request to {endpoint}")
            self.log(f"Headers: {json.dumps(headers, indent=2)}")
            try:
                self.log(f"Payload length: {len(formatted_payload) if isinstance(formatted_payload, list) else 'N/A'}")
            except Exception:
                self.log("Payload length: N/A")
            try:
                self.log(f"Full Payload: {json.dumps(formatted_payload, indent=2, default=str)}")
            except Exception:
                try:
                    if isinstance(formatted_payload, dict):
                        keys = list(formatted_payload.keys())
                    else:
                        keys = 'N/A'
                    self.log(f"Full Payload: <unserializable payload type={type(formatted_payload)} keys={keys}>")
                except Exception:
                    pass
            
            if isinstance(formatted_payload, list) and len(formatted_payload) == 0:
                self.log("⚠️ Warning: Empty payload list being sent")
            elif isinstance(formatted_payload, dict) and not formatted_payload:
                self.log("⚠️ Warning: Empty payload dictionary being sent")
            
            # Process payload in chunks if necessary
            if isinstance(formatted_payload, dict) and 'vouchers' in formatted_payload:
                vouchers = formatted_payload['vouchers']
                if not vouchers:
                    self.log("❌ No vouchers found in payload")
                    return False
                
                # Use larger chunks and connection pooling for better efficiency
                max_chunk_size = 50  # Increased chunk size to reduce number of connections
                initial_delay = 5  # Increased delay to allow connections to be released
                max_retries = 3  # Reduced retries to prevent connection buildup
                # Add random jitter to prevent all connections happening at once
                jitter = random.uniform(0.1, 0.5)
                
                chunks = [vouchers[i:i + max_chunk_size] 
                         for i in range(0, len(vouchers), max_chunk_size)]
                
                if len(chunks) > 1:
                    self.log(f"Processing {len(vouchers)} vouchers in {len(chunks)} small chunks")
                else:
                    self.log(f"Processing {len(vouchers)} vouchers in single request")
                
                success_count = 0
                total_chunks = len(chunks)
                
                for i, chunk in enumerate(chunks, 1):
                    retry_count = 0
                    delay = initial_delay
                    current_chunk_size = len(chunk)
                    
                    while retry_count < max_retries:
                        try:
                            # Add delay between chunks to avoid overwhelming the server
                            if i > 1:
                                time.sleep(delay)
                            
                            self.log(f"Sending chunk {i}/{total_chunks} ({current_chunk_size} vouchers)...")
                            chunk_payload = {"vouchers": chunk}
                            
                            # Close any existing connections before making new request
                            self.session.close()
                            
                            response = self.session.post(
                                endpoint,
                                json=chunk_payload,
                                headers=headers,
                                timeout=(30, 120)  # Increased timeout
                            )

                            # If we get a 401 and the server indicates Bearer auth, retry once using Bearer
                            try:
                                www_auth = response.headers.get('WWW-Authenticate', '')
                            except Exception:
                                www_auth = ''
                            if response.status_code == 401 and 'bearer' in www_auth.lower():
                                # Only retry if we didn't already use Bearer
                                if not headers.get('Authorization', '').lower().startswith('bearer'):
                                    self.log("Received 401 with WWW-Authenticate: Bearer. Retrying with Bearer auth")
                                    headers['Authorization'] = f'Bearer {api_key}'
                                    response = self.session.post(
                                        endpoint,
                                        json=chunk_payload,
                                        headers=headers,
                                        timeout=(30, 120)
                                    )
                            
                            if response.status_code in (429, 500):
                                raise requests.exceptions.RetryError("Rate limit or server error")
                                
                            if self._handle_response(response, f"{data_type} chunk {i}/{total_chunks}"):
                                success_count += 1
                                break  # Success, move to next chunk
                            else:
                                retry_count += 1
                                delay *= 2  # Exponential backoff
                                self.log(f"Retry {retry_count} for chunk {i} after {delay}s delay")
                                if current_chunk_size > 5:  # Try even smaller chunks
                                    chunk = chunk[:current_chunk_size // 2]
                                    current_chunk_size = len(chunk)
                                    self.log("Retrying with smaller chunk size...")
                                else:
                                    break  # Chunk is too small, move to next
                                
                        except requests.exceptions.ReadTimeout:
                            self.log(f"⚠️ Timeout on chunk {i}, retrying with smaller size...")
                            if current_chunk_size > 10:
                                chunk = chunk[:current_chunk_size // 2]  # Cut chunk size in half
                                current_chunk_size = len(chunk)
                                retry_count += 1
                            else:
                                break
                                
                        except Exception as e:
                            self.log(f"❌ Error processing chunk {i}: {str(e)}")
                            retry_count += 1
                            
                    if retry_count == max_retries:
                        self.log(f"❌ Failed to process chunk {i} after {max_retries} retries")
                
                # Return True only if all chunks were processed successfully
                success = success_count == total_chunks
                self.log(f"{'✅' if success else '❌'} Processed {success_count}/{total_chunks} chunks successfully")
                return success

                # If we get a 401 and server asks for Bearer, retry once using Bearer auth
                try:
                    www_auth = response.headers.get('WWW-Authenticate', '')
                except Exception:
                    www_auth = ''
                if response.status_code == 401 and 'bearer' in www_auth.lower():
                    if not headers.get('Authorization', '').lower().startswith('bearer'):
                        self.log("Received 401 with WWW-Authenticate: Bearer. Retrying single request with Bearer auth")
                        headers['Authorization'] = f'Bearer {api_key}'
                        response = self.session.post(
                            endpoint,
                            json=formatted_payload,
                            headers=headers,
                            timeout=(30, 90)
                        )

            # Get response
            success = self._handle_response(response, data_type)
            
            # Additional validation for zero records created
            if success and response.status_code in (200, 201):
                try:
                    response_data = response.json()
                    if response_data.get('balances_created', -1) == 0:
                        self.log("⚠️ Warning: No new balances were created. Debug information:")
                        self.log(f"  Company name being used: {self.company_name}")
                        self.log(f"  Number of records in payload: {len(formatted_payload)}")
                        try:
                            self.log(f"  Sample record: {json.dumps(formatted_payload[0] if formatted_payload else {}, indent=2, default=str)}")
                        except Exception:
                            self.log("  Sample record: <unserializable>")
                        try:
                            self.log(f"  Response details: {json.dumps(response_data, indent=2, default=str)}")
                        except Exception:
                            self.log("  Response details: <unserializable>")
                        self.log("  Backend message: " + response_data.get('message', 'No message provided'))
                        
                        # Show warning to user
                        warning_msg = "The data was sent successfully, but no new records were created.\n\n"
                        warning_msg += "This could be because:\n"
                        warning_msg += "1. These records already exist in the database\n"
                        warning_msg += "2. The company name does not match exactly\n"
                        warning_msg += f"\nCompany Name Used: {self.company_name}\n"
                        warning_msg += "\nPlease check:\n"
                        warning_msg += "1. Open config.env and verify COMPANY_NAME matches exactly\n"
                        warning_msg += "2. Check sync_log.txt for detailed information"
                        
                        messagebox.showwarning("No Records Created", warning_msg)
                except Exception as e:
                    self.log(f"⚠️ Warning: Could not parse response data: {e}")
            
            return success
            
        except json.JSONDecodeError as e:
            self.log(f"❌ Failed to parse JSON data: {e}")
            messagebox.showerror("Data Error", f"Failed to parse JSON data: {e}")
            return False
            
        except requests.exceptions.ReadTimeout as e:
            self.log(f"❌ Request timed out: {e}")
            messagebox.showerror("Timeout Error", 
                               "Request timed out. The data chunk might be too large.\n"
                               "The system will automatically retry with smaller chunks.")
            # Retry with smaller chunks
            if isinstance(formatted_payload, dict) and 'vouchers' in formatted_payload:
                return self.send_data_to_backend(api_key, data_type, 
                                              {"vouchers": formatted_payload['vouchers'][:50]}, 
                                              is_json=False)
            return False
            
        except requests.exceptions.ConnectionError as e:
            self.log(f"❌ Connection error: {e}")
            messagebox.showerror("Connection Error", 
                               "Failed to connect to the server.\n"
                               "Please check your internet connection and try again.")
            return False
            
        except requests.exceptions.RequestException as e:
            self.log(f"❌ Request failed: {e}")
            messagebox.showerror("Connection Error", f"Failed to send data: {str(e)}")
            return False
            
        except Exception as e:
            self.log(f"❌ Unexpected error: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
            return False
         
    
    def close(self) -> None:
        """Close the session and cleanup resources."""
        if hasattr(self, 'session'):
            self.session.close()
            self.log("✅ API connector session closed")

# Global instance for backward compatibility
_api_connector = APIConnector()

# Backward compatibility functions

def log(msg: str) -> None:
    """Legacy logging function for backward compatibility."""
    _api_connector.log(msg)

def send_data_to_backend(api_key: str, data_type: str, data: Any, is_json: bool = False) -> bool:
    """Legacy function for backward compatibility."""
    return _api_connector.send_data_to_backend(api_key, data_type, data, is_json)

def test_backend_connection(api_key: str) -> bool:
    """Legacy function for backward compatibility."""
    return _api_connector.test_backend_connection(api_key)

# Cleanup on module exit
import atexit
atexit.register(_api_connector.close)





