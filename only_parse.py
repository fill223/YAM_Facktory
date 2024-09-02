import os
import configparser
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from gologin import GoLogin
import shutil
import re

# Загрузка конфигурации из config.ini
config = configparser.ConfigParser()
config.read('config.ini')

API_KEY = config['gologin']['api_key']
SITE_URL = config['gologin']['site_url']
BASE_URL = 'https://api.gologin.com/browser/v2'

def get_profiles(api_key):
    """Получает список профилей из GoLogin с использованием предоставленного API ключа."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(BASE_URL, headers=headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return None

    return response.json()

def start_selenium_with_profile(profile_id, api_key):
    """Запускает Selenium WebDriver с указанным профилем GoLogin в headless режиме."""
    try:
        gl = GoLogin({
            "token": api_key,
            "profile_id": profile_id,
            "extra_params": {
                "autoHeadless": True  # Включаем headless режим через GoLogin API
            }
        })

        # Запускаем профиль GoLogin и получаем адрес отладчика
        debugger_address = gl.start()
        print(f"Started GoLogin profile {profile_id} with debugger address: {debugger_address}")

        # Настройка Chrome options для headless режима
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Включаем headless режим
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)

        # Используем уникальную временную директорию данных пользователя для каждого экземпляра
        temp_user_data_dir = os.path.join('C:\\TempProfiles', f"chrome_profile_{profile_id}")
        os.makedirs(temp_user_data_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={temp_user_data_dir}")

        # Указываем путь к загруженному ChromeDriver
        chrome_driver_path = 'C:\\Lichnoe\\Fucktory\\chromedriver-win64\\chromedriver.exe'
        service = ChromeService(executable_path=chrome_driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Вывод информации о состоянии окна браузера
        print(f"Initial window handles for profile {profile_id}: {driver.window_handles}")

        return driver, gl, temp_user_data_dir

    except Exception as e:
        print(f"Failed to start Selenium WebDriver for profile {profile_id}: {e}")
        raise

def extract_price(driver):
    """Извлекает цену с текущей страницы."""
    try:
        price_element = WebDriverWait(driver, 10, poll_frequency=0.2).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h3[data-auto='snippet-price-current']"))
        )
        price = price_element.text.strip()
        price = re.sub(r'[^\d,]', '', price)  # Удаляем все, кроме цифр и запятых
        price_float = float(price.replace(',', '.'))

        return price_float
    except Exception as e:
        print(f"Failed to extract price: {e}")
        return float('inf')  # Используем 'inf' для невозможных цен

def extract_prices_from_pickup_points(driver):
    """Извлекает цены из всех доступных пунктов самовывоза."""
    try:
        # Сначала получаем цену для текущего выбранного пункта самовывоза
        lowest_price = extract_price(driver)

        # Открыть меню пунктов выдачи
        pickup_menu_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".class_name_for_pickup_menu_button"))
        )
        pickup_menu_button.click()
        print("Pickup menu opened successfully.")

        # Найти все пункты самовывоза с использованием атрибута 'data-baobab-name="deliveryPoint"'
        pickup_points = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-baobab-name='deliveryPoint']"))
        )

        for index, point in enumerate(pickup_points):
            try:
                point.click()  # Переключиться на этот пункт выдачи
                print(f"Clicked on pickup point {index + 1}.")

                # Подождать обновления страницы и снова получить цену
                price = extract_price(driver)
                print(f"Price for pickup point {index + 1}: {price}")

                if price < lowest_price:
                    lowest_price = price

                # Снова открыть меню пунктов выдачи после обновления страницы
                pickup_menu_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".class_name_for_pickup_menu_button"))
                )
                pickup_menu_button.click()
                print("Reopened pickup menu.")

            except Exception as e:
                print(f"Failed to extract price from pickup point: {e}")
                continue

        return lowest_price
    except Exception as e:
        print(f"Failed to extract prices from pickup points: {e}")
        return float('inf')  # Если не удалось извлечь цены, используем 'inf'

def cleanup(temp_user_data_dir):
    """Очищает временные директории."""
    try:
        shutil.rmtree(temp_user_data_dir)
    except Exception as e:
        print(f"Failed to remove temporary directory: {e}")

def run_profile(profile, api_key):
    """Выполняет процесс парсинга для одного профиля GoLogin."""
    profile_id = profile['id']
    profile_name = profile['name']
    print(f"Processing profile: {profile_name}")

    try:
        driver, gl, temp_user_data_dir = start_selenium_with_profile(profile_id, api_key)
        try:
            print(f"Opening {SITE_URL} for profile: {profile_name}")
            driver.get(SITE_URL)

            # Извлечение лучшей цены из пунктов самовывоза
            best_price = extract_prices_from_pickup_points(driver)
            print(f"Best price extracted for profile {profile_name}: {best_price}")

        except Exception as e:
            print(f"Error during page interaction for profile {profile_name}: {e}")
            best_price = float('inf')  # Если не удалось извлечь цену, используем 'inf'
        finally:
            # Закрытие ресурсов и очистка
            driver.quit()
            gl.stop()
            cleanup(temp_user_data_dir)

    except Exception as e:
        print(f"Error setting up Selenium for profile {profile_name}: {e}")
        best_price = float('inf')  # Используем 'inf' для невозможных цен

    return {'profile_name': profile_name, 'best_price': best_price}

def run_profiles_sequentially(api_key, max_profiles=5):
    """Выполняет процесс парсинга последовательно по всем профилям GoLogin."""
    print("Starting the program...")

    profiles_data = get_profiles(api_key)
    if profiles_data is None:
        print("Failed to fetch profiles. Exiting.")
        return

    if 'profiles' in profiles_data:
        profiles = profiles_data['profiles']
        profile_count = len(profiles)
        print(f"Found {profile_count} profiles")

        if max_profiles is not None:
            profiles = profiles[:max_profiles]

        profile_data = []  # Сохранение данных профиля и цены

        for profile in profiles:
            result = run_profile(profile, api_key)
            profile_data.append(result)

        # Сортировка результатов по цене от самой дешевой до самой дорогой
        profile_data = sorted(profile_data, key=lambda x: x['best_price'])

    else:
        print("Unexpected response structure:", profiles_data)
        return

    print("\nParsing complete. Results (sorted by best price):")
    print("{:<20} {:<15}".format('Profile Name', 'Best Price'))
    print("-" * 35)
    for data in profile_data:
        print("{:<20} {:<15}".format(data['profile_name'], data['best_price']))

def main():
    """Основная точка входа в программу."""
    max_profiles_to_use = 30
    run_profiles_sequentially(API_KEY, max_profiles=max_profiles_to_use)

if __name__ == "__main__":
    main()
