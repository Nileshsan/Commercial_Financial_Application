# Quick Start Guide: Setting up CFA Tally Sync Agent

## Prerequisites
1. Make sure Tally.ERP 9 is installed and running
2. Python 3.8 or later is installed on your system

## Step 1: Install Required Files
1. Copy `CFA_Client_Export.tdl` to your Tally TDL folder (usually `C:\Users\Public\Tally.ERP9\Masters`)
2. Restart Tally to load the new TDL

## Step 2: Configure the Sync Agent
1. Open `config.env` and set the following:
   ```
   TALLY_HOST=localhost
   TALLY_PORT=9000
   API_BASE_URL=http://localhost:8000
   COMPANY_ID=1
   ```

## Step 3: Install Python Dependencies
1. Open a terminal in the Desktop_tally_sync-agent folder
2. Run: `pip install -r requirements.txt`

## Step 4: Test the Connection
1. Make sure Tally is running and company is loaded
2. Run the test script:
   ```
   python test_tally_tdl_test.py
   ```
   This will verify that the connection to Tally is working.

## Step 5: Run Initial Sync
1. Run the main sync script:
   ```
   python main.py --initial-sync
   ```
   This will:
   - Extract all client ledgers
   - Get transaction history
   - Upload data to the CFA backend

## Step 6: Verify Data
1. Check the sync logs:
   - `sync_log.txt` - Basic sync information
   - `enhanced_sync_log.txt` - Detailed sync information
2. Open the CFA mobile app and check if data is visible

## Common Issues and Solutions

### No Data Appearing in CFA
1. Check `sync_log.txt` for any errors
2. Verify Tally is running and company is loaded
3. Check if the correct company period is selected in Tally

### Connection Errors
1. Verify Tally is running
2. Check if port 9000 is not blocked by firewall
3. Make sure correct company is loaded in Tally

### Data Sync Errors
1. Check `enhanced_sync_log.txt` for detailed error messages
2. Verify company dates in Tally match expected period
3. Make sure all required masters (ledgers) are properly set up in Tally

## Support
If you encounter any issues:
1. Check the detailed logs in the `logs` folder
2. See full documentation in `TALLY_DATA_EXTRACTION_GUIDE.md`
3. Contact support with the contents of your log files
