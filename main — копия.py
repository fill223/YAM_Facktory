import os
import sys
import re
import requests
import configparser
import logging
from sys import platform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from gologin import GoLogin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration from config.ini
config = configparser.ConfigParser()
config.read('config.ini')

API_KEY = config['gologin']['api_key']
SITE_URL = config['gologin']['site_url']
BASE_URL = 'https://api.gologin.com/browser/v2'

def suppress_gologin_logs():
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

def enable_logs():
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

def get_profiles(api_key):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.get(BASE_URL, headers=headers)
    response.raise_for_status()
    return response.json()

def start_selenium_with_profile(profile_id, api_key):
    suppress_gologin_logs()
    gl = GoLogin({
        "token": api_key,
        "profile_id": profile_id,
    })

    debugger_address = gl.start()
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", debugger_address)

    # Specify the absolute path to the ChromeDriver
    chrome_driver_path = r'C:\Lichnoe\Fucktory\chromedriver-win64\chromedriver.exe'
    service = ChromeService(executable_path=chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    enable_logs()
    return driver, gl

def extract_price(text):
    numbers = re.findall(r'\d+', text)
    return int(''.join(numbers))

def check_out_of_stock(driver):
    """Check if the 'Товар разобрали' message appears."""
    try:
        out_of_stock_message = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Увы, товары разобрали')]"))
        )
        logging.info('Out of stock: товары разобрали')
        return True  # The item is out of stock
    except TimeoutException:
        return False  # No out-of-stock message, proceed with other actions

def handle_purchase(driver):
    try:
        buy_now_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-auto='default-offer-buy-now-button']"))
        )
        buy_now_button.click()
        logging.info('Clicked "Buy Now" button')

    except (NoSuchElementException, TimeoutException):
        try:
            cart_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-auto='counter-cart-button-go-to-cart-link']"))
            )
            cart_button.click()
            logging.info('Buy Now button not found, navigating to the cart')

            checkout_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-auto='cartCheckoutButton']"))
            )
            checkout_button.click()
            logging.info('Clicked "Checkout" button')

        except (NoSuchElementException, TimeoutException) as e:
            logging.error(f"Failed to proceed to checkout: {e}")
            return False

    # After clicking "Buy Now" or "Checkout", check for the out-of-stock message
    if check_out_of_stock(driver):
        logging.info('Stopping process: Item is out of stock')
        return False

    return True

def calculate_prices(driver):
    try:
        # Check again for the out-of-stock message before retrieving prices
        if check_out_of_stock(driver):
            logging.info("Товар разобрали")
            return  # Stop if items are out of stock

        yandex_discount = 0
        alfa_discount = 0

        try:
            yandex_discount_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, 
                "//span[contains(text(),'яндекс пэй')]/ancestor::div[contains(@class, '_3VBOg')]//span[@data-auto='price']"))
            )
            yandex_discount = extract_price(yandex_discount_element.text)
        except TimeoutException:
            logging.info("Yandex Pay discount not found.")

        try:
            alfa_discount_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, 
                "//span[contains(text(),'альфа банка')]/ancestor::div[contains(@class, '_3VBOg')]//span[@data-auto='price']"))
            )
            alfa_discount = extract_price(alfa_discount_element.text)
        except TimeoutException:
            logging.info("Alfa Bank discount not found.")

        final_price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[@data-baobab-name='totalPrice']"))
        )
        final_price = extract_price(final_price_element.text)

        selected_discount = yandex_discount if yandex_discount else alfa_discount
        raw_price = final_price + selected_discount

        logging.info(f"Raw Price: {raw_price} ₽")
        logging.info(f"With Yandex Pay: {raw_price - yandex_discount} ₽")
        logging.info(f"With Alfa: {raw_price - alfa_discount} ₽")
    except Exception as e:
        logging.error(f"Failed to retrieve prices: {e}")

def run_profiles(api_key):
    logging.info("Program started")
    profiles = get_profiles(api_key)
    profile_count = len(profiles.get('profiles', []))
    logging.info(f"Found {profile_count} profiles")

    if 'profiles' in profiles:
        for profile in profiles['profiles']:
            profile_id = profile['id']
            profile_name = profile['name']
            logging.info(f"Opening profile {profile_name}, ID: {profile_id}")

            driver = None
            gl = None
            try:
                driver, gl = start_selenium_with_profile(profile_id, api_key)
                driver.get(SITE_URL)
                logging.info("Navigated to the site URL")
                
                if handle_purchase(driver):
                    if not check_out_of_stock(driver):  # Check again before getting prices
                        calculate_prices(driver)
                    else:
                        logging.info("Товар разобрали")
                else:
                    logging.warning(f"Purchase failed for profile {profile_name}")
            except Exception as e:
                logging.error(f"An error occurred: {e}")
            finally:
                if driver:
                    driver.quit()
                if gl:
                    gl.stop()
    else:
        logging.error(f"Unexpected response structure: {profiles}")

def main():
    try:
        run_profiles(API_KEY)
    except requests.exceptions.HTTPError as err:
        logging.error(f"HTTP error occurred: {err}")
    except Exception as err:
        logging.error(f"An error occurred: {err}")

if __name__ == "__main__":
    main()
