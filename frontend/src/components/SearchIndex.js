import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { searchableContent, getSearchableStats, getContentByStatus } from '../utils/searchableContent.js';
import './SearchIndex.css';

const SearchIndex = () => {
  const [selectedLanguage, setSelectedLanguage] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const stats = getSearchableStats();

  const getFilteredContent = () => {
    let contentByStatus;
    
    if (selectedStatus === 'all') {
      contentByStatus = {
        hindi: searchableContent.hindi,
        gujarati: searchableContent.gujarati
      };
    } else {
      contentByStatus = getContentByStatus(selectedStatus);
    }
    
    if (selectedLanguage === 'all') {
      return {
        hindi: contentByStatus.hindi,
        gujarati: contentByStatus.gujarati
      };
    }
    
    return {
      hindi: selectedLanguage === 'hindi' ? contentByStatus.hindi : [],
      gujarati: selectedLanguage === 'gujarati' ? contentByStatus.gujarati : []
    };
  };

  const filteredContent = getFilteredContent();

  const renderContentTable = (content, language) => {
    if (!content || content.length === 0) return null;

    return (
      <div className="content-section">
        <h3 className="language-header">
          {language === 'hindi' ? 'Hindi Pravachans' : 'Gujarati Pravachans'}
        </h3>
        <div className="table-container">
          <table className="content-table">
            <thead>
              <tr>
                <th>Granth</th>
                <th>Year/Series</th>
                <th>Count</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {content.map((item, index) => (
                <tr key={`${language}-${index}`}>
                  <td className="granth-cell">{item.granth}</td>
                  <td className="series-cell">{item.series}</td>
                  <td className="count-cell">
                    {item.count ? item.count.toLocaleString() : 'Compiled'}
                  </td>
                  <td className="status-cell">
                    <span className={`status-badge ${item.status}`}>
                      {item.status === 'searchable' ? '✅ Searchable' : 
                       item.status === 'in_progress' ? '🔄 In Progress' : 
                       '📅 Planned'}
                    </span>
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
          <div className="overview-number">{stats.grandTotal.toLocaleString()}</div>
          <div className="overview-label">Total Pravachans Available</div>
        </div>
        <div className="overview-card">
          <div className="overview-number">{getContentByStatus('searchable').hindi.length + getContentByStatus('searchable').gujarati.length}</div>
          <div className="overview-label">Pravachan Series Available</div>
        </div>
        <div className="overview-card">
          <div className="overview-number">{getContentByStatus('in_progress').hindi.length + getContentByStatus('in_progress').gujarati.length}</div>
          <div className="overview-label">Pravachan Series in Progress</div>
        </div>
      </div>

      <div className="filters-section">
        <div className="filter-group">
          <label htmlFor="language-filter">Language:</label>
          <select 
            id="language-filter"
            value={selectedLanguage} 
            onChange={(e) => setSelectedLanguage(e.target.value)}
            className="filter-select"
          >
            <option value="all">All Languages</option>
            <option value="hindi">Hindi</option>
            <option value="gujarati">Gujarati</option>
          </select>
        </div>
        
        <div className="filter-group">
          <label htmlFor="status-filter">Status:</label>
          <select 
            id="status-filter"
            value={selectedStatus} 
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="filter-select"
          >
            <option value="all">All</option>
            <option value="searchable">Searchable</option>
            <option value="in_progress">In Progress</option>
          </select>
        </div>
      </div>

      <div className="content-tables">
        {renderContentTable(filteredContent.hindi, 'hindi')}
        {renderContentTable(filteredContent.gujarati, 'gujarati')}
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