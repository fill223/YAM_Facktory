import time
from sys import platform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from gologin import GoLogin
import configparser
import requests
import re
import sys
import os

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
    
    # Specify the path to the downloaded ChromeDriver
    chrome_driver_path = 'C:\\Lichnoe\\Fucktory\\chromedriver-win64\\chromedriver.exe'
    service = ChromeService(executable_path=chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    enable_logs()
    return driver, gl

def extract_price(text):
    numbers = re.findall(r'\d+', text)
    return int(''.join(numbers))

def run_profiles(api_key):
    print("Программа запустилась")
    profiles = get_profiles(api_key)
    profile_count = len(profiles['profiles'])
    print(f"Нашел {profile_count} профилей")

    if 'profiles' in profiles:
        for profile in profiles['profiles']:
            profile_id = profile['id']
            profile_name = profile['name']
            print(f"Открываю профиль {profile_name}, id {profile_id}")
            driver, gl = start_selenium_with_profile(profile_id, api_key)
            driver.get(SITE_URL)
            print("Открываю ссылку")
            time.sleep(5)
            
            try:
                # Шаг 1: Проверка наличия кнопки "Купить сейчас"
                try:
                    buy_now_button = driver.find_element("css selector", "button[data-auto='default-offer-buy-now-button']")
                    print('Кнопка "Купить сейчас" найдена')
                    
                    # Шаг 2: Нажимаем кнопку "Купить сейчас"
                    buy_now_button.click()
                    print('Нажал кнопку "Купить сейчас"')

                except:
                    print('Кнопка "Купить сейчас" не найдена, проверяю количество товара в корзине')
                    
                    # Шаг 3: Проверяем количество товара в корзине
                    try:
                        # Попробуем другой подход с использованием селекторов по data-autotest-id
                        quantity_element = driver.find_element("xpath", "//a[@data-autotest-id='counter']")
                        current_quantity = int(quantity_element.text.strip())
                        print(f"Товар уже в корзине в количестве {current_quantity}. Уменьшаем до нуля.")
                        
                        # Шаг 4: Уменьшаем количество товара до нуля
                        decrease_button = driver.find_element("xpath", "//div[@data-baobab-name='decrease']//button[@data-autotest-id='decrease']")
                        while current_quantity > 0:
                            decrease_button.click()
                            current_quantity -= 1
                            time.sleep(1)  # Ждем обновления количества
                        print("Количество уменьшено до нуля.")
                        
                        # Шаг 5: Повторное нажатие на кнопку "Купить сейчас"
                        buy_now_button = driver.find_element("css selector", "button[data-auto='default-offer-buy-now-button']")
                        buy_now_button.click()
                        print('Нажал кнопку "Купить сейчас" после уменьшения количества')
                    
                    except Exception as e:
                        print(f"Ошибка при уменьшении количества или нажатии на кнопку 'Купить сейчас': {e}")

            except Exception as e:
                print(f"Ошибка при обработке товара: {e}")
            time.sleep(5)
            
            try:
                yandex_discount = 0
                alfa_discount = 0

                try:
                    yandex_discount_element = driver.find_element("xpath", "//span[contains(text(),'яндекс пэй')]/ancestor::div[contains(@class, '_3VBOg')]//span[@data-auto='price']")
                    yandex_discount = extract_price(yandex_discount_element.text)
                except:
                    print("Yandex Pay discount not found.")
                
                try:
                    alfa_discount_element = driver.find_element("xpath", "//span[contains(text(),'альфа банка')]/ancestor::div[contains(@class, '_3VBOg')]//span[@data-auto='price']")
                    alfa_discount = extract_price(alfa_discount_element.text)
                except:
                    print("Alfa Bank discount not found.")
                
                # Get the final price (big green text)
                final_price_element = driver.find_element("xpath", "//div[@data-baobab-name='totalPrice']")
                final_price = extract_price(final_price_element.text)
                
                # Calculate Raw Price
                selected_discount = yandex_discount if yandex_discount else alfa_discount
                raw_price = final_price + selected_discount

                print(f"Профиль {profile_name}, цены:")
                print(f"Без скидки: {raw_price} ₽")
                print(f"Яндекс.Пэй: {raw_price - yandex_discount} ₽")
                print(f"Alfa: {raw_price - alfa_discount} ₽")
            except Exception as e:
                print(f"Failed to retrieve prices: {e}")

            driver.quit()
            suppress_gologin_logs()
            gl.stop()
            enable_logs()
    else:
        print("Unexpected response structure:", profiles)

def main():
    try:
        run_profiles(API_KEY)
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
    except Exception as err:
        print(f"An error occurred: {err}")

if __name__ == "__main__":
    main()
