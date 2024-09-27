import os
import sys
import re
import time
import shutil
import logging
import requests
import configparser
from gologin import GoLogin
from selenium import webdriver
from contextlib import contextmanager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Загрузка конфигурации из config.ini
config = configparser.ConfigParser()
config.read('config.ini')

# Чтение параметров из конфигурационного файла
API_KEY = config['gologin']['api_key']
SITE_URL = config['gologin']['site_url']
CHROME_DRIVER_PATH = config['selenium']['chrome_driver_path']
AMOUNT_OF_PROFILES = config.getint('selenium', 'amount_of_profiles')
PROFILE_FOLDER = config['gologin']['profile_folder']
BASE_URL = 'https://api.gologin.com/browser/v2'

# Контекстный менеджер для подавления вывода в консоль и stderr
@contextmanager
def suppress_output():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = devnull
            sys.stderr = devnull
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

def get_profiles(api_key, folder):
    """Получает список профилей из GoLogin с использованием предоставленного API ключа и указанной папки."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(f"{BASE_URL}?folder={folder}", headers=headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logging.error(f"Other error occurred: {err}")
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

        # Перенаправляем все выводы библиотеки
        with suppress_output():
            debugger_address = gl.start()

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)

        temp_user_data_dir = os.path.join('C:\\TempProfiles', f"chrome_profile_{profile_id}")
        os.makedirs(temp_user_data_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={temp_user_data_dir}")

        service = ChromeService(executable_path=CHROME_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        return driver, gl, temp_user_data_dir

    except Exception as e:
        logging.error(f"Failed to start Selenium WebDriver for profile {profile_id}: {e}")
        raise

def extract_price(driver):
    """Извлекает цену с текущей страницы."""
    try:
        price_element = WebDriverWait(driver, 10, poll_frequency=0.2).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h3[data-auto='snippet-price-current']"))
        )
        price = price_element.text.strip()
        price = re.sub(r'[^\d,]', '', price)
        price_float = float(price.replace(',', '.'))

        return price_float
    except Exception as e:
        logging.error(f"Failed to extract price: {e}")
        return float('inf')

def clean_pickup_point_address(raw_text):
    """Очищает текст пункта выдачи, оставляя только первую строку с адресом."""
    address_lines = raw_text.split('\n')
    if len(address_lines) > 1:
        first_line = address_lines[0].strip()
        first_line += ', ' + address_lines[1].strip()
    else:
        first_line = address_lines[0].strip()
    return first_line

def iterate_pickup_points(driver):
    """Перебирает все доступные пункты выдачи и возвращает данные с лучшей ценой."""
    try:
        best_price = float('inf')
        best_pickup_point = ""

        # Открыть меню пунктов выдачи
        WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.ID, "hyperlocation-unified-dialog-anchor"))
        ).click()

        # Ожидаем появления всех элементов ПВЗ
        WebDriverWait(driver, 2).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[@aria-label='Выбрать адрес доставки']"))
        )

        # Получаем все элементы пунктов выдачи с текстом "Пункт выдачи" или "7 дней хранения"
        pickup_points = driver.find_elements(By.XPATH, "//div[@aria-label='Выбрать адрес доставки' and (contains(., 'Пункт выдачи') or contains(., '7 дней хранения'))]")

        for i in range(len(pickup_points)):
            try:
                # Повторный поиск элемента для предотвращения stale element reference exception
                pickup_points = driver.find_elements(By.XPATH, "//div[@aria-label='Выбрать адрес доставки' and (contains(., 'Пункт выдачи') or contains(., '7 дней хранения'))]")
                if i >= len(pickup_points):
                    continue

                point = pickup_points[i]

                # Извлечение текста адреса
                point_address_raw = point.text.strip()
                point_address = clean_pickup_point_address(point_address_raw)

                # Прокрутка к элементу и клик по нему с помощью JavaScript
                driver.execute_script("arguments[0].scrollIntoView();", point)
                time.sleep(1)  # Пауза для прокрутки

                # Используем JavaScript для клика по элементу
                driver.execute_script("arguments[0].click();", point)
                time.sleep(1)  # Ждем завершения действия

                # После клика по пункту самовывоза необходимо подождать обновления цены
                price = extract_price(driver)

                # Сравниваем текущую цену с лучшей ценой
                if price < best_price:
                    best_price = price
                    best_pickup_point = point_address

                # После каждого выбора пункта выдачи, нужно снова открыть меню
                WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.ID, "hyperlocation-unified-dialog-anchor"))
                ).click()
                time.sleep(1)  # Пауза для обновления страницы и повторного открытия меню

            except Exception as e:
                pass  # Можно добавить логгирование в случае отладки

        return best_price, best_pickup_point

    except Exception as e:
        return float('inf'), ""  # Возвращаем 'inf' и пустую строку в случае ошибки

def cleanup(temp_user_data_dir):
    """Очищает временные директории."""
    try:
        shutil.rmtree(temp_user_data_dir)
        logging.info(f"Temporary profile directory {temp_user_data_dir} deleted successfully.")
    except Exception as e:
        logging.error(f"Failed to delete temporary profile directory {temp_user_data_dir}: {e}")

def run_profile(profile, api_key):
    """Выполняет процесс парсинга для одного профиля GoLogin."""
    profile_id = profile['id']
    profile_name = profile['name']

    logging.info(f"Открытие профиля {profile_name}...")  # Добавляем сообщение об открытии профиля

    try:
        with suppress_output():  # Подавляем стандартный вывод и stderr от GoLogin
            driver, gl, temp_user_data_dir = start_selenium_with_profile(profile_id, api_key)
        try:
            driver.get(SITE_URL)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )

            # Проверка на наличие активного окна перед выполнением действий
            if not driver.window_handles:
                logging.error(f"Окно закрыто для профиля {profile_name}.")
                return float('inf'), ""

            best_price, best_pickup_point = iterate_pickup_points(driver)
        except Exception as e:
            logging.error(f"Ошибка во время выполнения профиля {profile_name}: {e}")
            best_price, best_pickup_point = float('inf'), ""
        finally:
            # Проверяем, не закрылось ли окно перед закрытием драйвера
            if driver:
                driver.quit()
            gl.stop()
            cleanup(temp_user_data_dir)

    except Exception as e:
        logging.error(f"Ошибка при запуске профиля {profile_name}: {e}")
        best_price, best_pickup_point = float('inf'), ""

    return {'profile_name': profile_name, 'best_price': best_price, 'best_pickup_point': best_pickup_point}

def run_profiles_sequentially(api_key, amount_of_profiles):
    """Выполняет процесс парсинга последовательно по всем профилям GoLogin."""
    profiles_data = get_profiles(api_key, PROFILE_FOLDER)
    if profiles_data is None:
        return

    if 'profiles' in profiles_data:
        profiles = profiles_data['profiles']

        # Ограничиваем количество профилей
        profiles = profiles[:amount_of_profiles]

        profile_data = []

        for profile in profiles:
            result = run_profile(profile, api_key)
            profile_data.append(result)

        profile_data = sorted(profile_data, key=lambda x: x['best_price'])

        logging.info("\nParsing complete. Results (sorted by best price):")
        logging.info("{:<30} {:<15} {:<30}".format('Profile Name', 'Best Price', 'Best Pickup Point'))
        logging.info("-" * 75)
        for data in profile_data:
            logging.info("{:<30} {:<15} {:<30}".format(data['profile_name'], data['best_price'], data['best_pickup_point']))
    else:
        logging.error("Unexpected response structure: %s", profiles_data)

def main():
    """Основная точка входа в программу."""
    try:
        # Ограничение количества профилей из конфигурационного файла
        amount_of_profiles = AMOUNT_OF_PROFILES  # Получаем количество профилей из конфигурации

        logging.info(f"Запуск программы с обработкой {amount_of_profiles} профилей...")

        # Запуск парсинга профилей последовательно (без многопоточности)
        run_profiles_sequentially(API_KEY, amount_of_profiles=amount_of_profiles)

        logging.info("Парсинг завершен.")

    except Exception as e:
        logging.error(f"Ошибка в main: {e}")

if __name__ == "__main__":
    main()
