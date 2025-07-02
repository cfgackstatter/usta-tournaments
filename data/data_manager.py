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

from config import TOURNAMENTS_FILE

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

                # Extract event information
                events = tournament.get('events', [])
                event_tuples = []
                for event in events:
                    division = event.get('division', {})
                    gender = division.get('gender', '')
                    event_type = division.get('eventType', '')
                    if gender and event_type:
                        event_tuples.append((gender, event_type))

                # Store unique event tuples to avoid duplicates
                unique_event_tuples = list(set(event_tuples))
                
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
                    'event_tuples': json.dumps(unique_event_tuples),
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
            
            # Define cutoff date for 7 days ago - use UTC for consistent comparison
            cutoff_date = pd.Timestamp(datetime.now() - pd.Timedelta(days=7), tz='UTC')

            # Convert end_date to datetime if it's not already
            if not pd.api.types.is_datetime64_any_dtype(df['end_date']):
                df['end_date'] = pd.to_datetime(df['end_date'], utc=True)
            else:
                # If already datetime but has timezone info, convert to UTC
                if df['end_date'].dt.tz is not None:
                    df['end_date'] = df['end_date'].dt.tz_convert('UTC')
                else:
                    # If timezone-naive, assume UTC
                    df['end_date'] = df['end_date'].dt.tz_localize('UTC')

            # Filter out tournaments that ended more than 7 days ago
            # Keep tournaments that haven't ended yet or ended within the past 7 days
            initial_count = len(df)
            df = df[(df['end_date'] >= cutoff_date) | (pd.isna(df['end_date']))]
            removed_count = initial_count - len(df)
            logger.info(f"Removed {removed_count} tournaments that ended more than 7 days ago")
            
            # Save to Parquet file
            df.to_parquet(self.tournaments_file, engine='pyarrow', index=False)

            # Create and save a slim version without the 'data' column
            slim_df = df[df['is_cancelled'] == False].drop(columns=['data', 'is_cancelled'])
            slim_file = self.tournaments_file.replace('.parquet', '_slim.parquet')
            slim_df.to_parquet(slim_file, engine='pyarrow', index=False)
            
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

            # Parse events JSON string
            if 'event_tuples' in df.columns:
                df['event_tuples'] = df['event_tuples'].apply(lambda x: json.loads(x) if pd.notna(x) else [])
            
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

                if 'event_gender' in filters and filters['event_gender']:
                    df = self.filter_by_event(df, gender=filters['event_gender'], event_type=filters.get('event_type'))
                elif 'event_type' in filters and filters['event_type']:
                    df = self.filter_by_event(df, event_type=filters['event_type'])
                
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

            if 'start_date' in df.columns and not df.empty:
                df = df.sort_values(by='start_date', ascending=True)
                logger.debug("Sorted tournaments by start date (ascending)")
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting tournaments from Parquet: {e}", exc_info=True)
            return pd.DataFrame()
        
    def filter_by_event(self, df: pd.DataFrame, gender: Optional[str] = None, event_type: Optional[str] = None) -> pd.DataFrame:
        """
        Filter tournaments by event criteria (gender and/or event type).
        
        Args:
            df: DataFrame containing tournament data
            gender: Gender filter (e.g., 'Male', 'Female', 'Mixed')
            event_type: Event type filter (e.g., 'Singles', 'Doubles')
            
        Returns:
            Filtered DataFrame
        """
        if not gender and not event_type:
            return df
            
        if 'event_tuples' not in df.columns:
            logger.warning("event_tuples column not found in DataFrame")
            return df
            
        if gender and event_type:
            # Filter for tournaments with events matching both gender and event_type
            mask = df['event_tuples'].apply(lambda tuples: any(t[0] == gender and t[1] == event_type for t in tuples))
        elif gender:
            # Filter for tournaments with events matching gender
            mask = df['event_tuples'].apply(lambda tuples: any(t[0] == gender for t in tuples))
        else:  # event_type only
            # Filter for tournaments with events matching event_type
            mask = df['event_tuples'].apply(lambda tuples: any(t[1] == event_type for t in tuples))
            
        return df[mask]