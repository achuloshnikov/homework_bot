import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from exceptions import HTTPStatusError, RequestError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600  # 10 минут (10 * 60)
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def check_tokens() -> None:
    """Проверка окружения."""
    logger = logging.getLogger(__name__)
    logger.debug('Проверка окружения')
    for env_var in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        if env_var is None:
            logger.critical(f'Отсутствует переменная окружения {env_var}')
            sys.exit('Программа остановлена')
    logger.debug('Ошибки окружения отсутствуют')


def send_message(bot: telegram.Bot, message: str):
    """Отправляет сообщщение в чат тг.

    Args:
        bot (telegram.Bot): Объект бота Telegram.
        message (str): Текст сообщения.
    """
    logger = logging.getLogger(__name__)
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.exception(error)
    logger.debug(f'Бот отправил {message}')


def get_api_answer(timestamp: int) -> dict:
    """Запрос к API Практикума с возвратом ответа.

    Args:
        timestamp (int): Временная метка для запроса статусов заданий.

    Returns:
        dict: Словарь с данными о статусах заданий.

    Raises:
        HTTPStatusError: Если ответ от API не является успешным.
        RequestError: Если возникает ошибка при запросе к API.
    """
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp},
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise HTTPStatusError('Ответ не получен')
        return homework_statuses.json()
    except requests.exceptions.RequestException as error:
        raise RequestError(f'Ошибка при запросе к API: {error}')


def check_response(response: dict) -> list:
    """Проверка ответа API.

    Args:
        response (dict): Ответ API, который необходимо проверить.

    Returns:
        list: Список домашних заданий, если ответ прошел проверку.

    Raises:
        TypeError: Если ответ не является словарем или дз не является списком.
    """
    logging.info('Проверка ответа API')
    if not isinstance(response, dict):
        raise TypeError('Не является словарем')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Не является списком')
    return homeworks


def parse_status(homework: dict) -> str:
    """Формирует сообщение для отправки.

    Args:
        homework (dict): Словарь с информацией о домашней работе.

    Returns:
        str: Сообщение для отправки в чат.

    Raises:
        KeyError: Если не найден ключ или некорректен статус домашней работы.
    """
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('Нет ключа в словаре')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS or status is None:
        raise KeyError(f'Некорректный статус домашки {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger = logging.getLogger(__name__)
    check_tokens()
    logger.debug('Запуск бота')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logger.debug('Бот успешно запущен')
    logger.debug('Определение параметра from_date')
    timestamp = 0
    logger.debug('Параметр from_date определен')
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            homework = homeworks[0]
            message = parse_status(homework)
            send_message(bot, message)
        except Exception as error:
            message = f'Возникновение ошибки: {error}'
            logger.exception(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
