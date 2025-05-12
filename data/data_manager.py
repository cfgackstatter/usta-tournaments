"""
Data management module for USTA tournament data.

This module handles saving, loading, and filtering tournament data using Parquet files.
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytz

from config import TOURNAMENTS_FILE, PROCESSED_DIR, RAW_DIR

from config import TOURNAMENTS_FILE, PROCESSED_DIR, RAW_DIR

# Configure logger
logger = logging.getLogger(__name__)

class DataManager:
    """
    Manages tournament data storage and retrieval using Parquet files.
    
    This class handles saving tournament data to Parquet files, loading data,
    and filtering tournaments based on various criteria.
    """

    def __init__(self) -> None:
        """Initialize the DataManager with the configured tournament file path."""
        self.tournaments_file = TOURNAMENTS_FILE
        logger.debug(f"DataManager initialized with file: {self.tournaments_file}")
    
    def save_tournaments(self, tournaments: List[Dict[str, Any]]) -> None:
        """
        Save tournaments to Parquet files - both a complete version with all data
        and a slim version without the 'data' column for more efficient app usage.
        
        Args:
            tournaments: List of tournament dictionaries containing tournament data
                        from the USTA API.
        
        Returns:
            None
        """
        try:
            if not tournaments:
                logger.warning("No tournaments provided to save")
                return
            
            logger.info(f"Processing {len(tournaments)} tournaments for storage")

            # Process tournaments to extract key fields
            processed_data = []
            for tournament in tournaments:
                # Extract key fields for querying
                tournament_id = tournament.get('id', '')
                name = tournament.get('name', '')
                is_cancelled = tournament.get('isCancelled', False)
                
                # Extract location data with proper nested access
                location_data = tournament.get('location', {})
                latitude = location_data.get('geo', {}).get('latitude', None)
                longitude = location_data.get('geo', {}).get('longitude', None)
                location = location_data.get('name', '')
                
                # Extract timezone-aware dates
                timezone_str = tournament.get('timeZone', 'UTC')
                start_date = tournament.get('timeZoneStartDateTime', tournament.get('startDate', None))
                end_date = tournament.get('timeZoneEndDateTime', tournament.get('endDate', None))
                
                # Extract tournament type from nested structure
                tournament_type = tournament.get('levelCategories', [])[0].get('name', '') if tournament.get('levelCategories', []) else ''

                # Extract URL components for building tournament link
                url = tournament.get('url', '')
                url_segment = tournament.get('organization', {}).get('urlSegment', '')
                tournament_url = f"https://playtennis.usta.com/Competitions/{url_segment}{url}" if url and url_segment else ''

                # Extract enhanced location information
                primary_location = tournament.get('primaryLocation', {})
                town = primary_location.get('town', '')
                county = primary_location.get('county', '')
                full_location = ", ".join(filter(None, [location, town, county]))

                # Extract tournament level
                tournament_level = tournament.get('level', {}).get('name', '')

                # Extract registration close datetime
                registration_restrictions = tournament.get('registrationRestrictions', {})
                entries_close_datetime = registration_restrictions.get('entriesCloseDateTime', None)
                registration_timezone = registration_restrictions.get('timeZone', timezone_str)  # Fall back to tournament timezone
                
                # Create a processed record
                processed_record = {
                    'id': tournament_id,
                    'name': name,
                    'is_cancelled': is_cancelled,
                    'start_date': start_date,
                    'end_date': end_date,
                    'timezone': timezone_str,
                    'latitude': latitude,
                    'longitude': longitude,
                    'location': location,
                    'tournament_type': tournament_type,
                    'tournament_level': tournament_level,
                    'entries_close_datetime': entries_close_datetime,
                    'registration_timezone': registration_timezone,
                    'tournament_url': tournament_url,
                    'full_location': full_location,
                    'data': json.dumps(tournament),  # Store full data as JSON string
                    'last_updated': datetime.now().isoformat()
                }
                
                processed_data.append(processed_record)
            
            # Convert to DataFrame
            df = pd.DataFrame(processed_data)
            
            # If file exists, merge with existing data
            if os.path.exists(self.tournaments_file):
                logger.info(f"Merging with existing data in {self.tournaments_file}")
                existing_df = pd.read_parquet(self.tournaments_file)
                
                # Remove existing records with same IDs
                existing_df = existing_df[~existing_df['id'].isin(df['id'])]
                
                # Concatenate with new data
                df = pd.concat([existing_df, df], ignore_index=True)
            
            # Save to Parquet file
            df.to_parquet(self.tournaments_file, engine='pyarrow', index=False)

            # Create and save a slim version without the 'data' column
            slim_df = df[df['is_cancelled'] == False].drop(columns=['data', 'is_cancelled'])
            slim_file = self.tournaments_file.replace('.parquet', '_slim.parquet')
            slim_df.to_parquet(slim_file, engine='pyarrow', index=False)
            
            # Also save timestamped versions for history
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            history_file = os.path.join(PROCESSED_DIR, f"tournaments_{timestamp}.parquet")
            history_slim_file = os.path.join(PROCESSED_DIR, f"tournaments_slim_{timestamp}.parquet")
            df.to_parquet(history_file, engine='pyarrow', index=False)
            slim_df.to_parquet(history_slim_file, engine='pyarrow', index=False)
            
            # Log file sizes for comparison
            if os.path.exists(self.tournaments_file) and os.path.exists(slim_file):
                file_size_original = os.path.getsize(self.tournaments_file) / (1024 * 1024)  # MB
                file_size_slim = os.path.getsize(slim_file) / (1024 * 1024)  # MB
                logger.info(f"Original file size: {file_size_original:.2f} MB")
                logger.info(f"Slim file size: {file_size_slim:.2f} MB")
                logger.info(f"Size reduction: {(1 - file_size_slim/file_size_original) * 100:.1f}%")
            
            logger.info(f"Saved {len(tournaments)} tournaments to Parquet files")
            logger.info(f"Total tournaments in file: {len(df)}")
            
        except Exception as e:
            logger.error(f"Error saving tournaments to Parquet: {e}", exc_info=True)
    
    def get_tournaments(self, filters: Optional[Dict[str, Any]] = None, use_slim: bool = True) -> pd.DataFrame:
        """
        Get tournaments with optional filters.
        
        Args:
            filters: Dictionary of filter criteria, which may include:
                    - tournament_type: Type of tournament (e.g., 'adult', 'junior')
                    - start_date: Minimum start date for tournaments
                    - end_date: Maximum end date for tournaments
            use_slim: Whether to use the slim version of the Parquet file (default: True)
            
        Returns:
            DataFrame containing filtered tournament data
        """
        try:
            # Determine which file to use
            file_path = self.tournaments_file.replace('.parquet', '_slim.parquet') if use_slim else self.tournaments_file
            
            if not os.path.exists(file_path):
                logger.warning(f"Tournaments file does not exist: {file_path}")
                return pd.DataFrame()
            
            # Read the Parquet file
            logger.debug(f"Loading tournaments from {file_path}")
            df = pd.read_parquet(file_path)

            # Convert datetime strings to pandas datetime objects if they aren't already
            if 'start_date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['start_date']):
                df['start_date'] = pd.to_datetime(df['start_date'])
            
            if 'end_date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['end_date']):
                df['end_date'] = pd.to_datetime(df['end_date'])
            
            # Apply filters
            if filters:
                logger.debug(f"Applying filters: {filters}")
                initial_count = len(df)
                
                if 'tournament_type' in filters:
                    if filters['tournament_type'] == '':
                        df = df[(df['tournament_type'].isnull()) | (df['tournament_type'] == '')]
                    else:
                        df = df[df['tournament_type'] == filters['tournament_type']]

                if 'tournament_level' in filters and filters['tournament_level']:
                    # Filter for tournaments with levels in the selected list
                    df = df[df['tournament_level'].str.lower().isin([level.lower() for level in filters['tournament_level']])]
                
                if 'start_date' in filters and filters['start_date']:
                    # Convert filter date to datetime for comparison
                    filter_start_date = pd.to_datetime(filters['start_date']).date()
                    # Compare only the date part
                    df = df[df['start_date'].dt.date >= filter_start_date]
                
                if 'end_date' in filters and filters['end_date']:
                    # Convert filter date to datetime for comparison
                    filter_end_date = pd.to_datetime(filters['end_date']).date()
                    # Filter tournaments that START before or on the end date
                    df = df[df['start_date'].dt.date <= filter_end_date]

                logger.debug(f"Filter reduced dataset from {initial_count} to {len(df)} tournaments")
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting tournaments from Parquet: {e}", exc_info=True)
            return pd.DataFrame()