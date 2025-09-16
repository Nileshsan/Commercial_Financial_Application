# CFA AI Application - Enhanced Payment Prediction System

## Overview

The CFA AI Application is a comprehensive financial analysis and payment prediction system that helps businesses analyze their cash flow patterns, predict future payments, and manage their financial operations more effectively.

## Key Features

### 1. FIFO Payment Pattern Analysis
- **First-In-First-Out Matching**: Implements FIFO algorithm to match sales and receipts chronologically
- **Weighted Average Delays**: Calculates weighted average payment delays based on transaction amounts
- **Party-Specific Patterns**: Analyzes payment behavior for each party/ledger individually
- **Confidence Scoring**: Provides confidence scores based on data consistency and sample size

### 2. Unpaid Sales Detection
- **Automatic Detection**: Identifies sales transactions that haven't been fully paid
- **Remaining Amount Calculation**: Tracks remaining unpaid amounts for each sale
- **Payment Date Prediction**: Predicts expected payment dates based on historical patterns
- **Confidence Assessment**: Provides confidence levels for each prediction

### 3. Comprehensive Cash Flow Analysis
- **Bank Balance Integration**: Tracks and manages current bank balances
- **Future Cash Flow Projections**: Predicts cash flow for up to 90 days
- **Fixed Expense Recognition**: Identifies and tracks recurring expenses
- **Party Balance Management**: Maintains current balances for all parties

### 4. Advanced Analytics Dashboard
- **Payment Analysis Summary**: Comprehensive overview of payment patterns
- **Unpaid Sales Tracking**: Detailed view of outstanding receivables
- **Party Balance Overview**: Current balances and payment probabilities
- **Visual Charts**: Interactive charts showing cash flow predictions

## Technical Architecture

### Backend (Django)

#### Core Models
- `TallyTransaction`: Stores all transaction data from Tally
- `PaymentPattern`: Stores analyzed payment patterns for each party
- `TransactionMatching`: Tracks how sales and receipts are matched
- `PartyBalance`: Current balances for each party
- `BankBalance`: Current bank account balances

#### Key Components

##### PaymentPatternAnalyzer Class
```python
class PaymentPatternAnalyzer:
    def analyze_payment_patterns(self):
        # Implements FIFO matching algorithm
        # Calculates weighted average delays
        # Saves patterns to database
    
    def detect_unpaid_sales(self):
        # Identifies unpaid sales transactions
        # Calculates remaining amounts
    
    def predict_payment_dates(self):
        # Predicts payment dates for unpaid sales
        # Uses historical patterns for prediction
```

##### API Endpoints
- `GET /api/payment-predictions/`: Get cash flow predictions
- `GET /api/unpaid-sales/`: Get unpaid sales with predictions
- `GET /api/party-balances/`: Get current party balances
- `GET /api/payment-analysis-summary/`: Get comprehensive analysis summary
- `GET /api/bank-balance/`: Get/update bank balance

### Frontend (React Native)

#### Key Screens
- **Cashflow Screen**: Main dashboard with predictions and analysis
- **Payment Analysis**: Detailed payment pattern analysis
- **Unpaid Sales**: List of unpaid sales with predictions
- **Party Balances**: Current balances and payment probabilities

#### Components
- `PaymentPredictionChart`: Visual chart for cash flow predictions
- `BankBalanceInput`: Modal for updating bank balance
- `UnpaidSalesList`: List component for unpaid sales
- `PartyBalanceCard`: Card component for party balances

## Installation and Setup

### Prerequisites
- Python 3.8+
- Node.js 16+
- React Native development environment
- Tally ERP 9 (for data import)

### Backend Setup
1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run migrations:
   ```bash
   python manage.py migrate
   ```
5. Start the server:
   ```bash
   python manage.py runserver
   ```

### Frontend Setup
1. Navigate to mobile directory:
   ```bash
   cd mobile
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npx expo start
   ```

## Usage Guide

### 1. Initial Setup
1. **Login**: Use your credentials to access the application
2. **Company Selection**: Select your company from the dropdown
3. **Bank Balance**: Enter your current bank balance
4. **Data Import**: Import your Tally transaction data

### 2. Payment Pattern Analysis
1. **Automatic Analysis**: The system automatically analyzes payment patterns
2. **FIFO Matching**: Sales and receipts are matched using FIFO algorithm
3. **Pattern Recognition**: System identifies payment patterns for each party
4. **Confidence Scoring**: Each pattern gets a confidence score

### 3. Payment Predictions
1. **Unpaid Sales Detection**: System identifies unpaid sales automatically
2. **Date Prediction**: Predicted payment dates are calculated
3. **Confidence Levels**: Each prediction includes confidence percentage
4. **Visual Display**: Predictions are shown in charts and lists

### 4. Cash Flow Management
1. **Current Balance**: View current bank balance
2. **Future Projections**: See predicted cash flow for next 90 days
3. **Fixed Expenses**: Track recurring expenses
4. **Party Balances**: Monitor current balances for all parties

## API Documentation

### Payment Predictions
```http
GET /api/payment-predictions/?company_id=1&days=90
```
Returns cash flow predictions for the specified period.

### Unpaid Sales
```http
GET /api/unpaid-sales/?company_id=1
```
Returns list of unpaid sales with predicted payment dates.

### Party Balances
```http
GET /api/party-balances/?company_id=1
```
Returns current balances for all parties.

### Payment Analysis Summary
```http
GET /api/payment-analysis-summary/?company_id=1
```
Returns comprehensive payment analysis summary.

## Data Flow

### 1. Data Import
1. Tally transactions are imported via API
2. Data is validated and stored in database
3. Opening balances are recorded
4. Bank balances are updated

### 2. Pattern Analysis
1. Sales and receipts are sorted chronologically
2. FIFO matching algorithm is applied
3. Payment delays are calculated
4. Weighted averages are computed
5. Patterns are saved to database

### 3. Prediction Generation
1. Unpaid sales are identified
2. Historical patterns are retrieved
3. Payment dates are predicted
4. Confidence scores are calculated
5. Results are returned to frontend

### 4. Visualization
1. Data is formatted for charts
2. Predictions are displayed
3. Interactive elements are added
4. Real-time updates are provided

## Configuration

### Environment Variables
```bash
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=your-database-url

# API Settings
API_BASE_URL=http://localhost:8000
API_TIMEOUT=30000

# Tally Integration
TALLY_EXPORT_PATH=/path/to/tally/exports
```

### Database Configuration
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'cfa_db',
        'USER': 'cfa_user',
        'PASSWORD': 'cfa_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## Troubleshooting

### Common Issues

1. **Data Import Failures**
   - Check Tally export format
   - Verify file permissions
   - Ensure database connectivity

2. **Prediction Accuracy**
   - Ensure sufficient historical data
   - Check data quality
   - Verify pattern consistency

3. **Performance Issues**
   - Optimize database queries
   - Implement caching
   - Monitor server resources

### Support
For technical support, please contact:
- Email: support@cfa-ai.com
- Documentation: https://docs.cfa-ai.com
- GitHub Issues: https://github.com/cfa-ai/cfa-app/issues

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Changelog

### Version 2.0.0 (Latest)
- Enhanced FIFO payment pattern analysis
- Unpaid sales detection and prediction
- Comprehensive cash flow analysis
- Advanced analytics dashboard
- Improved API endpoints
- Better error handling
- Enhanced mobile UI

### Version 1.0.0
- Initial release
- Basic payment pattern analysis
- Simple cash flow predictions
- Mobile app foundation 