// Global variables
let priceComparisonForm;
let resultsContainer;
let loadingIndicator;
let errorMessageContainer;

// Initialize the price comparison functionality
function initPriceComparison() {
    priceComparisonForm = document.getElementById('price-comparison-form');
    resultsContainer = document.getElementById('results-container');
    loadingIndicator = document.createElement('div');
    loadingIndicator.id = 'price-comparison-loading';
    loadingIndicator.className = 'hidden';
    loadingIndicator.textContent = 'Loading...';
    errorMessageContainer = document.createElement('div');
    errorMessageContainer.id = 'price-comparison-error';
    errorMessageContainer.className = 'hidden text-red-500';

    if (priceComparisonForm) {
        priceComparisonForm.appendChild(loadingIndicator);
        priceComparisonForm.appendChild(errorMessageContainer);
        priceComparisonForm.addEventListener('submit', handlePriceComparisonSubmit);
    } else {
        console.error('Price comparison form not found in the DOM');
    }
}


// Handle form submission
async function handlePriceComparisonSubmit(e) {
    e.preventDefault();
    const zipCode = document.getElementById('zip-code').value.trim();
    const treatment = document.getElementById('treatment').value.trim();

    if (!zipCode || !treatment) {
        showError('Please enter both ZIP code and treatment.');
        return;
    }

    showLoading();
    hideError();

    try {
        const results = await fetchPriceComparisonData(zipCode, treatment);
        displayPriceComparisonResults(results);
    } catch (error) {
        showError('An error occurred while fetching price comparison data. Please try again.');
        console.error('Price comparison error:', error);
    } finally {
        hideLoading();
    }
}

// Fetch price comparison data from the API
async function fetchPriceComparisonData(zipCode, treatment) {
    const response = await fetch('/api/price-comparison', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ zipCode, treatment }),
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
}

// Display price comparison results
function displayPriceComparisonResults(results) {
    resultsContainer.innerHTML = '';

    if (results.length === 0) {
        resultsContainer.innerHTML = '<p class="text-gray-600">No results found for the given criteria.</p>';
        return;
    }

    const resultsList = document.createElement('ul');
    resultsList.className = 'space-y-4';

    results.forEach((result, index) => {
        const listItem = document.createElement('li');
        listItem.className = 'flex justify-between items-center border-b pb-2';
        listItem.innerHTML = `
            <div>
                <span class="font-semibold">${index + 1}. ${result.facilityName}</span>
                <p class="text-sm text-gray-600">${result.address}, ${result.city}, ${result.state} ${result.zipCode}</p>
            </div>
            <span class="text-lg font-bold text-green-600">$${result.price.toFixed(2)}</span>
        `;
        resultsList.appendChild(listItem);
    });

    resultsContainer.appendChild(resultsList);
}

// Show loading indicator
function showLoading() {
    loadingIndicator.classList.remove('hidden');
}

// Hide loading indicator
function hideLoading() {
    loadingIndicator.classList.add('hidden');
}

// Show error message
function showError(message) {
    errorMessageContainer.textContent = message;
    errorMessageContainer.classList.remove('hidden');
}

// Hide error message
function hideError() {
    errorMessageContainer.classList.add('hidden');
}

// Export the initPriceComparison function for use in main.js
window.initPriceComparison = initPriceComparison;

// Optional: Initialize price comparison if the DOM is already loaded
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    initPriceComparison();
} else {
    document.addEventListener('DOMContentLoaded', initPriceComparison);
}