# ERWAIT - Emergency Room Wait Time Tracker

ERWAIT is a comprehensive web application designed to help users find nearby hospitals, compare emergency room wait times, and access healthcare information easily.

## Features

- **Hospital Map**: Interactive map showing nearby hospitals with real-time wait time information.
- **Healthcare Chat**: AI-powered chat system to answer healthcare-related questions.
- **Treatment Price Comparison**: Tool to compare treatment prices across different healthcare facilities.

## Project Structure

```
ERWAIT/
├── backend/              # Backend Python code
│   ├── helpers/          # Helper functions and utilities
│   ├── api.py            # Flask API endpoints
│   ├── chat_service.py   # Chat functionality
│   ├── main.py           # Main application entry point
│   └── price_comparison_service.py  # Price comparison logic
├── frontend/             # Frontend web files
│   ├── css/              # Stylesheets
│   ├── js/               # JavaScript files
│   └── *.html            # HTML pages
├── venv/                 # Python virtual environment
├── .env                  # Environment variables
├── .gitignore            # Git ignore file
├── README.md             # Project documentation
└── requirements.txt      # Python dependencies
```

## Setup and Installation

1. Clone the repository:
   ```
   git clone https://github.com/your-username/ERWAIT.git
   cd ERWAIT
   ```

2. Set up a Python virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Copy `.env.example` to `.env` and fill in the required values.

5. Initialize the database:
   ```
   python backend/helpers/init.sql
   ```

6. Run the application:
   ```
   python backend/main.py
   ```

7. Open a web browser and navigate to `http://localhost:5000` to access the application.

## Usage

- Use the navigation menu to switch between different features:
  - Hospital Map: View nearby hospitals and their wait times.
  - Healthcare Chat: Ask health-related questions and get AI-powered responses.
  - Treatment Price Comparison: Compare prices for specific treatments across different facilities.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- OpenAI for providing the GPT model used in the healthcare chat feature.
- Google Maps for the mapping functionality.