/**
 * Format a number as Indian Rupees
 */
export const formatCurrency = (amount: number): string => {
  if (isNaN(amount) || !isFinite(amount)) {
    return '₹0';
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

/**
 * Format a date in Indian locale
 */
export const formatDate = (date: string | Date): string => {
  if (!date) return '';
  const d = new Date(date);
  return d.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

/**
 * Format a number in Indian number format without currency symbol
 */
export const formatAmount = (amount: number): string => {
  if (isNaN(amount) || !isFinite(amount)) return '0';
  return amount.toLocaleString('en-IN');
};

// Export all formatters as named exports
export const formatters = {
  currency: formatCurrency,
  date: formatDate,
  amount: formatAmount,
} as const;

// Default export for router compatibility
export default formatters;
