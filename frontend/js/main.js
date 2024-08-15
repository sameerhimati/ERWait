// Define the API URL
const API_URL = '/api';

// Map functionality
let map, userMarker, markers = [];
let currentInfoWindow = null;

let currentPage = 1;
let isLoading = false;
let hasMoreData = true;
let socket;
let userLocation = null;

function initializeMap() {
  console.log("Initializing map");
  try {
    map = new google.maps.Map(document.getElementById('map'), {
      center: { lat: 39.8283, lng: -98.5795 }, // Center of US
      zoom: 4
    });

    getUserLocation(); // This will fetch hospitals after getting user location
  } catch (error) {
    console.error("Error initializing map:", error);
    showError("Failed to initialize the map. Please try refreshing the page.");
  }

  google.maps.event.addListener(map, 'idle', fetchHospitals);
  google.maps.event.addListener(map, 'zoom_changed', resetPagination);
  google.maps.event.addListener(map, 'bounds_changed', function() {
    if (map.getZoom() > 10 && !isLoading && hasMoreData) {
      fetchHospitals();
    }
  });
}

function resetPagination() {
  currentPage = 1;
  clearMarkers();
  hasMoreData = true;
}

function getUserLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(position) {
            const userLocation = {
                lat: position.coords.latitude,
                lng: position.coords.longitude
            };
            map.setCenter(userLocation);
            map.setZoom(10);
            
            // Add a blue dot for user's location
            new google.maps.Marker({
                position: userLocation,
                map: map,
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 7,
                    fillColor: "#4285F4",
                    fillOpacity: 1,
                    strokeColor: "#ffffff",
                    strokeWeight: 2
                },
                title: "Your Location"
            });
            fetchHospitals();
            console.log('Fetched hospitals with user location');
        }, function() {
            handleLocationError(true, map.getCenter());
            console.log('Error: The Geolocation service failed.');
        });
    } else {
        handleLocationError(false, map.getCenter());
        console.log('Geolocation is not supported by this browser.');
    }
}

function handleLocationError(browserHasGeolocation, pos) {
    showError(browserHasGeolocation ?
        'Error: The Geolocation service failed.' :
        'Error: Your browser doesn\'t support geolocation.');
}


function initializeWebSocket() {
    socket = io(window.location.origin);

    socket.on('connect', () => {
        console.log('Connected to WebSocket');
        requestInitialData();
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from WebSocket');
    });

    socket.on('initial_data', (data) => {
        console.log('Received initial data:', data);
        addMarkersToMap(data.hospitals);
    });

    socket.on('wait_time_update', (data) => {
        console.log('Received wait time update:', data);
        updateMarkerWaitTime(data.hospital_id, data.new_wait_time);
    });
}

function requestInitialData() {
  const center = map.getCenter();
  const bounds = map.getBounds();
  const ne = bounds.getNorthEast();
  const radius =
    google.maps.geometry.spherical.computeDistanceBetween(center, ne) / 1609.34; // Convert to miles

  socket.emit('request_initial_data', {
    lat: center.lat(),
    lon: center.lng(),
    radius: radius
  });
}

function updateMarkerWaitTime(hospitalId, newWaitTime, isLive) {
    const marker = markers.find((m) => m.hospitalId === hospitalId);
    if (marker) {
      const hasData =
        newWaitTime !== null &&
        newWaitTime !== undefined &&
        newWaitTime !== 'N/A';
      const waitTime = hasData ? parseInt(newWaitTime) : null;
  
      let labelText = '';
      if (hasData) {
        labelText = isLive ? `${waitTime}` : 'CMS';
      }
  
      marker.setIcon(getMarkerIcon(waitTime, isLive, hasData));
      marker.setLabel({
        text: labelText,
        color: 'black',
        fontSize: '12px',
        fontWeight: 'bold'
      });
  
      if (currentInfoWindow && currentInfoWindow.anchor === marker) {
        const content = currentInfoWindow.getContent();
        const updatedContent = content.replace(
          /(?:Current|Historic average) wait time: .*<br>/,
          `${
            hasData
              ? isLive
                ? `Current wait time: ${waitTime} minutes`
                : `Historic average wait time: ${waitTime} minutes (CMS dataset)`
              : 'Wait time: Not available'
          }<br>`
        );
        currentInfoWindow.setContent(updatedContent);
      }
    }
  }

  function fetchHospitals() {
    if (isLoading || !hasMoreData) return;
  
    isLoading = true;
    showLoading();
  
    const bounds = map.getBounds();
    const center = map.getCenter();
    const ne = bounds.getNorthEast();
  
    // Calculate radius in miles
    const radius = google.maps.geometry.spherical.computeDistanceBetween(center, ne) / 1609.34;
  
    const url = `${API_URL}/hospitals?lat=${center.lat()}&lon=${center.lng()}&radius=${radius}&page=${currentPage}&per_page=50`;
    console.log('Fetching hospitals from:', url);
  
    fetch(url)
      .then(response => response.json())
      .then((data) => {
        console.log('Received hospital data:', data);
        addMarkersToMap(data.hospitals);
        updateNearestER(data.hospitals); // Call updateNearestER here
        currentPage++;
        hasMoreData = currentPage <= data.total_pages;
        isLoading = false;
        hideLoading();
      })
      .catch((error) => {
        console.error('Error fetching hospital data:', error);
        showError('Failed to fetch hospital data. Please try again later.');
        isLoading = false;
        hideLoading();
      });
  }
  

