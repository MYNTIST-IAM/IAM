import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Users, 
  Activity, 
  TrendingUp, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  RefreshCw,
  Clock
} from 'lucide-react';
import TokenHealthView from './components/TokenHealthView';
import './index.css';

function App() {
  const [tokenData, setTokenData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Read the token health data directly from the public folder
      const response = await fetch('/token_health.json');
      const data = await response.json();
      
      setTokenData(data);
      console.log(data)
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError('Failed to load token data');
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    
    // Refresh data every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const getStatusStats = () => {
    if (!tokenData) return { healthy: 0, degrading: 0, critical: 0, total: 0 };
    
    const stats = tokenData.reduce((acc, token) => {
      acc.total++;
      if (token.status === 'Healthy') acc.healthy++;
      else if (token.status === 'Degrading') acc.degrading++;
      else if (token.status === 'Critical') acc.critical++;
      return acc;
    }, { healthy: 0, degrading: 0, critical: 0, total: 0 });
    
    return stats;
  };

  const getAverageScore = () => {
    if (!tokenData || tokenData.length === 0) return 0;
    const sum = tokenData.reduce((acc, token) => acc + token.survivability_score, 0);
    return (sum / tokenData.length).toFixed(3);
  };

  const stats = getStatusStats();
  const avgScore = getAverageScore();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4 text-primary-600" />
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <XCircle className="h-8 w-8 mx-auto mb-4 text-danger-600" />
          <p className="text-danger-600 mb-4">Error loading dashboard: {error}</p>
          <button 
            onClick={fetchData}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center space-x-3">
              <Shield className="h-8 w-8 text-primary-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Survivability IAM Dashboard
                </h1>
                <p className="text-sm text-gray-500">
                  Identity and Access Management Health Monitor
                </p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              {lastUpdated && (
                <div className="flex items-center space-x-2 text-sm text-gray-500">
                  <Clock className="h-4 w-4" />
                  <span>Last updated: {lastUpdated.toLocaleTimeString()}</span>
                </div>
              )}
              <button
                onClick={fetchData}
                className="flex items-center space-x-2 px-3 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                <RefreshCw className="h-4 w-4" />
                <span>Refresh</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex flex-col gap-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* System Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="metric-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Tokens</p>
                <p className="text-3xl font-bold text-gray-900">{stats.total}</p>
              </div>
              <Users className="h-8 w-8 text-primary-600" />
            </div>
          </div>

          <div className="metric-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Average Score</p>
                <p className="text-3xl font-bold text-gray-900">{avgScore}</p>
              </div>
              <TrendingUp className="h-8 w-8 text-success-600" />
            </div>
          </div>

          <div className="metric-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Healthy</p>
                <p className="text-3xl font-bold text-success-600">{stats.healthy}</p>
              </div>
              <CheckCircle className="h-8 w-8 text-success-600" />
            </div>
          </div>

          <div className="metric-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Issues</p>
                <p className="text-3xl font-bold text-danger-600">{stats.degrading + stats.critical}</p>
              </div>
              <AlertTriangle className="h-8 w-8 text-danger-600" />
            </div>
          </div>
        </div>

        {/* Token Health Details with Sparklines */}
        <TokenHealthView tokenData={tokenData} />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <p className="text-sm text-gray-500">
              Powered by Survivability IAM System
            </p>
            <p className="text-sm text-gray-500">
              Auto-refreshes every 24 hours
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;

