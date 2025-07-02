# USTA Tournament Map

A web application for browsing and filtering USTA tennis tournaments on an interactive map.

## Overview

This application fetches tournament data from the USTA API and displays it on an interactive map, allowing users to filter tournaments by date range and tournament type. The application is built with Python and Streamlit, using Folium for map visualization.

## Features

- Interactive map showing tournament locations across the US

- Filter tournaments by date range

- Filter tournaments by tournament type (Adult, Junior, etc.)

- View detailed tournament information by clicking on map markers

- Responsive design that works on both desktop and mobile devices

## Installation

1. Clone the repository:

```console
git clone https://github.com/yourusername/usta-tournament-map.git
cd usta-tournament-map
```

2. Create a virtual environment and install dependencies:

```console
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create necessary directories:

```console
mkdir -p data/raw data/processed static
```

## Usage

### Updating Tournament Data

To fetch the latest tournament data from the USTA API:

```console
python main.py --update
```

Optional parameters:

- `--max-pages`: Maximum number of pages to fetch (default: 5)

- `--sleep-min`: Minimum sleep time between requests (default: 2 seconds)

- `--sleep-max`: Maximum sleep time between requests (default: 5 seconds)

### Running the Web Application

To start the Streamlit web application:

```console
python main.py --webapp
```

Or directly with Streamlit:

```console
streamlit run main.py -- --webapp
```

## Project Structure

- `main.py`: Main entry point for the application

- `config.py`: Configuration settings for the application

- `data/`: Directory for storing tournament data

  - `tournaments.parquet`: Main tournament data file

  - `tournaments_slim.parquet`: Optimized version without the bulky data column

- `scraper/`: Code for fetching tournament data

  - `tournament_scraper.py`: Handles API requests to fetch tournament data

- `webapp/`: Web application code

  - `app.py`: Streamlit application for displaying tournaments

- `static/`: Static assets

  - `style.css`: CSS styles for the web application

## Technologies Used

- Python 3.10+

- Streamlit for web interface

- Pandas for data manipulation

- Folium for map visualization

- Parquet for efficient data storage

- Requests for API communication

## License

MIT License