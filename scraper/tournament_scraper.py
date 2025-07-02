"""
Tournament scraper module for fetching USTA tournament data.

This module handles API requests to fetch tournament data from the USTA API,
with pagination, rate limiting, and error handling.
"""
import os
import json
import time
import random
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

import requests

from config import API_ENDPOINT, DEFAULT_HEADERS, DEFAULT_SEARCH_PARAMS

# Configure logger
logger = logging.getLogger(__name__)

class TournamentScraper:
    """
    Scraper for fetching tournament data from the USTA API.
    
    This class handles API requests with pagination, rate limiting, and error handling
    to fetch tournament data from the USTA API.
    """

    def __init__(self) -> None:
        """Initialize the scraper with API endpoint, headers, and default parameters."""
        self.endpoint = API_ENDPOINT
        self.headers = DEFAULT_HEADERS
        self.default_params = DEFAULT_SEARCH_PARAMS
        logger.debug(f"TournamentScraper initialized with endpoint: {self.endpoint}")
    
    def fetch_tournaments(self, max_pages: int = 5, sleep_min: float = 2, sleep_max: float = 5) -> List[Dict[str, Any]]:
        """
        Fetch tournaments from the USTA API with pagination.
        
        Args:
            max_pages: Maximum number of pages to fetch
            sleep_min: Minimum sleep time between requests (seconds)
            sleep_max: Maximum sleep time between requests (seconds)
            
        Returns:
            List of tournament objects
        """
        all_tournaments = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"Starting tournament fetch with max_pages={max_pages}")
        
        for page in range(max_pages):
            # Update the 'from' parameter for pagination
            params = self.default_params.copy()
            params['options']['from'] = page * params['options']['size']
            
            try:
                logger.info(f"Fetching page {page+1} of tournaments")
                
                # Make API request
                response = requests.post(
                    self.endpoint,
                    json=params,
                    headers=self.headers
                )
                
                # Check if we got a valid response
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract tournaments from the correct nested structure
                    search_results = data.get('searchResults', [])
                    
                    # Process each search result to extract the actual tournament data
                    page_tournaments = []
                    for result in search_results:
                        # The actual tournament data is in the 'item' key
                        tournament = result.get('item', {})
                        if tournament:  # Only add if we have actual tournament data
                            page_tournaments.append(tournament)
                    
                    all_tournaments.extend(page_tournaments)
                    logger.info(f"Found {len(page_tournaments)} tournaments on page {page+1}")
                    
                    # If we got fewer items than requested, we've reached the end
                    if len(search_results) < params['options']['size']:
                        logger.info("Reached the end of results")
                        break
                        
                elif response.status_code == 204:
                    # No content response
                    logger.info("No more tournaments found (204 No Content)")
                    break
                else:
                    logger.error(f"Error fetching tournaments: HTTP {response.status_code}")
                    break
                
                # Sleep to avoid rate limiting
                sleep_time = random.uniform(sleep_min, sleep_max)
                logger.debug(f"Sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
                
            except requests.RequestException as e:
                logger.error(f"Request error fetching tournaments: {e}", exc_info=True)
                break
            except Exception as e:
                logger.error(f"Unexpected error fetching tournaments: {e}", exc_info=True)
                break
        
        logger.info(f"Fetched a total of {len(all_tournaments)} tournaments")
        return all_tournaments