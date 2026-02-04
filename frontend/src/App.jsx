import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, ZoomControl } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'        // ← Use this
import 'leaflet.markercluster/dist/MarkerCluster.Default.css' // ← Use this
import './App.css'

// Fix for default marker icons in React-Leaflet
import L from 'leaflet'
import icon from 'leaflet/dist/images/marker-icon.png'
import iconShadow from 'leaflet/dist/images/marker-shadow.png'

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34]
})
L.Marker.prototype.options.icon = DefaultIcon

const getTournamentStatus = (tournament) => {
  const now = new Date()
  const startDate = new Date(tournament.startDate)
  const entriesCloseDateTime = tournament.entriesCloseDateTime 
    ? new Date(tournament.entriesCloseDateTime) 
    : null
  
  // Check if tournament has started (red)
  if (now >= startDate) {
    return 'started'
  }
  
  // Check if entries are closed (orange)
  if (entriesCloseDateTime && now >= entriesCloseDateTime) {
    return 'entries-closed'
  }
  
  // Still open for registration (blue)
  return 'open'
}

// Create colored marker icons
const createColoredIcon = (color) => {
  const svgIcon = `
    <svg width="25" height="41" viewBox="0 0 25 41" xmlns="http://www.w3.org/2000/svg">
      <path d="M12.5 0C5.596 0 0 5.596 0 12.5c0 9.375 12.5 28.5 12.5 28.5S25 21.875 25 12.5C25 5.596 19.404 0 12.5 0z" 
            fill="${color}" stroke="#fff" stroke-width="2"/>
      <circle cx="12.5" cy="12.5" r="4" fill="#fff"/>
    </svg>
  `
  
  return L.divIcon({
    html: svgIcon,
    className: 'custom-marker',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34]
  })
}

// Create icon variants
const blueIcon = createColoredIcon('#3b82f6')    // Blue - open
const orangeIcon = createColoredIcon('#f97316')  // Orange - entries closed
const redIcon = createColoredIcon('#ef4444')     // Red - started

// Helper to get the right icon
const getMarkerIcon = (status) => {
  switch(status) {
    case 'started': return redIcon
    case 'entries-closed': return orangeIcon
    default: return blueIcon
  }
}

// Helper to format tournament date range
const formatDateRange = (startDateStr, endDateStr) => {
  // Parse YYYY-MM-DD without timezone conversion
  const parseDate = (dateStr) => {
    const [year, month, day] = dateStr.split('T')[0].split('-');
    return new Date(year, month - 1, day);
  };
  
  const startDate = parseDate(startDateStr);
  const endDate = parseDate(endDateStr);
  
  const startYear = startDate.getFullYear();
  const endYear = endDate.getFullYear();
  
  const startFormatted = startDate.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric' 
  });
  
  // Only include year on end date, unless years differ
  const endOptions = startYear === endYear 
    ? { month: 'short', day: 'numeric', year: 'numeric' }
    : { month: 'short', day: 'numeric', year: 'numeric' };
  
  const endFormatted = endDate.toLocaleDateString('en-US', endOptions);
  
  return `${startFormatted} - ${endFormatted}`;
};

