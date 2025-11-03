"""Сервис отслеживания изменений"""
import logging
from typing import List, Dict, Optional


from database import db
from database.models import TrackedProfile, TrackedProfile

from sqlalchemy import select

from services.shikimori_parser import parser
                
logger = logging.getLogger(__name__)


class ProfileTracker:
    """Отслеживание изменений в профилях"""

    async def check_profile_updates(self, profile_id: int, shikimori_username: str) -> Dict:
        """
        Проверить обновления профиля

        Returns:
            Dict с ключами: 'new_history', 'online_changed', 'status'
        """
        result = {
            'new_history': [],
            'online_changed': False,
            'online_status': None,
            'was_online': False,
            'is_online_now': False,
            'success': False,
            'error': None
        }

        try:
            # Получаем данные с Shikimori
            data = await parser.get_profile_data(shikimori_username)

            if not data or not data.get('success'):
                result['error'] = 'Не удалось получить данные профиля'
                return result

            result['success'] = True

            # Проверяем историю
            history_entries = data.get('history', [])
            if history_entries:
                new_entries = await self._check_new_history(profile_id, history_entries)
                result['new_history'] = new_entries

            # Проверяем онлайн статус
            online_status = data.get('online_status', {})
            is_online = online_status.get('is_online', False)
            status_text = online_status.get('status_text', '')

            result['online_status'] = status_text
            result['is_online_now'] = is_online

            # Проверяем смену никнейма
            profile_info = data.get('profile_info', {})
            current_username = profile_info.get('username', '')
            if current_username and current_username != shikimori_username:
                logger.info(
                    f"Обнаружена смена никнейма: {shikimori_username} -> {current_username}")
                # Обновляем никнейм в БД
                async with db.session_maker() as session:
                    stmt = select(TrackedProfile).where(
                        TrackedProfile.id == profile_id)
                    result_db = await session.execute(stmt)
                    profile = result_db.scalar_one_or_none()
                    if profile:
                        profile.shikimori_username = current_username
                        await session.commit()

            # Получаем предыдущий статус из БД
            async with db.session_maker() as session:
                stmt = select(TrackedProfile).where(
                    TrackedProfile.id == profile_id)
                result_db = await session.execute(stmt)
                profile = result_db.scalar_one_or_none()

                if profile:
                    result['was_online'] = profile.was_online

                    # Проверяем изменение статуса (только если есть новая активность в истории)
                    # Не отправляем уведомление просто за изменение времени "был в сети X минут назад"
                    if profile.was_online != is_online and result['new_history']:
                        result['online_changed'] = True
                        logger.info(
                            f"Изменение статуса для {shikimori_username}: {profile.was_online} -> {is_online}")
                    # Если нет новой активности, но статус изменился с offline на online - уведомляем
                    elif not profile.was_online and is_online:
                        result['online_changed'] = True
                        logger.info(
                            f"Пользователь {shikimori_username} вошёл в сеть")
                    # Если был online и стал offline - уведомляем
                    elif profile.was_online and not is_online:
                        result['online_changed'] = True
                        logger.info(
                            f"Пользователь {shikimori_username} вышел из сети")

            # Обновляем статус в БД
            await db.update_profile_status(profile_id, status_text, is_online)

            # Сохраняем статус в историю
            await db.add_online_status(profile_id, is_online, status_text)

        except Exception as e:
            logger.error(
                f"Ошибка проверки обновлений профиля {shikimori_username}: {e}")
            result['error'] = str(e)

        return result

    async def _check_new_history(self, profile_id: int, history_entries: List[Dict]) -> List[Dict]:
        """Проверить новые записи в истории"""
        new_entries = []

        for entry in history_entries:
            try:
                # Пытаемся добавить запись в БД
                db_entry = await db.add_history_entry(
                    profile_id=profile_id,
                    entry_id=entry['entry_id'],
                    anime_name=entry['anime_name'],
                    anime_url=entry['anime_url'],
                    action=entry['action'],
                    timestamp=entry['timestamp']
                )

                # Если запись новая (не None), добавляем в результат
                if db_entry:
                    new_entries.append(entry)
                    logger.info(
                        f"Новая запись в истории: {entry['anime_name']} - {entry['action']}")

            except Exception as e:
                logger.error(f"Ошибка добавления записи истории: {e}")
                continue

        return new_entries

    async def check_all_profiles(self) -> Dict[int, Dict]:
        """Проверить все активные профили"""
        results = {}

        profiles = await db.get_all_active_profiles()
        logger.info(f"Проверка {len(profiles)} активных профилей")

        for profile in profiles:
            try:
                result = await self.check_profile_updates(
                    profile.id,
                    profile.shikimori_username
                )
                results[profile.id] = result

            except Exception as e:
                logger.error(
                    f"Ошибка проверки профиля {profile.shikimori_username}: {e}")
                results[profile.id] = {
                    'success': False,
                    'error': str(e)
                }

        return results

    async def get_full_history(self, username: str, limit: int = 20) -> Optional[List[Dict]]:
        """Получить полную историю со страницы /history"""
        try:
            history = await parser.get_history_page(username)
            if history:
                return history[:limit]
            return None
        except Exception as e:
            logger.error(
                f"Ошибка получения полной истории для {username}: {e}")
            return None


# Глобальный экземпляр
tracker = ProfileTracker()
