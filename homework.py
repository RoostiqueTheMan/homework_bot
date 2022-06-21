import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv
from telegram.error import TelegramError

import exceptions

load_dotenv()


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(funcName)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramError as error:
        raise exceptions.BotError(
            f'Ошибка при отправке сообщения [{message}]'
        ) from error
    else:
        logger.info(f'Сообщение [{message}] отправлено')


def get_api_answer(current_timestamp):
    """Получает ответ от API."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)

    except requests.exceptions.RequestException as error:
        raise ConnectionError(
            f'Отсутствует доступ к эндпоинту {ENDPOINT} '
            f'Ошибка: {error}'
        ) from error

    if response.status_code != 200:
        raise ConnectionError(
            f'Статус эндпоинта {ENDPOINT} отличен от 200'
            f'Статус {response.status_code}'
        )

    return response.json()


def check_response(response):
    """Проверяет полученные данные."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ошибка в типе полученных данных '
            f'Тип данных: {type(response)}'
        )

    homeworks = response.get('homeworks')

    if 'current_date' not in response:
        raise exceptions.DateError(
            'Ключа current_date нет в полученных данных'
        )

    if 'homeworks' not in response:
        raise KeyError(
            'Ключа homeworks нет в полученных данных'
        )

    if not isinstance(homeworks, list):
        raise TypeError(
            f'Ошибка в типе данных домашних заданий '
            f'Тип данных: {type(homeworks)}'
        )
    return homeworks


def parse_status(homework):
    """Подгоняет формат данных под строку."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if not homework_name:
        raise KeyError(
            'Отсутствует ключ homework_name'
        )

    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError(
            f'Получен неожиданный статус работы: {homework_status}'
        )

    verdict = HOMEWORK_STATUSES.get(homework_status)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет переменные окружения."""
    env_vars = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for key, value in env_vars.items():
        if not value:
            logger.critical(f'Отсутствует переменная окружения {key}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    if check_tokens():

        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())

        error_cache = ''

        while True:
            try:
                response = get_api_answer(current_timestamp)
                homeworks = check_response(response)

                if len(homeworks) > 0:
                    text = parse_status(homeworks[0])
                    send_message(bot, text)
                response_date = response.get('current_date')

                if isinstance(response_date, int):
                    current_timestamp = response_date

            except (exceptions.BotError, exceptions.DateError) as error:
                logger.error(error)

            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
                if error_cache != message:
                    send_message(bot, message)
                    error_cache = message

            finally:
                time.sleep(RETRY_TIME)

    else:
        logger.critical('Работа бота была прервана')


if __name__ == '__main__':
    main()