function App() {
  const [allTournaments, setAllTournaments] = useState([])
  const [filteredTournaments, setFilteredTournaments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Date filter state - default to next month
  const today = new Date().toISOString().split('T')[0]
  const oneMonthLater = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]

  const [fromDate, setFromDate] = useState(today)
  const [toDate, setToDate] = useState(oneMonthLater)

  // Category filter state (rename if you like)
  const [selectedCategories, setSelectedCategories] = useState(new Set())
  const [availableCategories, setAvailableCategories] = useState([])

  // Level filter state
  const [selectedLevels, setSelectedLevels] = useState(new Set())
  const [availableLevels, setAvailableLevels] = useState([])
  const [levelDropdownOpen, setLevelDropdownOpen] = useState(false)

  // Event filter states - dropdown style like Level
  const [selectedSurfaces, setSelectedSurfaces] = useState(new Set())
  const [availableSurfaces, setAvailableSurfaces] = useState([])
  const [surfaceDropdownOpen, setSurfaceDropdownOpen] = useState(false)

  const [selectedCourtLocations, setSelectedCourtLocations] = useState(new Set())
  const [availableCourtLocations, setAvailableCourtLocations] = useState([])
  const [courtLocationDropdownOpen, setCourtLocationDropdownOpen] = useState(false)

  const [selectedGenders, setSelectedGenders] = useState(new Set())
  const [availableGenders, setAvailableGenders] = useState([])
  const [genderDropdownOpen, setGenderDropdownOpen] = useState(false)

  const [selectedEventTypes, setSelectedEventTypes] = useState(new Set())
  const [availableEventTypes, setAvailableEventTypes] = useState([])
  const [eventTypeDropdownOpen, setEventTypeDropdownOpen] = useState(false)

  const [selectedTodsCodes, setSelectedTodsCodes] = useState(new Set())
  const [availableTodsCodes, setAvailableTodsCodes] = useState([])
  const [todsCodeDropdownOpen, setTodsCodeDropdownOpen] = useState(false)

  // Label mappings for filter display
  const genderLabels = {
    'boys': 'Men',
    'girls': 'Women',
    'coed': 'Coed',
    'mixed': 'Mixed',
  }

  const eventTypeLabels = {
    'singles': 'Singles',
    'doubles': 'Doubles',
    'team': 'Team',
  }

  const surfaceLabels = {
    'hard': 'Hard',
    'greenClay': 'Clay (Green)',
    'redClay': 'Clay (Red)',
    'grass': 'Grass',
  }

  const courtLocationLabels = {
    'indoor': 'Indoor',
    'outdoor': 'Outdoor',
  }

  // Helper function to get display label
  const getDisplayLabel = (value, labelMap) => {
    return labelMap[value] || value // Return mapped label or original if not found
  }

  // Fetch tournaments on mount
  useEffect(() => {
    fetch('/api/tournaments')
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch tournaments')
        return res.json()
      })
      .then(data => {
        setAllTournaments(data)

        // Extract unique categories from t.categories (array)
        const categorySet = new Set()
        data.forEach(t => {
          (t.categories || []).forEach(c => {
            if (c) categorySet.add(c)
          })
        })
        const categories = [...categorySet].sort()
        setAvailableCategories(categories)

        // Default to ONLY Adult selected
        const defaultCategories = new Set()
        if (categories.includes('Adult')) {
          defaultCategories.add('Adult')
        }
        setSelectedCategories(defaultCategories)

        // Extract unique levels
        const levels = [...new Set(data.map(t => t.level).filter(Boolean))].sort()
        setAvailableLevels(levels)

        // Default to ALL levels selected
        setSelectedLevels(new Set(levels))

        // Extract unique event properties from all 5 fields
        const surfaceSet = new Set()
        const courtLocationSet = new Set()
        const genderSet = new Set()
        const eventTypeSet = new Set()
        const todsCodeSet = new Set()

        data.forEach(t => {
          (t.events || []).forEach(event => {
            if (event.surface) surfaceSet.add(event.surface)
            if (event.courtLocation) courtLocationSet.add(event.courtLocation)
            if (event.gender) genderSet.add(event.gender)
            if (event.eventType) eventTypeSet.add(event.eventType)
            if (event.todsCode) todsCodeSet.add(event.todsCode)
          })
        })

        const surfaces = [...surfaceSet].sort()
        const courtLocations = [...courtLocationSet].sort()
        const genders = [...genderSet].sort()
        const eventTypes = [...eventTypeSet].sort()
        const todsCodes = [...todsCodeSet].sort()

        setAvailableSurfaces(surfaces)
        setAvailableCourtLocations(courtLocations)
        setAvailableGenders(genders)
        setAvailableEventTypes(eventTypes)
        setAvailableTodsCodes(todsCodes)

        // Default to ALL selected for event filters
        setSelectedSurfaces(new Set(surfaces))
        setSelectedCourtLocations(new Set(courtLocations))
        setSelectedGenders(new Set(genders))
        setSelectedEventTypes(new Set(eventTypes))
        setSelectedTodsCodes(new Set(todsCodes))

        setLoading(false)
      })
      .catch(err => {
        console.error('Error:', err)
        setError(err.message)
        setLoading(false)
      })
  }, [])

  // Filter tournaments when dates, categories, levels, or data change
  useEffect(() => {
    if (allTournaments.length === 0) {
      setFilteredTournaments([])
      return
    }

    const filtered = allTournaments.filter(t => {
      if (!t.startDate) return false

      // Date filter
      const startDateStr = t.startDate.split('T')[0]
      const dateMatch = startDateStr >= fromDate && startDateStr <= toDate

      // Category filter - if nothing selected, show nothing
      if (selectedCategories.size === 0) return false
      const tournamentCategories = t.categories || []
      const categoryMatch = tournamentCategories.some(cat =>
        selectedCategories.has(cat)
      )

      // Level filter - if nothing selected, show nothing
      if (selectedLevels.size === 0) return false
      const levelMatch = selectedLevels.has(t.level)

      // Event filters - if ANY filter has nothing selected, show nothing
      if (selectedSurfaces.size === 0) return false
      if (selectedCourtLocations.size === 0) return false
      if (selectedGenders.size === 0) return false
      if (selectedEventTypes.size === 0) return false
      if (selectedTodsCodes.size === 0) return false

      // Get tournament events
      const events = t.events || []
      
      // If no events, exclude
      if (events.length === 0) return false

      // Tournament must have at least one event matching ALL selected filters
      const eventMatch = events.some(event => {
        const surfaceMatch = event.surface && selectedSurfaces.has(event.surface)
        const courtLocationMatch = event.courtLocation && selectedCourtLocations.has(event.courtLocation)
        const genderMatch = event.gender && selectedGenders.has(event.gender)
        const eventTypeMatch = event.eventType && selectedEventTypes.has(event.eventType)
        const todsCodeMatch = event.todsCode && selectedTodsCodes.has(event.todsCode)
        
        // Event matches if ALL criteria pass
        return surfaceMatch && courtLocationMatch && genderMatch && eventTypeMatch && todsCodeMatch
      })

      return dateMatch && categoryMatch && levelMatch && eventMatch
    })

    setFilteredTournaments(filtered)
  }, [allTournaments, fromDate, toDate, selectedCategories, selectedLevels, 
      selectedSurfaces, selectedCourtLocations, selectedGenders, selectedEventTypes, selectedTodsCodes])

  // Toggle category selection
  const toggleCategory = (category) => {
    setSelectedCategories(prev => {
      const newSet = new Set(prev)
      if (newSet.has(category)) {
        newSet.delete(category)
      } else {
        newSet.add(category)
      }
      return newSet
    })
  }

  const selectAllCategories = () => {
    setSelectedCategories(new Set(availableCategories))
  }
  const clearAllCategories = () => {
    setSelectedCategories(new Set())
  }

  // Toggle level selection
  const toggleLevel = (level) => {
    setSelectedLevels(prev => {
      const newSet = new Set(prev)
      if (newSet.has(level)) {
        newSet.delete(level)
      } else {
        newSet.add(level)
      }
      return newSet
    })
  }

  const selectAllLevels = () => {
    setSelectedLevels(new Set(availableLevels))
  }

  const clearAllLevels = () => {
    setSelectedLevels(new Set())
  }

  // Toggle surface selection
  const toggleSurface = (surface) => {
    setSelectedSurfaces(prev => {
      const newSet = new Set(prev)
      if (newSet.has(surface)) {
        newSet.delete(surface)
      } else {
        newSet.add(surface)
      }
      return newSet
    })
  }

  const selectAllSurfaces = () => {
    setSelectedSurfaces(new Set(availableSurfaces))
  }

  const clearAllSurfaces = () => {
    setSelectedSurfaces(new Set())
  }

  // Toggle court location selection
  const toggleCourtLocation = (location) => {
    setSelectedCourtLocations(prev => {
      const newSet = new Set(prev)
      if (newSet.has(location)) {
        newSet.delete(location)
      } else {
        newSet.add(location)
      }
      return newSet
    })
  }

  const selectAllCourtLocations = () => {
    setSelectedCourtLocations(new Set(availableCourtLocations))
  }

  const clearAllCourtLocations = () => {
    setSelectedCourtLocations(new Set())
  }

  // Toggle gender selection
  const toggleGender = (gender) => {
    setSelectedGenders(prev => {
      const newSet = new Set(prev)
      if (newSet.has(gender)) {
        newSet.delete(gender)
      } else {
        newSet.add(gender)
      }
      return newSet
    })
  }

  const selectAllGenders = () => {
    setSelectedGenders(new Set(availableGenders))
  }

  const clearAllGenders = () => {
    setSelectedGenders(new Set())
  }

  // Toggle event type selection
  const toggleEventType = (eventType) => {
    setSelectedEventTypes(prev => {
      const newSet = new Set(prev)
      if (newSet.has(eventType)) {
        newSet.delete(eventType)
      } else {
        newSet.add(eventType)
      }
      return newSet
    })
  }

  const selectAllEventTypes = () => {
    setSelectedEventTypes(new Set(availableEventTypes))
  }

  const clearAllEventTypes = () => {
    setSelectedEventTypes(new Set())
  }

  // Toggle TODS code selection
  const toggleTodsCode = (code) => {
    setSelectedTodsCodes(prev => {
      const newSet = new Set(prev)
      if (newSet.has(code)) {
        newSet.delete(code)
      } else {
        newSet.add(code)
      }
      return newSet
    })
  }

  const selectAllTodsCodes = () => {
    setSelectedTodsCodes(new Set(availableTodsCodes))
  }

  const clearAllTodsCodes = () => {
    setSelectedTodsCodes(new Set())
  }

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>Loading tournaments...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="error-container">
        <h2>⚠️ Error</h2>
        <p>{error}</p>
        <button onClick={() => window.location.reload()}>Retry</button>
      </div>
    )
  }

  return (
    <div className="app">
      {/* Floating header with filters */}
      <div className="header-overlay">
        <div className="header-title">
          <h1>USTA Tournaments</h1>
          <span className="tournament-count">
            {filteredTournaments.length} of {allTournaments.length}
          </span>
        </div>

        <div className="date-filters">
          <div className="filter-section-header">
            <label>Start Date</label>
          </div>
          <div className="date-inputs">
            <div className="date-filter-group">
              <label htmlFor="from-date">From</label>
              <input
                id="from-date"
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
              />
            </div>
            <div className="date-filter-group">
              <label htmlFor="to-date">To</label>
              <input
                id="to-date"
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Category filter */}
        <div className="type-filter">
          <div className="type-filter-header">
            <label>Category</label>
            <div className="type-filter-actions">
              <button onClick={selectAllCategories} className="filter-btn">All</button>
              <button onClick={clearAllCategories} className="filter-btn">None</button>
            </div>
          </div>
          <div className="type-checkboxes">
            {availableCategories.map(category => (
              <label key={category} className="type-checkbox">
                <input
                  type="checkbox"
                  checked={selectedCategories.has(category)}
                  onChange={() => toggleCategory(category)}
                />
                <span>{category}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Level filter - dropdown style */}
        <div className="type-filter filter-dropdown">
          <div 
            className="dropdown-header"
            onClick={() => setLevelDropdownOpen(!levelDropdownOpen)}
          >
            <div className="dropdown-label">
              <label>Level</label>
              <span className="selected-count">
                ({selectedLevels.size} selected)
              </span>
            </div>
            <span className={`dropdown-arrow ${levelDropdownOpen ? 'open' : ''}`}>
              ▼
            </span>
          </div>
          
          {levelDropdownOpen && (
            <div className="dropdown-content">
              <div className="type-checkboxes">
                {availableLevels.map(level => (
                  <label key={level} className="type-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedLevels.has(level)}
                      onChange={() => toggleLevel(level)}
                    />
                    <span>{level}</span>
                  </label>
                ))}
              </div>
              <div className="type-filter-actions">
                <button onClick={selectAllLevels} className="filter-btn">All</button>
                <button onClick={clearAllLevels} className="filter-btn">None</button>
              </div>
            </div>
          )}
        </div>

        {/* Surface filter - dropdown */}
        <div className="type-filter filter-dropdown">
          <div 
            className="dropdown-header"
            onClick={() => setSurfaceDropdownOpen(!surfaceDropdownOpen)}
          >
            <div className="dropdown-label">
              <label>Surface</label>
              <span className="selected-count">
                ({selectedSurfaces.size} selected)
              </span>
            </div>
            <span className={`dropdown-arrow ${surfaceDropdownOpen ? 'open' : ''}`}>
              ▼
            </span>
          </div>
          
          {surfaceDropdownOpen && (
            <div className="dropdown-content">
              <div className="type-checkboxes">
                {availableSurfaces
                  .sort((a, b) => getDisplayLabel(a, surfaceLabels).localeCompare(getDisplayLabel(b, surfaceLabels)))
                  .map(surface => (
                    <label key={surface} className="type-checkbox">
                      <input
                        type="checkbox"
                        checked={selectedSurfaces.has(surface)}
                        onChange={() => toggleSurface(surface)}
                      />
                      <span>{getDisplayLabel(surface, surfaceLabels)}</span>
                    </label>
                  ))}
              </div>
              <div className="type-filter-actions">
                <button onClick={selectAllSurfaces} className="filter-btn">All</button>
                <button onClick={clearAllSurfaces} className="filter-btn">None</button>
              </div>
            </div>
          )}
        </div>

        {/* Court Location filter - dropdown */}
        <div className="type-filter filter-dropdown">
          <div 
            className="dropdown-header"
            onClick={() => setCourtLocationDropdownOpen(!courtLocationDropdownOpen)}
          >
            <div className="dropdown-label">
              <label>Court Location</label>
              <span className="selected-count">
                ({selectedCourtLocations.size} selected)
              </span>
            </div>
            <span className={`dropdown-arrow ${courtLocationDropdownOpen ? 'open' : ''}`}>
              ▼
            </span>
          </div>
          
          {courtLocationDropdownOpen && (
            <div className="dropdown-content">
              <div className="type-checkboxes">
                {availableCourtLocations
                  .sort((a, b) => getDisplayLabel(a, courtLocationLabels).localeCompare(getDisplayLabel(b, courtLocationLabels)))
                  .map(location => (
                    <label key={location} className="type-checkbox">
                      <input
                        type="checkbox"
                        checked={selectedCourtLocations.has(location)}
                        onChange={() => toggleCourtLocation(location)}
                      />
                      <span>{getDisplayLabel(location, courtLocationLabels)}</span>
                    </label>
                  ))}
              </div>
              <div className="type-filter-actions">
                <button onClick={selectAllCourtLocations} className="filter-btn">All</button>
                <button onClick={clearAllCourtLocations} className="filter-btn">None</button>
              </div>
            </div>
          )}
        </div>

        {/* Gender filter - dropdown */}
        <div className="type-filter filter-dropdown">
          <div 
            className="dropdown-header"
            onClick={() => setGenderDropdownOpen(!genderDropdownOpen)}
          >
            <div className="dropdown-label">
              <label>Gender</label>
              <span className="selected-count">
                ({selectedGenders.size} selected)
              </span>
            </div>
            <span className={`dropdown-arrow ${genderDropdownOpen ? 'open' : ''}`}>
              ▼
            </span>
          </div>
          
          {genderDropdownOpen && (
            <div className="dropdown-content">
              <div className="type-checkboxes">
                {availableGenders
                  .sort((a, b) => getDisplayLabel(a, genderLabels).localeCompare(getDisplayLabel(b, genderLabels)))
                  .map(gender => (
                    <label key={gender} className="type-checkbox">
                      <input
                        type="checkbox"
                        checked={selectedGenders.has(gender)}
                        onChange={() => toggleGender(gender)}
                      />
                      <span>{getDisplayLabel(gender, genderLabels)}</span>
                    </label>
                  ))}
              </div>
              <div className="type-filter-actions">
                <button onClick={selectAllGenders} className="filter-btn">All</button>
                <button onClick={clearAllGenders} className="filter-btn">None</button>
              </div>
            </div>
          )}
        </div>

        {/* Event Type filter - dropdown */}
        <div className="type-filter filter-dropdown">
          <div 
            className="dropdown-header"
            onClick={() => setEventTypeDropdownOpen(!eventTypeDropdownOpen)}
          >
            <div className="dropdown-label">
              <label>Event Type</label>
              <span className="selected-count">
                ({selectedEventTypes.size} selected)
              </span>
            </div>
            <span className={`dropdown-arrow ${eventTypeDropdownOpen ? 'open' : ''}`}>
              ▼
            </span>
          </div>
          
          {eventTypeDropdownOpen && (
            <div className="dropdown-content">
              <div className="type-checkboxes">
                {availableEventTypes
                .sort((a, b) => getDisplayLabel(a, eventTypeLabels).localeCompare(getDisplayLabel(b, eventTypeLabels)))
                .map(eventType => (
                  <label key={eventType} className="type-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedEventTypes.has(eventType)}
                      onChange={() => toggleEventType(eventType)}
                    />
                    <span>{getDisplayLabel(eventType, eventTypeLabels)}</span>
                  </label>
                ))}
              </div>
              <div className="type-filter-actions">
                <button onClick={selectAllEventTypes} className="filter-btn">All</button>
                <button onClick={clearAllEventTypes} className="filter-btn">None</button>
              </div>
            </div>
          )}
        </div>

        {/* TODS Code filter - dropdown */}
        <div className="type-filter filter-dropdown">
          <div 
            className="dropdown-header"
            onClick={() => setTodsCodeDropdownOpen(!todsCodeDropdownOpen)}
          >
            <div className="dropdown-label">
              <label>Age (TODS)</label>
              <span className="selected-count">
                ({selectedTodsCodes.size} selected)
              </span>
            </div>
            <span className={`dropdown-arrow ${todsCodeDropdownOpen ? 'open' : ''}`}>
              ▼
            </span>
          </div>
          
          {todsCodeDropdownOpen && (
            <div className="dropdown-content">
              <div className="type-checkboxes">
                {availableTodsCodes.map(code => (
                  <label key={code} className="type-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedTodsCodes.has(code)}
                      onChange={() => toggleTodsCode(code)}
                    />
                    <span>{code}</span>
                  </label>
                ))}
              </div>
              <div className="type-filter-actions">
                <button onClick={selectAllTodsCodes} className="filter-btn">All</button>
                <button onClick={clearAllTodsCodes} className="filter-btn">None</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Full-screen map with clustering */}
      <MapContainer 
        center={[39.8283, -98.5795]} 
        zoom={4} 
        className="map-container"
        scrollWheelZoom={true}
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={18}
        />

        <ZoomControl position="topleft" />

        <MarkerClusterGroup
          key={`${fromDate}-${toDate}-${selectedCategories.size}-${selectedLevels.size}`}
          chunkedLoading
          showCoverageOnHover={false}
          maxClusterRadius={60}
          spiderfyOnMaxZoom={true}
          zoomToBoundsOnClick={true}
        >
          {filteredTournaments.map(tournament => {
            const status = getTournamentStatus(tournament)
            const icon = getMarkerIcon(status)
            
            return (
              <Marker 
                key={tournament.id}
                position={[tournament.latitude, tournament.longitude]}
                icon={icon}
              >
                <Popup maxWidth={300}>
                  <div className="popup-content">
                    <h3>{tournament.name}</h3>
                    <div className="popup-details">
                      <div className="detail-row">
                        <span className="icon">📍</span>
                        <span>{tournament.location}</span>
                      </div>

                      <div className="detail-row">
                        <span className="icon">📅</span>
                        <span>{formatDateRange(tournament.startDate, tournament.endDate)}</span>
                      </div>

                      {tournament.categories && (
                        <div className="detail-row">
                          <span className="icon">👥</span>
                          <span>{(tournament.categories || []).join(', ')}</span>
                        </div>
                      )}

                      {tournament.level && (
                        <div className="detail-row">
                          <span className="icon">📊</span>
                          <span>{tournament.level}</span>
                        </div>
                      )}
                    </div>

                    {tournament.url && (
                      <a 
                        href={tournament.url}
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="details-link"
                      >
                        View Details →
                      </a>
                    )}
                  </div>
                </Popup>
              </Marker>
            )
          })}
        </MarkerClusterGroup>
      </MapContainer>
    </div>
  )
}

export default App