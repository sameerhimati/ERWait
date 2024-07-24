const API_URL = '/api';

document.addEventListener('DOMContentLoaded', () => {
    const priceComparisonForm = document.getElementById('price-comparison-form');
    const zipCodeInput = document.getElementById('zip-code');
    const treatmentInput = document.getElementById('treatment');
    const resultsContainer = document.getElementById('results-container');

    priceComparisonForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const zipCode = zipCodeInput.value.trim();
        const treatment = treatmentInput.value.trim();

        if (!zipCode || !treatment) {
            displayResults({ error: 'Please enter both ZIP code and treatment.' });
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
            displayResults(data);
        } catch (error) {
            console.error('Error:', error);
            displayResults({ error: 'Sorry, there was an error processing your request.' });
        }
    });

    function displayResults(results) {
        resultsContainer.innerHTML = '';

        if (results.error) {
            resultsContainer.textContent = results.error;
            return;
        }

        if (results.length === 0) {
            resultsContainer.textContent = 'No results found for the given criteria.';
            return;
        }

        results.forEach(result => {
            const resultElement = document.createElement('div');
            resultElement.classList.add('result-item');
            resultElement.innerHTML = `
                <span class="facility-name">${result.facilityName}</span>
                <span class="price">$${result.price.toFixed(2)}</span>
            `;
            resultsContainer.appendChild(resultElement);
        });
    }
});