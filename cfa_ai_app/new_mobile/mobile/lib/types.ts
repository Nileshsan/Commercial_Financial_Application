export interface CashflowPrediction {
  date: string;
  amount: number;
  confidence: number;
}

export interface CashflowSummary {
  totalParties: number;
  totalPredictions: number;
  fixedExpenses: number;
}

export interface IPartyBalance {
  party_name: string;
  current_balance: number;
  expected_payment_date: string | null;
  payment_probability: number;
  avg_payment_days: number;
  confidence: number;
  sample_size: number;
}

export type PartyBalance = Omit<IPartyBalance, 'expected_payment_date'> & {
  expected_payment_date: string;
};

export interface APIResponse<T> {
  status: 'success' | 'error';
  data: T;
}

export interface CashflowPredictionResponse {
  data: {
    predictions: CashflowPrediction[];
    summary: CashflowSummary;
    partyBalances?: PartyBalance[];
  };
  status: 'success' | 'error';
}

export interface PartyBalancesResponse {
  party_balances: PartyBalance[];
  total_outstanding: number;
  total_parties: number;
}
