"""This module handles all Daily REST API operations."""
import dataclasses
import datetime
import json

import requests

DAILY_API_URL_DEFAULT = 'https://api.daily.co/v1'


@dataclasses.dataclass
class Recording:
    """Class that represents a single Daily recording"""
    id: str
    room_name: str
    timestamp: datetime.datetime


def fetch_recordings(api_key: str, api_url: str = DAILY_API_URL_DEFAULT,
                     room_name: str = None, limit: int = None):
    """Fetches all Daily recordings is a Daily API key is configured"""
    if not api_key:
        raise Exception("Daily API key not configured in server environment")

    headers = {'Authorization': f'Bearer {api_key}'}
    url = f'{api_url}/recordings'

    params = {}
    if room_name is not None:
        params["room_name"] = room_name
    if limit > 0:
        params["limit"] = limit

    print("Daily query url:", url, params)
    res = requests.get(url, params=params, headers=headers, timeout=5)
    if not res.ok:
        raise Exception(
            f'Failed to fetch recordings; return code {res.status_code}; {res.text}')
    data = json.loads(res.text)
    recordings = data['data']
    finished_recordings = []
    for r in recordings:
        start = r['start_ts']
        duration = r['duration']
        d = datetime.datetime.fromtimestamp(start)
        timestamp = d + datetime.timedelta(0, duration)
        recording = Recording(r['id'], r['room_name'], timestamp)
        finished_recordings.append(recording)
    return finished_recordings


def get_access_link(api_key: str, recording_id: str,
                    api_url: str = DAILY_API_URL_DEFAULT) -> str:
    """Fetches access link for provided Daily recording ID"""
    if not api_key:
        raise Exception("Daily API key not configured in server environment")

    url = f'{api_url}/recordings/{recording_id}/access-link'
    headers = {'Authorization': f'Bearer {api_key}'}

    res = requests.get(url, headers=headers, timeout=5)
    if not res.ok:
        raise Exception(
            f'Failed to get recording access link; return code {res.status_code}')
    data = json.loads(res.text)
    download_link = data['download_link']
    return download_link
