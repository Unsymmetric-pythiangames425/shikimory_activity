"""Парсер данных с Shikimori"""
import config
import aiohttp
import asyncio
import logging

from bs4 import BeautifulSoup
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class ShikimoriParser:
    """Парсер профилей Shikimori"""

    def __init__(self):
        self.base_url = config.SHIKIMORI_BASE_URL
        self.timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    async def _fetch_page(self, url: str, retries: int = 0) -> Optional[str]:
        """Получить HTML страницы"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 404:
                        logger.error(f"Профиль не найден: {url}")
                        return None
                    else:
                        logger.error(
                            f"Ошибка {response.status} при получении {url}")
                        return None
        except asyncio.TimeoutError:
            if retries < config.MAX_RETRIES:
                logger.warning(
                    f"Timeout, повтор {retries + 1}/{config.MAX_RETRIES}")
                await asyncio.sleep(2 ** retries)  # Экспоненциальная задержка
                return await self._fetch_page(url, retries + 1)
            logger.error(f"Превышено количество попыток для {url}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении страницы: {e}")
            return None

    def _parse_online_status(self, soup: BeautifulSoup) -> Dict[str, any]:
        """Парсинг онлайн статуса"""
        try:
            # Ищем в блоке c-brief > header > .misc
            misc_block = soup.find('div', class_='c-brief')
            if not misc_block:
                return {'is_online': False, 'status_text': 'Неизвестно'}

            header = misc_block.find('header', class_='head misc')
            if not header:
                return {'is_online': False, 'status_text': 'Неизвестно'}

            misc_div = header.find('div', class_='misc')
            if not misc_div:
                return {'is_online': False, 'status_text': 'Неизвестно'}

            status_text = misc_div.get_text(strip=True)

            # Определяем онлайн статус
            is_online = 'в сети' in status_text.lower() and 'назад' not in status_text.lower()

            return {
                'is_online': is_online,
                'status_text': status_text
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга статуса: {e}")
            return {'is_online': False, 'status_text': 'Ошибка парсинга'}

    def _parse_history(self, soup: BeautifulSoup) -> List[Dict]:
        """Парсинг истории активности"""
        history_entries = []

        try:
            # Ищем блок истории
            history_block = soup.find('div', class_='c-history')
            if not history_block:
                return history_entries

            # Парсим записи
            entries = history_block.find_all('div', class_='entry', limit=10)

            for entry in entries:
                try:
                    # Ссылка на аниме
                    link = entry.find('a')
                    if not link:
                        continue

                    anime_url = link.get('href', '')
                    if anime_url:
                        anime_url = f"{self.base_url}{anime_url}"

                    # Название аниме
                    anime_name_en = link.find('span', class_='name-en')
                    anime_name_ru = link.find('span', class_='name-ru')

                    anime_name = ''
                    if anime_name_en:
                        anime_name = anime_name_en.get_text(strip=True)
                    if anime_name_ru:
                        ru_name = anime_name_ru.get_text(strip=True)
                        if ru_name:
                            anime_name = f"{anime_name} / {ru_name}" if anime_name else ru_name

                    # Действие
                    misc_span = entry.find('span', class_='misc')
                    action = misc_span.get_text(
                        strip=True) if misc_span else ''

                    # Время
                    time_elem = entry.find('time', class_='date')
                    timestamp = time_elem.get_text(
                        strip=True) if time_elem else ''
                    datetime_attr = time_elem.get(
                        'datetime', '') if time_elem else ''

                    # Извлекаем ID из ссылки на историю (если есть)
                    history_link = entry.find_parent(
                        'div', class_='b-user_history-line')
                    entry_id = history_link.get(
                        'data-id', '') if history_link else f"{anime_url}_{timestamp}"

                    if anime_name and action:
                        history_entries.append({
                            'entry_id': entry_id or f"{anime_url}_{timestamp}",
                            'anime_name': anime_name,
                            'anime_url': anime_url,
                            'action': action,
                            'timestamp': timestamp,
                            'datetime': datetime_attr
                        })

                except Exception as e:
                    logger.error(f"Ошибка парсинга записи истории: {e}")
                    continue

        except Exception as e:
            logger.error(f"Ошибка парсинга истории: {e}")

        return history_entries

    def _parse_profile_info(self, soup: BeautifulSoup) -> Dict:
        """Парсинг информации профиля"""
        info = {
            'user_id': None,
            'username': '',
            'anime_stats': {},
            'manga_stats': {}
        }

        try:
            # ID пользователя (постоянный, не меняется при смене никнейма)
            profile_head = soup.find('div', class_='profile-head')
            if profile_head:
                user_id = profile_head.get('data-user-id')
                if user_id:
                    info['user_id'] = user_id

            # Имя пользователя
            username_elem = soup.find('h1', class_='aliases')
            if username_elem:
                info['username'] = username_elem.get_text(strip=True)

            # Статистика аниме
            anime_bar = soup.find('div', class_='b-stats_bar anime')
            if anime_bar:
                stats = anime_bar.find_all('div', class_='stat_name')
                for stat in stats:
                    link = stat.find('a')
                    if link:
                        # Извлекаем текст без цифр
                        text_parts = []
                        size_elem = link.find('span', class_='size')

                        # Получаем весь текст ссылки
                        full_text = link.get_text(strip=True)

                        # Удаляем цифры из текста
                        if size_elem:
                            count = size_elem.get_text(strip=True)
                            # Получаем текст без span.size
                            stat_name = full_text.replace(count, '').strip()
                            info['anime_stats'][stat_name] = count

            # Статистика манги
            manga_bar = soup.find('div', class_='b-stats_bar manga')
            if manga_bar:
                stats = manga_bar.find_all('div', class_='stat_name')
                for stat in stats:
                    link = stat.find('a')
                    if link:
                        # Извлекаем текст без цифр
                        size_elem = link.find('span', class_='size')

                        # Получаем весь текст ссылки
                        full_text = link.get_text(strip=True)

                        # Удаляем цифры из текста
                        if size_elem:
                            count = size_elem.get_text(strip=True)
                            # Получаем текст без span.size
                            stat_name = full_text.replace(count, '').strip()
                            info['manga_stats'][stat_name] = count

        except Exception as e:
            logger.error(f"Ошибка парсинга информации профиля: {e}")

        return info

    async def get_profile_data(self, username: str) -> Optional[Dict]:
        """Получить все данные профиля"""
        url = f"{self.base_url}/{username}"
        html = await self._fetch_page(url)

        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        # Парсим все данные
        online_status = self._parse_online_status(soup)
        history = self._parse_history(soup)
        profile_info = self._parse_profile_info(soup)

        return {
            'username': username,
            'url': url,
            'online_status': online_status,
            'history': history,
            'profile_info': profile_info,
            'success': True
        }

    async def get_history_page(self, username: str) -> Optional[List[Dict]]:
        """Получить историю со страницы /history"""
        url = f"{self.base_url}/{username}/history"
        html = await self._fetch_page(url)

        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        history_entries = []

        try:
            # Находим все записи истории
            history_lines = soup.find_all(
                'div', class_='b-user_history-line', limit=20)

            for line in history_lines:
                try:
                    entry_id = line.get('data-id', '')

                    # Ссылка на аниме
                    link = line.find('a', class_='db-entry')
                    if not link:
                        continue

                    anime_url = link.get('href', '')
                    if anime_url:
                        anime_url = f"{self.base_url}{anime_url}"

                    # Название
                    name_en = link.find('span', class_='name-en')
                    name_ru = link.find('span', class_='name-ru')

                    anime_name = ''
                    if name_en:
                        anime_name = name_en.get_text(strip=True)
                    if name_ru:
                        ru_name = name_ru.get_text(strip=True)
                        if ru_name:
                            anime_name = f"{anime_name} / {ru_name}" if anime_name else ru_name

                    # Действие - весь текст между ссылкой и временем
                    spans = line.find_all('span')
                    action = ''
                    for span in spans:
                        if 'db-entry' not in span.get('class', []) and 'date' not in span.get('class', []):
                            text = span.get_text(strip=True)
                            if text and text not in anime_name:
                                action = text
                                break

                    # Время
                    time_elem = line.find('time', class_='date')
                    timestamp = time_elem.get_text(
                        strip=True) if time_elem else ''
                    datetime_attr = time_elem.get(
                        'datetime', '') if time_elem else ''

                    if anime_name and entry_id:
                        history_entries.append({
                            'entry_id': entry_id,
                            'anime_name': anime_name,
                            'anime_url': anime_url,
                            'action': action,
                            'timestamp': timestamp,
                            'datetime': datetime_attr
                        })

                except Exception as e:
                    logger.error(
                        f"Ошибка парсинга записи на странице истории: {e}")
                    continue

        except Exception as e:
            logger.error(f"Ошибка парсинга страницы истории: {e}")

        return history_entries


# Глобальный экземпляр
parser = ShikimoriParser()
