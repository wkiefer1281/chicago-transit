# backend/utilities/http.py
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_RETRY = Retry(
    total=3,
    backoff_factor=1.0,  # 0s, 2s, 4s between attempts
    status_forcelist=(500, 502, 503, 504),
    allowed_methods=("GET",),
)


def get(url: str, *, timeout: float, **kwargs) -> requests.Response:
    """GET with retries on transient server errors (Metra in particular flakes with 5xx)."""
    with requests.Session() as session:
        adapter = HTTPAdapter(max_retries=_RETRY)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        response = session.get(url, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response
