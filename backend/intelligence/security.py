import hmac
import ipaddress
import os
import socket
from urllib.parse import urlsplit
import httpx
from fastapi import Header, HTTPException


def authenticate(authorization: str = Header(default='')):
    token = os.getenv('APP_TOKEN', '')
    if len(token) < 32:
        raise HTTPException(503, 'Set APP_TOKEN to a random secret of at least 32 characters')
    if not hmac.compare_digest(authorization, 'Bearer '+token):
        raise HTTPException(401, 'Authentication required')


def approved_url(url, domains):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Only public HTTPS URLs are allowed')
    host = parsed.hostname or ''
    if host not in domains:
        raise ValueError('Domain is not approved')
    addresses = socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Private network destinations are forbidden')
    return url


def retrieve(url, domains):
    approved_url(url, domains)
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        with client.stream('GET',url,headers={'User-Agent':'MyIntelligence/0.1'}) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content)>2_000_000:
                    raise ValueError('Source exceeds 2 MB limit')
            return bytes(content)
