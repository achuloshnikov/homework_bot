import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}

logger = logging.getLogger(__name__)


class HTTPStatusError(Exception):
    """Исключечение для ошибок HTTP статуса."""

    pass


def check_tokens():
    """Проверка окружения."""
    logger.debug('Проверка окружения')
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical('Отсутствует переменная окружения')
        sys.exit('Программа остановлена')
    logger.debug('Ошибки окружения отсутствуют')


def send_message(bot, message):
    """Отправляет сообщщение в чат тг."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил {message}')
    except Exception as error:
        logger.error(error)


def get_api_answer(timestamp):
    """Запрос к API Практикума с возвратом ответа."""
    try:
        payload = {'from_date': timestamp}
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=payload,
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise HTTPStatusError('Ответ не получен')
        return homework_statuses.json()
    except requests.exceptions.RequestException as error:
        raise Exception(f'Ошибка при запросе к API: {error}')


def check_response(response):
    """Проверка ответа API."""
    logging.info('Проверка ответа API')
    if not isinstance(response, dict):
        raise TypeError('Не является словарем')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Не является списком')
    return homeworks


def parse_status(homework):
    """Формирует сообщение для отправки."""
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
