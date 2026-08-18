export const getTotalRevenue = () => {
  return {
    total: '2,847.23',
    growth: '+24.3%',
  }
}

export const getRevenueDetails = () => {
  return {
    total: '2,847.23',
    thisMonth: '524.80',
    lastMonth: '423.15',
    growth: '+24.3%',
    topEndpoints: [
      { name: 'Financial Analytics API', revenue: '1,142.50', percentage: 40.1 },
      { name: 'Customer Insights API', revenue: '856.75', percentage: 30.1 },
      { name: 'Marketing Data API', revenue: '523.40', percentage: 18.4 },
      { name: 'Research Dataset API', revenue: '324.58', percentage: 11.4 },
    ],
    monthlyBreakdown: [
      { month: 'Jan', revenue: 384.2 },
      { month: 'Feb', revenue: 421.5 },
      { month: 'Mar', revenue: 456.8 },
      { month: 'Apr', revenue: 423.15 },
      { month: 'May', revenue: 524.8 },
    ],
    metrics: {
      totalTransactions: '47,234',
      avgRevenuePerTransaction: '$0.060',
      paidUsers: '1,847',
      conversionRate: '23.4%',
    },
  }
}