function createCustomMarkerIcon(color, hasData) {
  const svg = `
    <svg xmlns='http://www.w3.org/2000/svg' width='36' height='36' viewBox='0 0 36 36'>
      <circle cx='18' cy='18' r='16' fill='${color}' stroke='white' stroke-width='2'/>
      ${hasData ? "<circle cx='18' cy='18' r='6' fill='white'/>" : ''}
    </svg>`;

  return {
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
    scaledSize: new google.maps.Size(36, 36),
    anchor: new google.maps.Point(18, 18),
  };
}

function getMarkerIcon(waitTime, isLive, hasData) {
  let color;
  if (!hasData) {
    color = '#BDBDBD'; // Lighter gray for no data
  } else if (!isLive) {
    color = '#757575'; // Dark gray for historical data
  } else {
    // Live data color scheme
    if (waitTime <= 15) {
      color = '#4CAF50'; // Green
    } else if (waitTime <= 30) {
      color = '#FFC107'; // Yellow
    } else if (waitTime <= 60) {
      color = '#FF9800'; // Orange
    } else {
      color = '#F44336'; // Red
    }
  }

  return createCustomMarkerIcon(color, hasData);
}

function addMarkersToMap(hospitals) {
  console.log('Adding markers for hospitals:', hospitals);
  hospitals.forEach((hospital) => {
    const lat = parseFloat(hospital.latitude);
    const lng = parseFloat(hospital.longitude);

    if (!isNaN(lat) && !isNaN(lng)) {
      const hasData =
        hospital.wait_time !== null && hospital.wait_time !== undefined;
      const isLive = hospital.has_live_wait_time;
      const waitTime = hasData ? parseInt(hospital.wait_time) : null;

      const marker = new google.maps.Marker({
        position: { lat, lng },
        map: map,
        title: hospital.facility_name,
        hospitalId: hospital.id,
        icon: getMarkerIcon(waitTime, isLive, hasData),
        // Remove the label property entirely
      });

      marker.addListener('click', () => {
        if (currentInfoWindow) {
          currentInfoWindow.close();
        }
        const infoWindow = createInfoWindow(hospital, marker.getPosition());
        infoWindow.open(map, marker);
        currentInfoWindow = infoWindow;
      });

      markers.push(marker);
    } else {
      console.warn('Invalid coordinates for hospital:', hospital);
    }
  });
}

function createInfoWindow(hospital, position) {
    const hasData =
      hospital.wait_time !== null && hospital.wait_time !== undefined;
    const isLive = hospital.has_live_wait_time;
    const waitTime = hasData ? hospital.wait_time : null;
  
    let distanceText = '';
    let travelTimeId = `travel-time-${hospital.id}`;
  
    if (userLocation) {
      const distance = google.maps.geometry.spherical.computeDistanceBetween(
        userLocation,
        position
      );
      const distanceMiles = (distance * 0.000621371).toFixed(2); // Convert meters to miles
      distanceText = `<p>Distance: ${distanceMiles} miles</p>`;
    }
  
    const content = `
      <div style='max-width: 300px;'>
        <h3>${hospital.facility_name}</h3>
        <p>${hospital.address}, ${hospital.city}, ${hospital.state} ${hospital.zip_code}</p>
        ${
          hasData
            ? isLive
              ? `<p>Current wait time: ${waitTime} minutes</p>`
              : `<p>Historic average wait time: ${waitTime} minutes (CMS dataset Historical Average)</p>`
            : '<p>Wait time: Not available</p>'
        }
        ${hospital.phone_number ? `<p>Phone: ${hospital.phone_number}</p>` : ''}
        ${
          hospital.website
            ? `<p>Website: <a href='${hospital.website}' target='_blank'>${hospital.website}</a></p>`
            : ''
        }
        ${distanceText}
        <p>Travel time: <span id='${travelTimeId}'>Calculating...</span></p>
        <button onclick='openDirections(${position.lat()}, ${position.lng()})'>Get Directions</button>
      </div>
    `;
  
    const infoWindow = new google.maps.InfoWindow({ content });
  
    // Calculate travel time after the InfoWindow is opened
    infoWindow.addListener('domready', () => {
      if (userLocation) {
        calculateTravelTime(userLocation, position, travelTimeId);
      }
    });
  
    return infoWindow;
  }

  function calculateTravelTime(origin, destination, elementId) {
    const service = new google.maps.DistanceMatrixService();
    service.getDistanceMatrix(
      {
        origins: [origin],
        destinations: [destination],
        travelMode: 'DRIVING',
        unitSystem: google.maps.UnitSystem.IMPERIAL,
      },
      (response, status) => {
        if (status === 'OK') {
          const duration = response.rows[0].elements[0].duration.text;
          const element = document.getElementById(elementId);
          if (element) {
            element.textContent = duration;
          }
        }
      }
    );
  }

