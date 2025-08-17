-- First drop the tables if they exist
DROP TABLE IF EXISTS transactions_transactionmatching;
DROP TABLE IF EXISTS transactions_tallytransaction;
DROP TABLE IF EXISTS transactions_paymentpattern;
DROP TABLE IF EXISTS transactions_fixedexpense;
DROP TABLE IF EXISTS transactions_partybalance;

-- Create base tables first
CREATE TABLE transactions_paymentpattern (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    party_name VARCHAR(255) NOT NULL,
    avg_payment_days INT NOT NULL DEFAULT 30,
    confidence_score FLOAT NOT NULL DEFAULT 0.5,
    delay_std_deviation FLOAT NOT NULL DEFAULT 0.0,
    pattern_consistency FLOAT NOT NULL DEFAULT 1.0,
    sample_size INT NOT NULL DEFAULT 0,
    expected_payment_date DATE NULL,
    last_updated DATETIME(6) NOT NULL,
    last_analysis_date DATE NOT NULL,
    UNIQUE KEY unique_company_party (company_id, party_name),
    KEY idx_company_party (company_id, party_name),
    KEY idx_expected_payment_date (expected_payment_date),
    KEY idx_pattern_consistency (pattern_consistency)
);

CREATE TABLE transactions_fixedexpense (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    amount_std_deviation DECIMAL(15,2) NOT NULL DEFAULT 0,
    frequency VARCHAR(20) NOT NULL DEFAULT 'monthly',
    interval_days INT NOT NULL DEFAULT 30,
    interval_std_deviation FLOAT NOT NULL DEFAULT 0.0,
    pattern_consistency FLOAT NOT NULL DEFAULT 1.0,
    due_day INT NOT NULL,
    next_date DATE NOT NULL,
    last_paid_date DATE NULL,
    sample_size INT NOT NULL DEFAULT 0,
    is_active BOOL NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    KEY idx_company_next_date (company_id, next_date),
    KEY idx_is_active (is_active),
    KEY idx_pattern_consistency (pattern_consistency)
);

CREATE TABLE transactions_tallytransaction (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    voucher_type VARCHAR(50) NOT NULL,
    voucher_number VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    remaining_amount DECIMAL(15,2) NULL,
    party_name VARCHAR(255) NOT NULL,
    register_type VARCHAR(20) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    is_reconciled BOOL NOT NULL DEFAULT FALSE,
    UNIQUE KEY unique_company_voucher (company_id, voucher_type, voucher_number),
    KEY idx_company_party (company_id, party_name),
    KEY idx_date (date),
    KEY idx_register_type (register_type)
);

CREATE TABLE transactions_partybalance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    party_name VARCHAR(255) NOT NULL,
    current_balance DECIMAL(15,2) NOT NULL,
    last_updated DATETIME(6) NOT NULL,
    expected_payment_date DATE NULL,
    payment_probability FLOAT NOT NULL DEFAULT 0.5,
    UNIQUE KEY unique_company_party (company_id, party_name),
    KEY idx_company_party (company_id, party_name),
    KEY idx_expected_payment_date (expected_payment_date)
);

CREATE TABLE transactions_transactionmatching (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_transaction_id INT NOT NULL,
    target_transaction_id INT NOT NULL,
    matched_amount DECIMAL(15,2) NOT NULL,
    matched_at DATETIME(6) NOT NULL,
    delay_days INT NOT NULL,
    UNIQUE KEY unique_source_target (source_transaction_id, target_transaction_id),
    KEY idx_source_transaction (source_transaction_id),
    KEY idx_target_transaction (target_transaction_id),
    KEY idx_matched_at (matched_at),
    CONSTRAINT fk_source_transaction FOREIGN KEY (source_transaction_id) REFERENCES transactions_tallytransaction(id),
    CONSTRAINT fk_target_transaction FOREIGN KEY (target_transaction_id) REFERENCES transactions_tallytransaction(id)
);
