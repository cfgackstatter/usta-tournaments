"""
Web application module for USTA Tournament Map.

This module provides a Streamlit-based web interface for browsing and filtering
USTA tournament data on an interactive map.
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import pandas as pd
import json
import pytz

from data.data_manager import DataManager

# Configure logger
logger = logging.getLogger(__name__)

display_names = {
    # Tournament types
    "adult": "Adult",
    "junior": "Junior",
    "wheelchair": "Wheelchair",
    "wtnPlay": "WTN",
    "": "<Empty>",

    # Event genders
    "boys": "Men/Boys",
    "girls": "Women/Girls",
    "coed": "Coed",
    "mixed": "Mixed",

    # Event types
    "singles": "Singles",
    "doubles": "Doubles",
    "team": "Team",

    # Special case for "All" option
    "All": "All"
}

def load_css(css_file_path):
    """
    Load CSS from a file and inject it into the Streamlit app.
    
    Args:
        css_file_path: Path to the CSS file
        
    Returns:
        None
    """
    with open(css_file_path, "r") as f:
        css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

class TournamentApp:
    """
    Web application for displaying USTA tournaments on an interactive map.
    
    This class handles the Streamlit web interface, including filters, map display,
    and tournament listings.
    """
    def __init__(self) -> None:
        """Initialize the tournament application with a data manager."""
        self.data_manager = DataManager()
        logger.debug("TournamentApp initialized")
    
    def run(self) -> None:
        """
        Run the Streamlit web application.
        
        Sets up the page layout, filters, map, and tournament table.
        
        Returns:
            None
        """
        # Configure page settings with responsive layout
        st.set_page_config(
            page_title="USTA Tournament Map",
            page_icon="🎾",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # Load CSS from external file
        load_css("static/style.css")
        
        st.title("🎾 USTA Tournaments")
        
        # Process filters and load data
        filters, tournaments_df = self._handle_filters()
        
        # Display map and tournament table
        self._display_map(tournaments_df)
        self._display_tournament_table(tournaments_df)
    
    def _handle_filters(self) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """
        Handle filter controls and load filtered tournament data.
        
        Creates sidebar filter controls, processes user selections, and loads
        the filtered tournament data.
        
        Returns:
            Tuple containing the filter dictionary and filtered DataFrame
        """
        filters = {}
        
        # Add filters in the sidebar
        with st.sidebar:            
            # Date range filter
            st.subheader("Start Date")
            date_col1, date_col2 = st.columns(2)

            with date_col1:
                today = datetime.now()
                start_date = st.date_input(
                    "From",
                    today
                )

            with date_col2:
                end_date = st.date_input(
                    "To",
                    today + timedelta(days=30)
                )
            
            # Initialize filters with date range
            if start_date:
                filters['start_date'] = start_date
                logger.debug(f"Added start_date filter: {start_date}")
            if end_date:
                filters['end_date'] = end_date
                logger.debug(f"Added end_date filter: {end_date}")
            
            # Get tournaments from Parquet file first to extract types
            initial_df = self.data_manager.get_tournaments(filters, use_slim=True)
            logger.debug(f"Loaded {len(initial_df)} tournaments for type filtering")
            
            # Get unique tournament types from the loaded data
            if not initial_df.empty and 'tournament_type' in initial_df.columns:
                # Extract unique values and sort them
                unique_types = sorted(initial_df['tournament_type'].unique())
                tournament_types = ["All"] + [t_type for t_type in unique_types]
                logger.debug(f"Found tournament types: {unique_types}")
            else:
                # Fallback if no data is available
                tournament_types = ["All", "Adult", "Junior", "Wheelchair"]
                logger.debug("Using default tournament types")
            
            # Tournament type filter
            st.subheader("Category")
            selected_type = st.selectbox(
                "Select Category",
                tournament_types,
                format_func=lambda x: display_names.get(x, x)
            )
            
            # Update filters with selected type
            if selected_type == "":
                filters['tournament_type'] = ''
            elif selected_type and selected_type != "All":
                filters['tournament_type'] = selected_type
                logger.debug(f"Added tournament_type filter: {selected_type}")

            # Get unique tournament levels
            if not initial_df.empty and 'tournament_level' in initial_df.columns:
                # Extract unique values and sort them
                unique_levels = sorted([level for level in initial_df['tournament_level'].unique() if pd.notna(level)])
                levels_for_display = [level for level in unique_levels]
            else:
                # Fallback if no data is available
                unique_levels = []
                levels_for_display = []

            # Initialize session state for selected levels if not already present
            if 'selected_levels' not in st.session_state:
                st.session_state.selected_levels = []

            # Tournament level filter (multi-select)
            if levels_for_display:
                st.subheader("Level")

                selected_levels = st.multiselect(
                    "Select Levels",
                    options=levels_for_display,
                    default=st.session_state.selected_levels,
                    key="tournament_levels"
                )

                # Update session state with current selection
                st.session_state.selected_levels = selected_levels

                # Update filters with selected levels
                if selected_levels and len(selected_levels) < len(levels_for_display):
                    # Only add filter if not all levels are selected
                    filters['tournament_level'] = selected_levels
                    logger.debug(f"Added tournament_level filter: {selected_levels}")

            # Get unique event genders and types
            event_genders = set()
            event_types = set()

            if not initial_df.empty and 'event_tuples' in initial_df.columns:
                for tuples in initial_df['event_tuples']:
                    for gender, event_type in tuples:
                        if gender:
                            event_genders.add(gender)
                        if event_type:
                            event_types.add(event_type)

            # Event filters
            st.subheader("Event Filters")
            col1, col2 = st.columns(2)

            with col1:
                # Format the gender options using the display dictionary
                gender_options = ["All"] + sorted(list(event_genders))
                selected_gender = st.selectbox(
                    "Gender",
                    gender_options,
                    format_func=lambda x: display_names.get(x.lower(), x)
                )
                
                if selected_gender != "All":
                    filters['event_gender'] = selected_gender

            with col2:
                # Format the event type options using the display dictionary
                event_type_options = ["All"] + sorted(list(event_types))
                selected_event_type = st.selectbox(
                    "Event Type",
                    event_type_options,
                    format_func=lambda x: display_names.get(x.lower(), x)
                )
                
                if selected_event_type != "All":
                    filters['event_type'] = selected_event_type
        
        # Get tournaments with all filters applied
        tournaments_df = self.data_manager.get_tournaments(filters, use_slim=True)
        logger.info(f"Loaded {len(tournaments_df)} tournaments with filters: {filters}")
        
        return filters, tournaments_df
    
    def _display_map(self, tournaments_df: pd.DataFrame) -> None:
        """
        Display an interactive map with tournament markers.
        
        Args:
            tournaments_df: DataFrame containing tournament data
            
        Returns:
            None
        """        
        # Create map centered on US with responsive sizing
        map_height = 500
        m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)
        
        # Add marker cluster for better performance with many markers
        marker_cluster = MarkerCluster().add_to(m)
        
        # Add markers for each tournament
        if not tournaments_df.empty:
            marker_count = 0
            for _, row in tournaments_df.iterrows():
                if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                    # Format dates (date only, no time or timezone)
                    start_date = self._format_date_only(row['start_date'])
                    end_date = self._format_date_only(row['end_date'])
                    
                    # Load tournament type
                    tournament_type = row.get('tournament_type', '')
                    tournament_type_display = display_names.get(tournament_type, tournament_type)

                    # Get tournament URL and full location
                    tournament_url = row.get('tournament_url', '#')
                    full_location = row.get('full_location', row['location'])

                    # Check registration status
                    is_closed = self._is_registration_closed(
                        row.get('entries_close_datetime'), 
                        row.get('registration_timezone')
                    )

                    # Set marker color based on registration status
                    marker_color = 'orange' if is_closed else 'green'

                    # Add registration status to popup
                    registration_status = "Registration Closed" if is_closed else "Registration Open"
                    
                    # Create popup content with clickable link
                    popup_content = f"""
                    <h4><a href="{tournament_url}" target="_blank">{row['name']}</a></h4>
                    <b>Starts:</b> {start_date}<br>
                    <b>Ends:</b> {end_date}<br>
                    <b>Location:</b> {full_location}<br>
                    <b>Type:</b> {tournament_type_display.replace('<','&lt;').replace('>','&gt;')}<br>
                    <b>Level:</b> {row.get('tournament_level', '')}<br>
                    <b>Status:</b> {registration_status}<br>
                    """
                    
                    # Add marker
                    folium.Marker(
                        location=[row['latitude'], row['longitude']],
                        popup=folium.Popup(popup_content, max_width=300),
                        icon=folium.Icon(color=marker_color, icon='info-sign')
                    ).add_to(marker_cluster)
                    marker_count += 1
            
            logger.info(f"Added {marker_count} markers to map")
        
        # Get the HTML representation of the map
        map_html = m._repr_html_()
        
        # Create a responsive wrapper with custom CSS
        html = f"""
        <style>
        .folium-map {{
            width: 100%;
            height: {map_height}px;
            margin: 0 auto;
        }}
        </style>
        <div class="folium-map">
            {map_html}
        </div>
        """
        
        # Use the HTML component for full width
        st.components.v1.html(html, height=map_height+10)
    
    def _display_tournament_table(self, tournaments_df: pd.DataFrame) -> None:
        """
        Display a table of tournaments below the map.
        
        Args:
            tournaments_df: DataFrame containing tournament data
            
        Returns:
            None
        """
        if not tournaments_df.empty:
            # Create a copy of the dataframe for display
            display_df = tournaments_df.copy()
            
            # Format dates (date only)
            display_df['start_date'] = display_df['start_date'].apply(self._format_date_only)
            display_df['end_date'] = display_df['end_date'].apply(self._format_date_only)

            # Cast tournament names to ASCII to prevent rendering issues
            if 'name' in display_df.columns:
                display_df['name'] = display_df['name'].apply(lambda x: x.encode('ascii', 'ignore').decode('ascii') if isinstance(x, str) else x)

            # Apply the display mapping to tournament_type
            display_df['tournament_type_display'] = display_df['tournament_type'].apply(
                lambda x: display_names.get(x, x) if pd.notna(x) else ''
            )

            # Create clickable links for tournament names
            display_df['name'] = display_df.apply(
                lambda row: f'<a href="{row["tournament_url"]}" target="_blank">{row["name"]}</a>' 
                if pd.notna(row["tournament_url"]) else row["name"], 
                axis=1
            )

            if 'start_date' in display_df.columns and not display_df.empty:
                # Convert back to datetime for proper sorting (since we formatted it as string earlier)
                temp_start_dates = pd.to_datetime(display_df['start_date'])
                display_df = display_df.iloc[temp_start_dates.argsort()]

            # Create final display dataframe
            final_df = display_df[['name', 'start_date', 'end_date', 'full_location', 'tournament_type_display', 'tournament_level']]
            
            # Rename columns for display
            final_df = final_df.rename(columns={
                'name': 'Name',
                'start_date': 'Start Date',
                'end_date': 'End Date',
                'full_location': 'Location',
                'tournament_type_display': 'Type',
                'tournament_level': 'Level'
            })

            # # Ensure dates are properly formatted as strings without problematic characters
            # if 'start_date' in final_df.columns:
            #     final_df['start_date'] = final_df['start_date'].apply(
            #         lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else ''
            #     )
                
            # if 'end_date' in final_df.columns:
            #     final_df['end_date'] = final_df['end_date'].apply(
            #         lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else ''
            #     )
            
            # Display the dataframe with HTML rendering enabled
            st.write(final_df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.info("No tournaments found with the current filters.")
    
    @staticmethod
    def _format_date_only(dt_value: Any) -> str:
        """
        Format a datetime value as date only (YYYY-MM-DD).
        
        Args:
            dt_value: Datetime value to format
            
        Returns:
            Formatted date string
        """
        if pd.notna(dt_value):
            try:
                dt = pd.to_datetime(dt_value)
                return dt.strftime('%Y-%m-%d')
            except Exception as e:
                logger.error(f"Error formatting date {dt_value}: {e}")
                return str(dt_value)
        return 'N/A'
    
    def _is_registration_closed(self, close_datetime, timezone_str: str) -> bool:
        """
        Check if registration is closed based on close datetime and timezone.
        
        Args:
            close_datetime: The datetime when registration closes
            timezone_str: The timezone of the close datetime
            
        Returns:
            True if registration is closed, False otherwise
        """
        if not close_datetime or pd.isna(close_datetime):
            return False
            
        try:
            # Parse the close datetime
            close_dt = pd.to_datetime(close_datetime)
            
            # Get the current time in Eastern timezone
            eastern_tz = pytz.timezone('US/Eastern')
            current_time = datetime.now(eastern_tz)
            
            # Convert close datetime to timezone-aware datetime
            if timezone_str:
                try:
                    # Try to use the provided timezone
                    tz = pytz.timezone(timezone_str)
                    close_dt = close_dt.replace(tzinfo=tz)
                except pytz.exceptions.UnknownTimeZoneError:
                    # Fall back to UTC if timezone is unknown
                    close_dt = close_dt.replace(tzinfo=pytz.UTC)
            else:
                # Default to UTC if no timezone provided
                close_dt = close_dt.replace(tzinfo=pytz.UTC)
                
            # Compare with current Eastern time
            return close_dt < current_time
            
        except Exception as e:
            logger.error(f"Error checking registration status: {e}")
            return False