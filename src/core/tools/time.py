
from datetime import datetime
from zoneinfo import ZoneInfo

def get_datetime(timezone: str) -> str:
    """
    Returns the current localized datetime for a given IANA time zone name,
    correctly accounting for DST transitions.

    :param timezone_name: The full IANA name of the time zone (e.g., "America/Vancouver").
    :return: Formatted string of the current date, time, and timezone name.
    """
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S") + f" ({timezone})"
    except Exception as e:
        return f"ERROR: Error fetching time for {timezone}: {e}"
    
get_datetime_config = {
        "type": "function",
        "function": {
            "name": "get_datetime",
            "description": "Returns the current, localized date and time for a given time zone name, correctly accounting for Daylight Saving Time (DST) and all time zone rules.",
            "parameters": {
                'type': 'object',
                'properties': {
                    'timezone': {
                        'type': 'string',
                        "description": "The full IANA time zone name (e.g., 'America/Los_Angeles', 'Europe/London', 'Asia/Tokyo'). This name allows the function to correctly calculate DST shifts."
                    }
                },
                'required': ['timezone'] 
            }
        }
    }