function openDirections(lat, lng) {
  const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
  window.open(url, '_blank');
}

function formatWaitTime(hospital) {
  if (hospital.wait_time === null || hospital.wait_time === undefined) {
    return 'Not available';
  }
  const waitTimeText = `${hospital.wait_time} minutes`;
  return hospital.has_live_wait_time
    ? waitTimeText
    : `${waitTimeText} (historical average)`;
}

function updateNearestER(hospitals) {
    if (userLocation && hospitals.length > 0) {
      const nearestHospital = hospitals.reduce(
        (nearest, hospital) => {
          const distance = google.maps.geometry.spherical.computeDistanceBetween(
            userLocation,
            new google.maps.LatLng(hospital.latitude, hospital.longitude)
          );
          return distance < nearest.distance ? { hospital, distance } : nearest;
        },
        { hospital: null, distance: Infinity }
      ).hospital;
  
      if (nearestHospital) {
        const nearestERInfo = document.getElementById('nearest-er-info');
        if (nearestERInfo) {
          nearestERInfo.innerHTML = `
            <div class='hospital-info'>
              <h3 class='text-xl font-semibold'>${nearestHospital.facility_name}</h3>
              <p>${nearestHospital.address}, ${nearestHospital.city}, ${nearestHospital.state} ${nearestHospital.zip_code}</p>
              <p>Wait time: <span class='wait-time'>${formatWaitTime(nearestHospital)}</span></p>
              <p>Travel time: <span id='nearest-travel-time'>Calculating...</span></p>
            </div>
            <a href='https://www.google.com/maps/dir/?api=1&destination=${nearestHospital.latitude},${nearestHospital.longitude}' target='_blank' class='directions-btn'>Get Directions</a>
          `;
  
          calculateTravelTime(
            userLocation,
            new google.maps.LatLng(nearestHospital.latitude, nearestHospital.longitude),
            'nearest-travel-time'
          );
        } else {
          console.error('Element with id "nearest-er-info" not found');
        }
      }
    }
  }

function clearMarkers() {
  markers.forEach((marker) => marker.setMap(null));
  markers = [];
}

function showLoading() {
  document.getElementById('loading').style.display = 'block';
}

function hideLoading() {
  document.getElementById('loading').style.display = 'none';
}
// Price comparison functionality
function initPriceComparison() {
  const priceComparisonForm = document.getElementById('price-comparison-form');
  if (priceComparisonForm) {
    priceComparisonForm.addEventListener('submit', handlePriceComparisonSubmit);
  }
}

async function handlePriceComparisonSubmit(e) {
  e.preventDefault();
  const zipCode = document.getElementById('zip-code').value;
  const treatment = document.getElementById('treatment').value;

  if (!zipCode.trim() || !treatment.trim()) {
    showError('Please enter both ZIP code and treatment.');
    return;
  }

  try {
    const response = await fetch(`${API_URL}/price-comparison`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ zipCode, treatment }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    displayPriceComparisonResults(data);
  } catch (error) {
    console.error('Error:', error);
    showError('Sorry, there was an error processing your request.');
  }
}

function displayPriceComparisonResults(results) {
  const resultsContainer = document.getElementById('results-container');
  resultsContainer.innerHTML = ''; // Clear previous results

  if (results.error) {
    showError(results.error);
    return;
  }

  results.forEach(result => {
    const resultElement = document.createElement('div');
    resultElement.textContent = `${result.facilityName}: $${result.price}`;
    resultsContainer.appendChild(resultElement);
});
}

// Navigation
function initNavigation() {
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const pageId = e.target.getAttribute('data-page');
        switchPage(pageId);
    });
});
}

function switchPage(pageId) {
document.querySelectorAll('.page').forEach(page => {
    page.style.display = 'none';
  });
  document.getElementById(`${pageId}-page`).style.display = 'block';
  if (pageId === 'map' && typeof initializeMap === 'function') {
    initializeMap();
  }
}

// Utility functions
function showError(message) {
  const errorDiv = document.getElementById('error');
  errorDiv.textContent = message;
  errorDiv.style.display = 'block';
}

function hideError() {
  document.getElementById('error').style.display = 'none';
}

function initMap() {
  initializeMap();
}

window.initMap = initMap;

// Initialize all features
function initAll() {
  if (typeof google !== 'undefined') {
    initializeMap();
    console.log('Google Maps API is ready!');
  } else {
    window.initializeMap = initializeMap;
    console.log('Google Maps API is not ready!');
  }
  //switchPage('map');
  initNavigation();
  initPriceComparison();
  initializeWebSocket();
}

// Call initAll when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initAll);
