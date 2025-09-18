/**
 * Searchable Content Index
 * 
 * This file maintains a list of all pravachans and content available for search.
 * Update this file as new content is indexed and made searchable.
 */

export const searchableContent = {
  hindi: [
    {
      granth: "Samaysaar",
      series: "1978-80 (19th time)",
      count: 536,
      status: "searchable"
    },
    {
      granth: "Pravachansaar", 
      series: "1979-80",
      count: 287,
      status: "searchable"
    },
    {
      granth: "Niyamsaar",
      series: "1979-80",
      count: 214,
      status: "searchable"
    },
    {
      granth: "Niyamsaar",
      series: "1971",
      count: 202,
      status: "searchable"
    },
    {
      granth: "Panchastikaya",
      series: "1970",
      count: 88,
      status: "searchable"
    },
    {
      granth: "Asht Pahud",
      series: "1970-71",
      count: 195,
      status: "searchable"
    },
    {
      granth: "Samaysaar Kalash Tika",
      series: "1977-78",
      count: 308,
      status: "searchable"
    },
    {
      granth: "Parmatma Prakash",
      series: "1976-77",
      count: 245,
      status: "searchable"
    },
    {
      granth: "Samadhi Tantra",
      series: "1974",
      count: 110,
      status: "searchable"
    },
    {
      granth: "Purusharth Siddhi Upay",
      series: "1966",
      count: 89,
      status: "searchable"
    },
    {
      granth: "Padmanandi Panchvinshati",
      series: "1960",
      count: 69,
      status: "searchable"
    },
    {
      granth: "Natak Samaysar",
      series: "1971-72",
      count: 197,
      status: "searchable"
    },
    {
      granth: "Ishtopadesh",
      series: "1966",
      count: 55,
      status: "searchable"
    },
    {
      granth: "Yogsaar",
      series: "1966",
      count: 45,
      status: "searchable"
    },
    {
      granth: "Kartikeya Anupreksha",
      series: "1952",
      count: null,
      status: "searchable"
    },
    {
        granth: "Bahinshree Nu Vachanamrut",
        series: 1978,
        count: 181,
        status: "in_progress"
    },
    {
        granth: "Pravachan Navneet",
        series: 1977,
        count: 142,
        status: "planned"
    }
  ],
  gujarati: [
    {
      granth: "Samaysaar",
      series: "1966-68 (15th time)",
      count: 595,
      status: "searchable"
    },
    {
      granth: "Pravachansaar",
      series: "1968-69",
      count: 280,
      status: "in_progress"
    },
    {
        granth: "Samaysaar",
        series: "1975 (18th time)",
        count: 535,
        status: "planned"
    }
  ]
};

/**
 * Get searchable content statistics
 */
export const getSearchableStats = () => {
  const hindiSearchable = searchableContent.hindi.filter(item => item.status === 'searchable');
  const gujaratiSearchable = searchableContent.gujarati.filter(item => item.status === 'searchable');
  
  const hindiTotal = hindiSearchable.reduce((sum, item) => sum + (item.count || 0), 0);
  const gujaratiTotal = gujaratiSearchable.reduce((sum, item) => sum + (item.count || 0), 0);
  
  const hindiSeries = hindiSearchable.length;
  const gujaratiSeries = gujaratiSearchable.length;
  
  return {
    hindiTotal,
    gujaratiTotal,
    hindiSeries,
    gujaratiSeries,
    grandTotal: hindiTotal + gujaratiTotal
  };
};

/**
 * Get content by status
 */
export const getContentByStatus = (status = 'searchable') => {
  return {
    hindi: searchableContent.hindi.filter(item => item.status === status),
    gujarati: searchableContent.gujarati.filter(item => item.status === status)
  };
};

/**
 * Get all unique granths
 */
export const getAllGranths = () => {
  const hindiGranths = searchableContent.hindi.map(item => item.granth);
  const gujaratiGranths = searchableContent.gujarati.map(item => item.granth);
  return [...new Set([...hindiGranths, ...gujaratiGranths])];
};