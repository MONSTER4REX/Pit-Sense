import logging
import os
from typing import Dict, Any, List
import pandas as pd

logger = logging.getLogger(__name__)

_session_cache = None

def get_fastf1_session():
    global _session_cache
    if _session_cache is None:
        try:
            import fastf1
            cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'fastf1_cache')
            os.makedirs(cache_dir, exist_ok=True)
            fastf1.Cache.enable_cache(cache_dir)
            logger.info("Loading FastF1 session (2024 Belgian GP)...")
            session = fastf1.get_session(2024, 'Belgium', 'R')
            # Load with telemetry for DistanceToDriverAhead
            session.load(telemetry=True, weather=False, messages=False)
            _session_cache = session
            logger.info("FastF1 session loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load FastF1 session: {e}")
            raise
    return _session_cache

def extract_lap_dynamic_data(lap_number: int, main_driver: str = 'NOR', rival_driver: str = 'VER') -> Dict[str, Any]:
    """
    Extracts dynamic data from the FastF1 session for a given lap:
    - DistanceToDriverAhead (avg for the lap from telemetry)
    - Rival tyre age
    - Gaps to cars ahead (for traffic penalty)
    """
    try:
        session = get_fastf1_session()
    except Exception as exc:
        logger.warning("FastF1 live enrichment unavailable for lap %s: %s", lap_number, exc)
        return {
            'rival_tyre_age': 0,
            'distance_to_driver_ahead': 0.0,
            'gaps_to_ahead': [],
            'pit_time_loss': 22.0,
        }
    laps = session.laps
    
    # 1. Rival Tyre Age
    rival_tyre_age = 0
    rival_laps = laps.pick_driver(rival_driver)
    rival_lap = rival_laps[rival_laps['LapNumber'] == lap_number]
    if not rival_lap.empty:
        val = rival_lap.iloc[0]['TyreLife']
        if pd.notna(val):
            rival_tyre_age = int(val)
            
    # 2. Distance to Driver Ahead
    main_laps = laps.pick_driver(main_driver)
    main_lap = main_laps[main_laps['LapNumber'] == lap_number]
    dist_ahead = 0.0
    if not main_lap.empty:
        try:
            tel = main_lap.iloc[0].get_telemetry()
            if 'DistanceToDriverAhead' in tel.columns:
                val = tel['DistanceToDriverAhead'].replace([float('inf'), -float('inf')], pd.NA).dropna().mean()
                if pd.notna(val):
                    dist_ahead = float(val)
        except Exception as e:
            logger.warning(f"Could not get telemetry for lap {lap_number}: {e}")

    # 3. Gaps to cars ahead
    # Find cars ahead of main_driver
    gaps_to_ahead: List[float] = []
    if not main_lap.empty:
        my_pos = main_lap.iloc[0]['Position']
        my_time = main_lap.iloc[0]['Time']
        if pd.notna(my_pos) and pd.notna(my_time):
            lap_all = laps[laps['LapNumber'] == lap_number]
            ahead_cars = lap_all[lap_all['Position'] < my_pos]
            for _, row in ahead_cars.iterrows():
                t = row['Time']
                if pd.notna(t):
                    gap = (my_time - t).total_seconds()
                    gaps_to_ahead.append(gap)
    
    # Ensure gaps is sorted
    gaps_to_ahead.sort()
    
    return {
        'rival_tyre_age': rival_tyre_age,
        'distance_to_driver_ahead': dist_ahead,
        'gaps_to_ahead': gaps_to_ahead,
        'pit_time_loss': 22.0  # Dynamic pit loss could be calculated, fallback to 22.0
    }
