import sys
import os
import configparser
import requests
from concurrent.futures import ProcessPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from gologin import GoLogin

# Load configuration from config.ini
config = configparser.ConfigParser()
config.read('config.ini')

API_KEY = config['gologin']['api_key']
SITE_URL = config['gologin']['site_url']
BASE_URL = 'https://api.gologin.com/browser/v2'

# Logging Utilities
def suppress_gologin_logs():
    """Suppresses GoLogin logs to remove unwanted messages."""
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

def enable_logs():
    """Enables standard logging."""
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

# GoLogin API Interactions
def get_profiles(api_key):
    """Fetches the list of profiles from GoLogin using the provided API key."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.get(BASE_URL, headers=headers)
    response.raise_for_status()
    return response.json()

def start_selenium_with_profile(profile_id, api_key):
    """Starts Selenium WebDriver with a specified GoLogin profile."""
    suppress_gologin_logs()  # Suppress logs during profile start
    gl = GoLogin({
        "token": api_key,
        "profile_id": profile_id,
    })

    # Start the GoLogin profile
    debugger_address = gl.start()
    enable_logs()

    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")  # Disable GPU for headless mode
    chrome_options.add_argument("--disable-extensions")  # Disable extensions for faster loading
    chrome_options.add_experimental_option("debuggerAddress", debugger_address)

    # Specify the path to the downloaded ChromeDriver
    chrome_driver_path = 'C:\\Lichnoe\\Fucktory\\chromedriver-win64\\chromedriver.exe'
    service = ChromeService(executable_path=chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver, gl

def extract_price(driver):
    """Extracts the price from the Yandex Market page."""
    try:
        # Wait for the price element to be visible and extract the price text
        price_element = WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h3[data-auto='snippet-price-current']"))
        )
        price = price_element.text.strip()

        # Remove unwanted text like "Цена с картой Яндекс Пэй:" from the price
        unwanted_text = "Цена с картой Яндекс Пэй:"
        if unwanted_text in price:
            price = price.replace(unwanted_text, "").strip()

        # Remove unwanted text like "Цена с картой Альфа-Банка" from the price
        unwanted_text_2 = "Цена с картой Альфа-Банка"
        if unwanted_text_2 in price:
            price = price.replace(unwanted_text_2, "").strip()

        return price
    except Exception as e:
        print(f"Failed to extract price: {e}")
        return "N/A"  # Return "N/A" if the price couldn't be extracted

def run_profile(profile, api_key):
    """Runs the scraping process for a single GoLogin profile."""
    profile_id = profile['id']
    profile_name = profile['name']
    print(f"Открываю профиль {profile_name}, id {profile_id}")

    driver, gl = start_selenium_with_profile(profile_id, api_key)
    driver.get(SITE_URL)
    print("Открываю ссылку")

    # Wait for the page to load and the main content to be available
    WebDriverWait(driver, 3).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "h3[data-auto='snippet-price-current']"))
    )

    price = extract_price(driver)
    driver.quit()

    suppress_gologin_logs()  # Suppress logs during profile stop to remove unwanted messages
    gl.stop()  # This might still print something to stdout/stderr
    enable_logs()

    return {'profile_name': profile_name, 'price': price}

def run_profiles(api_key):
    """Runs the scraping process across all GoLogin profiles in parallel."""
    print("Программа запустилась")
    profiles = get_profiles(api_key)
    profile_count = len(profiles['profiles'])
    print(f"Нашел {profile_count} профилей")

    profile_data = []  # To store profile name and price

    if 'profiles' in profiles:
        # Use ProcessPoolExecutor to run multiple profiles in parallel
        with ProcessPoolExecutor(max_workers=7) as executor:  # Increased concurrency
            futures = {executor.submit(run_profile, profile, api_key): profile for profile in profiles['profiles']}
            
            for future in as_completed(futures):
                result = future.result()
                profile_data.append(result)
    else:
        print("Unexpected response structure:", profiles)

    # Display the profile data as a table
    print("\nПарсинг завершен. Результаты:")
    print("{:<20} {:<15}".format('Profile Name', 'Price'))
    print("-" * 35)
    for data in profile_data:
        print("{:<20} {:<15}".format(data['profile_name'], data['price']))

def main():
    """Main entry point for the program."""
    try:
        run_profiles(API_KEY)
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
    except Exception as err:
        print(f"An error occurred: {err}")

if __name__ == "__main__":
    main()
