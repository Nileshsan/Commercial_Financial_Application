from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import json
import os
from .payment_analysis import PaymentPatternAnalyzer
from transactions.models import TallyTransaction
from .models import LedgerOpeningBalance

class ModelTrainingView(APIView):
    def __init__(self):
        super().__init__()
        self.data_path = os.path.join(settings.BASE_DIR, 'data')
        os.makedirs(self.data_path, exist_ok=True)

    def get_patterns_file_path(self, company_id):
        return os.path.join(self.data_path, f'payment_patterns_{company_id}.json')

    def get_expenses_file_path(self, company_id):
        return os.path.join(self.data_path, f'fixed_expenses_{company_id}.json')

    def post(self, request):
        """Start the model training process"""
        try:
            company_id = request.data.get('company_id')
            if not company_id:
                return Response({
                    'status': 'error',
                    'message': 'Company ID is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            step = request.data.get('step', 'all')
            
            if step not in ['all', 'data-loading', 'payment-patterns', 'fixed-expenses', 'cashflow-setup']:
                return Response({
                    'status': 'error',
                    'message': 'Invalid step specified'
                }, status=status.HTTP_400_BAD_REQUEST)

            analyzer = PaymentPatternAnalyzer(company_id)
            response_data = {
                'status': 'success',
                'step': step,
                'progress': 0
            }

            # Data loading and processing step
            if step in ['all', 'data-loading']:
                try:
                    # First ensure we have raw transaction data
                    transactions = TallyTransaction.objects.filter(company_id=company_id)
                    if not transactions.exists():
                        return Response({
                            'status': 'error',
                            'message': 'No transaction data found. Please sync Tally data first.'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Process and generate party balances
                    balances_generated = analyzer._generate_party_balances()
                    response_data['party_balances'] = balances_generated
                    
                    # Generate payment patterns from historical data
                    payment_patterns = analyzer.analyze_payment_patterns()
                    response_data['payment_patterns'] = len(payment_patterns)
                    
                    # Identify and store fixed expenses
                    fixed_expenses = analyzer.analyze_fixed_expenses()
                    response_data['fixed_expenses'] = len(fixed_expenses)
                    
                    response_data['progress'] = 25
                    response_data['message'] = 'Data processed successfully'
                    response_data['details'] = {
                        'transactions_processed': transactions.count(),
                        'patterns_generated': bool(payment_patterns),
                        'expenses_identified': bool(fixed_expenses),
                        'party_balances_updated': bool(balances_generated)
                    }
                except Exception as e:
                    return Response({
                        'status': 'error',
                        'message': str(e),
                        'step': 'data-loading'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Payment patterns analysis
            if step in ['all', 'payment-patterns']:
                try:
                    patterns = analyzer.analyze_payment_patterns()
                    # Convert Decimal values to float for JSON serialization
                    serializable_patterns = {}
                    for party, data in patterns.items():
                        serializable_patterns[party] = {
                            'avg_delay': float(data['avg_delay']),
                            'confidence': float(data['confidence']),
                            'std_deviation': float(data['std_deviation']),
                            'sample_size': data['sample_size']
                        }
                    
                    with open(self.get_patterns_file_path(company_id), 'w') as f:
                        json.dump(serializable_patterns, f)
                    response_data['payment_patterns'] = serializable_patterns
                    response_data['progress'] = 50
                    response_data['message'] = 'Payment patterns analyzed successfully'
                except Exception as e:
                    return Response({
                        'status': 'error',
                        'message': f'Error analyzing payment patterns: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Fixed expenses analysis
            if step in ['all', 'fixed-expenses']:
                try:
                    expenses = analyzer.analyze_fixed_expenses()
                    with open(self.get_expenses_file_path(company_id), 'w') as f:
                        json.dump(expenses, f)
                    response_data['fixed_expenses'] = expenses
                    response_data['progress'] = 75
                    response_data['message'] = 'Fixed expenses analyzed successfully'
                except Exception as e:
                    return Response({
                        'status': 'error',
                        'message': f'Error analyzing fixed expenses: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Cashflow setup and predictions
            if step in ['all', 'cashflow-setup']:
                try:
                    # Load saved patterns and expenses
                    try:
                        with open(self.get_patterns_file_path(company_id)) as f:
                            analyzer.payment_patterns = json.load(f)
                        with open(self.get_expenses_file_path(company_id)) as f:
                            analyzer.fixed_expenses = json.load(f)
                    except FileNotFoundError:
                        return Response({
                            'status': 'error',
                            'message': 'Payment patterns or fixed expenses not found. Run those steps first.'
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # Generate test predictions for 30 days
                    predictions = analyzer.predict_future_payments(days=30)
                    # Convert Decimal values to float for JSON serialization
                    serializable_predictions = []
                    for pred in predictions:
                        serializable_predictions.append({
                            'date': pred['date'].isoformat(),
                            'amount': float(pred['amount']),
                            'type': pred['type'],
                            'party': pred['party'],
                            'probability': float(pred['probability'])
                        })
                    response_data['predictions'] = serializable_predictions
                    response_data['progress'] = 100
                    response_data['message'] = 'Cashflow predictions ready'
                except Exception as e:
                    return Response({
                        'status': 'error',
                        'message': f'Error setting up cashflow predictions: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Set final success state
            response_data['status'] = 'success'
            if step == 'all':
                response_data['message'] = 'All training steps completed successfully'
                response_data['progress'] = 100
            
            return Response(response_data)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        """Check model training status"""
        try:
            company_id = request.query_params.get('company_id', 1)
            
            # Check if pattern and expense files exist
            patterns_exist = os.path.exists(self.get_patterns_file_path(company_id))
            expenses_exist = os.path.exists(self.get_expenses_file_path(company_id))

            return Response({
                'status': 'trained' if patterns_exist and expenses_exist else 'untrained',
                'patterns_available': patterns_exist,
                'expenses_available': expenses_exist
            })

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
