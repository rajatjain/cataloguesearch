import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { searchableContent, getSearchableStats, getContentByStatus } from '../utils/searchableContent.js';
import './SearchIndex.css';

const SearchIndex = () => {
  const [sortConfig, setSortConfig] = useState({ key: 'name', direction: 'asc' });
  const stats = getSearchableStats();

  // Extract year from series string for sorting
  const extractYear = (series) => {
    // Extract first year from patterns like "1978-80", "1979-80", "1966", etc.
    const yearMatch = series.match(/(\d{4})/);
    return yearMatch ? parseInt(yearMatch[1]) : 0;
  };

  // Handle sort functionality
  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  // Get combined status for an item
  const getCombinedStatus = (item) => {
    // Return the first non-null status
    return item.hindi || item.gujarati || null;
  };

  // Sort content based on sort configuration
  const sortContent = (content) => {
    return [...content].sort((a, b) => {
      let aValue, bValue;

      // For Year, Granth, and Count sorting, always prioritize status first
      if (sortConfig.key === 'name' || sortConfig.key === 'year' || sortConfig.key === 'count') {
        // First sort by status: searchable first, in_progress last
        const statusOrder = { 'searchable': 1, 'in_progress': 2, 'planned': 3 };
        const aStatus = statusOrder[getCombinedStatus(a)] || 99;
        const bStatus = statusOrder[getCombinedStatus(b)] || 99;

        if (aStatus !== bStatus) {
          return aStatus - bStatus;
        }

        // If status is the same, then sort by the requested field
        if (sortConfig.key === 'name') {
          aValue = a.granth;
          bValue = b.granth;
          const result = aValue.localeCompare(bValue);
          return sortConfig.direction === 'asc' ? result : -result;
        } else if (sortConfig.key === 'year') {
          aValue = extractYear(a.series);
          bValue = extractYear(b.series);
          const result = aValue - bValue;
          return sortConfig.direction === 'asc' ? result : -result;
        } else if (sortConfig.key === 'count') {
          aValue = a.count || 0;
          bValue = b.count || 0;
          const result = aValue - bValue;
          return sortConfig.direction === 'asc' ? result : -result;
        }
      }
      return 0;
    });
  };

  // Get sort indicator icon
  const getSortIcon = (columnKey) => {
    if (sortConfig.key !== columnKey) {
      return <span style={{ color: '#ccc', fontSize: '0.8em' }}> ⇅</span>;
    }
    const color = '#2563eb'; // Blue for active sort
    return sortConfig.direction === 'asc' ? 
      <span style={{ color, fontSize: '0.9em' }}> ▲</span> : 
      <span style={{ color, fontSize: '0.9em' }}> ▼</span>;
  };

  // Get CSS class for sort headers
  const getSortHeaderClass = (columnKey) => {
    return sortConfig.key === columnKey ? 'sortable-header active-sort' : 'sortable-header';
  };

  const getContent = () => {
    return sortContent(searchableContent);
  };

  const content = getContent();

  const renderStatusBadge = (status) => {
    if (!status) return '-';
    return (
      <span className={`status-badge ${status}`}>
        {status === 'searchable' ? '✅ Searchable' :
         status === 'in_progress' ? '🔄 In Progress' :
         '📅 Planned'}
      </span>
    );
  };

  const renderContentTable = () => {
    if (!content || content.length === 0) return null;

    return (
      <div className="content-section">
        <div className="table-container">
          <table className="content-table">
            <thead>
              <tr>
                <th
                  className={getSortHeaderClass('name')}
                  onClick={() => handleSort('name')}
                  style={{ cursor: 'pointer' }}
                >
                  Granth{getSortIcon('name')}
                </th>
                <th
                  className={getSortHeaderClass('year')}
                  onClick={() => handleSort('year')}
                  style={{ cursor: 'pointer' }}
                >
                  Year/Series{getSortIcon('year')}
                </th>
                <th
                  className={getSortHeaderClass('count')}
                  onClick={() => handleSort('count')}
                  style={{ cursor: 'pointer' }}
                >
                  Count{getSortIcon('count')}
                </th>
                <th>
                  Hindi
                </th>
                <th>
                  Gujarati
                </th>
              </tr>
            </thead>
            <tbody>
              {content.map((item, index) => (
                <tr key={`${item.granth}-${item.series}-${index}`}>
                  <td className="granth-cell">{item.granth}</td>
                  <td className="series-cell">{item.series}</td>
                  <td className="count-cell">
                    {item.count ? item.count.toLocaleString() : 'Compiled'}
                  </td>
                  <td className="status-cell">
                    {renderStatusBadge(item.hindi)}
                  </td>
                  <td className="status-cell">
                    {renderStatusBadge(item.gujarati)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="search-index-page">

      <div className="stats-overview">
        <div className="overview-card">
          <div className="overview-number">{getContentByStatus('searchable').hindi.length + getContentByStatus('searchable').gujarati.length} Series</div>
          <div className="overview-secondary">{stats.grandTotal.toLocaleString()} Pravachans</div>
        </div>
        <div className="overview-card language-split">
          <div className="language-stat">
            <div className="overview-number">{stats.hindiTotal.toLocaleString()}</div>
            <div className="overview-label">Hindi</div>
          </div>
          <div className="language-divider"></div>
          <div className="language-stat">
            <div className="overview-number">{stats.gujaratiTotal.toLocaleString()}</div>
            <div className="overview-label">Gujarati</div>
          </div>
        </div>
        {(() => {
          const inProgressCount = getContentByStatus('in_progress').hindi.length + getContentByStatus('in_progress').gujarati.length;
          return inProgressCount > 0 ? (
            <div className="overview-card">
              <div className="overview-number">{inProgressCount}</div>
              <div className="overview-label">Series in Progress</div>
            </div>
          ) : null;
        })()}
      </div>

      <div className="content-tables">
        {renderContentTable()}
      </div>

      <div className="page-footer">
        <div className="footer-actions">
          <Link to="/" className="btn btn-primary">
            🔍 Start Searching
          </Link>
        </div>
        
        <div className="update-info">
          <p>
            <strong>NOTE:</strong> Series marked as "In Progress" are currently being processed and will be available soon.
          </p>
        </div>
      </div>
    </div>
  );
};

export default SearchIndex;
