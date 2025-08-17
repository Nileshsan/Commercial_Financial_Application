/**
 * Format a number as Indian currency (INR)
 */
export const formatCurrency = (amount: number, compact: boolean = false): string => {
  const formatter = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
    notation: compact ? 'compact' : 'standard'
  });
  
  return formatter.format(amount);
}

/**
 * Format a number as percentage
 */
export const formatPercentage = (value: number): string => {
  return `${(value * 100).toFixed(1)}%`;
}

/**
 * Format a date to Indian format
 */
export const formatDate = (date: Date | string): string => {
  if (typeof date === 'string') {
    date = new Date(date);
  }
  return date.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  });
}

// Default export to satisfy expo-router which expects a default export from route files
const defaultExport = {
  formatCurrency,
  formatPercentage,
  formatDate,
};

export default defaultExport;
