import React from 'react';
import { AlertTriangle, CheckCircle, XCircle, TrendingUp, TrendingDown } from 'lucide-react';

const TokenHealthView = ({ tokenData }) => {
  if (!tokenData || tokenData.length === 0) {
    return (
      <div className="card">
        <p className="text-gray-500">No token data available</p>
      </div>
    );
  }

  const getStatusBadge = (status) => {
    if (status === 'Healthy') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-success-100 text-success-800">
          <CheckCircle className="h-3 w-3 mr-1" />
          Healthy
        </span>
      );
    } else if (status === 'Degrading') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-warning-100 text-warning-800">
          <AlertTriangle className="h-3 w-3 mr-1" />
          Degrading
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-danger-100 text-danger-800">
          <XCircle className="h-3 w-3 mr-1" />
          Critical
        </span>
      );
    }
  };

  const getScoreColor = (score) => {
    if (score >= 0.8) return 'text-success-600';
    if (score >= 0.2) return 'text-warning-600';
    return 'text-danger-600';
  };

  const getScoreColorHex = (score) => {
    if (score >= 0.8) return '#22c55e'; // success green
    if (score >= 0.2) return '#f59e0b'; // warning amber
    return '#ef4444'; // danger red
  };

  const renderSparkline = (token) => {
    if (!token.score_history || token.score_history.length < 2) {
      return (
        <div className="flex items-center justify-center h-8 text-gray-400 text-xs">
          No data
        </div>
      );
    }

    const scores = token.score_history
      .slice(-7) // Last 7 days
      .map(entry => entry.score);

    const min = Math.min(...scores);
    const max = Math.max(...scores);
    const range = max - min || 1; // Avoid division by zero
    const width = 100;
    const height = 35;

    // Calculate trend direction
    const firstScore = scores[0];
    const lastScore = scores[scores.length - 1];
    const trend = lastScore > firstScore ? 'up' : lastScore < firstScore ? 'down' : 'stable';
    const trendColor = trend === 'up' ? 'text-success-600' : trend === 'down' ? 'text-danger-600' : 'text-gray-600';

    // Get color for current score
    const lineColor = getScoreColorHex(token.survivability_score);

    // Generate SVG path
    const points = scores.map((score, index) => {
      const x = (index / (scores.length - 1 || 1)) * width;
      const y = height - ((score - min) / range) * height;
      return `${x},${y}`;
    });

    const pathData = `M ${points.join(' L ')}`;

    return (
      <div className="flex items-center space-x-2">
        <svg width={width} height={height} className="overflow-visible">
          <defs>
            <linearGradient id={`gradient-${token.token_id}`} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={lineColor} stopOpacity="0.3" />
              <stop offset="100%" stopColor={lineColor} stopOpacity="0.05" />
            </linearGradient>
          </defs>
          <path
            d={`${pathData} L ${width},${height} L 0,${height} Z`}
            fill={`url(#gradient-${token.token_id})`}
          />
          <path
            d={pathData}
            fill="none"
            stroke={lineColor}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <div className={`flex items-center ${trendColor}`}>
          {trend === 'up' && <TrendingUp className="h-3.5 w-3.5" />}
          {trend === 'down' && <TrendingDown className="h-3.5 w-3.5" />}
          {trend === 'stable' && <span className="h-2 w-2 rounded-full bg-gray-400"></span>}
        </div>
      </div>
    );
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Token Health Details</h2>
      </div>
      
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Owner
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Score
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                7-Day Trend
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Role
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {tokenData.map((token) => (
              <tr key={token.token_id} className="hover:bg-gray-50">
                <td className="px-4 py-4 whitespace-nowrap">
                  <div className="text-sm font-medium text-gray-900">{token.owner}</div>
                  <div className="text-xs text-gray-500 font-mono mt-1">#{token.token_id}</div>
                </td>
                <td className="px-4 py-4 whitespace-nowrap">
                  <div className={`text-lg font-bold ${getScoreColor(token.survivability_score)}`}>
                    {token.survivability_score.toFixed(3)}
                  </div>
                </td>
                <td className="px-4 py-4 whitespace-nowrap">
                  {getStatusBadge(token.status)}
                </td>
                <td className="px-4 py-4 whitespace-nowrap">
                  {renderSparkline(token)}
                </td>
                <td className="px-4 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-500">{token.role || 'N/A'}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TokenHealthView;

