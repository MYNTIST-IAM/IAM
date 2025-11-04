import React from 'react';
import { CheckCircle, AlertTriangle, XCircle, Package, Users } from 'lucide-react';

const ProductHealthView = ({ productData }) => {
  if (!productData || productData.length === 0) {
    return (
      <div className="card">
        <p className="text-gray-500">No product data available</p>
      </div>
    );
  }

  const getStatusBadge = (status) => {
    if (status === 'Green') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-success-100 text-success-800">
          <CheckCircle className="h-3 w-3 mr-1" />
          Healthy
        </span>
      );
    } else if (status === 'Yellow') {
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

  const getHealthColor = (status) => {
    if (status === 'Green') return 'border-success-500 bg-success-50';
    if (status === 'Yellow') return 'border-warning-500 bg-warning-50';
    return 'border-danger-500 bg-danger-50';
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center">
          <Package className="h-6 w-6 mr-2 text-primary-600" />
          Product Health
        </h2>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Product
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Team
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Health Score
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Dependencies
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {productData.map((product) => (
              <tr key={product.product_id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm font-medium text-gray-900">
                    {product.product_name}
                  </div>
                  <div className="text-xs text-gray-500">{product.product_id}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900 flex items-center">
                    <Users className="h-4 w-4 mr-1 text-gray-400" />
                    {product.responsible_team}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className={`text-sm font-bold ${getScoreColor(product.survivability_health)}`}>
                    {product.survivability_health.toFixed(3)}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {getStatusBadge(product.health_status)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900">
                    {product.linked_agents_count + product.linked_tokens_count} total
                  </div>
                  <div className="text-xs text-gray-500">
                    {product.linked_agents_count} agents, {product.linked_tokens_count} tokens
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ProductHealthView;

