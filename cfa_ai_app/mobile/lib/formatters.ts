const formatCurrency = (amount: number): string => {
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

const formatDate = (date: string | Date): string => {
  if (!date) return '';
  const d = new Date(date);
  return d.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

const Formatters = {
  formatCurrency,
  formatDate,
};

export { formatCurrency, formatDate };
export default Formatters;
