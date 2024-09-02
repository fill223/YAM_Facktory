import os
import configparser
import requests
import json

import http.client
import json


# Загрузка конфигурации из config.ini
config = configparser.ConfigParser()
config.read('config.ini')

API_KEY = config['gologin']['api_key']
url = "https://api.gologin.com/browser/YOUR_PROFILE_ID"

conn = http.client.HTTPSConnection("api.gologin.com")
payload = ''
headers = {
  'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Njk3ZmE3YTVkNDE2NWYxODhjYTYxZTIiLCJ0eXBlIjoiZGV2Iiwiand0aWQiOiI2NmIwZTk3NWMwMThmZTc3NDZiMWVjNWMifQ.uRqwyYNtuiW2tbMa8pjgwGYrwYbo3LvITNSxnF9IWzU',
  'Content-Type': 'application/json'
}
conn.request("GET", "/browser/v2", payload, headers)
res = conn.getresponse()
data = res.read()
print(data.decode("utf-8"))