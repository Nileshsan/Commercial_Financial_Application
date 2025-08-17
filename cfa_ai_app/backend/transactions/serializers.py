from rest_framework import serializers
from .models import PartyBalance

class PartyBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartyBalance
        fields = [
            'party_name',
            'current_balance',
            'expected_payment_date',
            'payment_probability'
        ]

class PaymentSerializer(serializers.Serializer):
    date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    party = serializers.CharField()
    confidence = serializers.FloatField()

class ExpenseSerializer(serializers.Serializer):
    date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    description = serializers.CharField()

class CashflowPredictionSerializer(serializers.Serializer):
    date = serializers.DateField()
    predicted_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    min_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    max_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    receipts = PaymentSerializer(many=True)
    expenses = ExpenseSerializer(many=True)
