"""Сервис отправки уведомлений"""
import logging
from typing import Dict, List
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from database import db
from database.models import TrackedProfile
from sqlalchemy import select

logger = logging.getLogger(__name__)


class Notifier:
    """Отправка уведомлений пользователям"""

    def __init__(self, bot: Bot):
        self.bot = bot

    def _format_history_message(self, username: str, entries: List[Dict]) -> str:
        """Форматировать сообщение об изменениях в истории"""
        if not entries:
            return ""

        message = f"🔔 <b>Новая активность {username}</b>\n\n"

        for entry in entries[:5]:  # Максимум 5 записей
            anime_name = entry['anime_name']
            action = entry['action']
            timestamp = entry['timestamp']
            anime_url = entry.get('anime_url', '')

            if anime_url:
                message += f"📺 <a href='{anime_url}'>{anime_name}</a>\n"
            else:
                message += f"📺 {anime_name}\n"

            message += f"   {action}\n"
            message += f"   ⏰ {timestamp}\n\n"

        if len(entries) > 5:
            message += f"<i>... и ещё {len(entries) - 5} записей</i>"

        return message

    def _format_online_message(self, username: str, is_online: bool, status_text: str) -> str:
        """Форматировать сообщение об изменении статуса"""
        if is_online:
            return f"🟢 <b>{username}</b> сейчас в сети!\n\n{status_text}"
        else:
            return f"⚫ <b>{username}</b> вышел из сети\n\n{status_text}"

    async def notify_history_changes(self, user_id: int, username: str, entries: List[Dict]) -> bool:
        """Отправить уведомление об изменениях в истории"""
        if not entries:
            return False

        try:
            message = self._format_history_message(username, entries)
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info(
                f"Отправлено уведомление об истории для пользователя {user_id}")
            return True

        except TelegramForbiddenError:
            logger.warning(f"Бот заблокирован пользователем {user_id}")
            return False

        except TelegramBadRequest as e:
            logger.error(
                f"Ошибка отправки сообщения пользователю {user_id}: {e}")
            return False

        except Exception as e:
            logger.error(f"Неожиданная ошибка отправки уведомления: {e}")
            return False

    async def notify_online_status(self, user_id: int, username: str,
                                   is_online: bool, status_text: str) -> bool:
        """Отправить уведомление об изменении онлайн-статуса"""
        try:
            message = self._format_online_message(
                username, is_online, status_text)
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info(
                f"Отправлено уведомление о статусе для пользователя {user_id}")
            return True

        except TelegramForbiddenError:
            logger.warning(f"Бот заблокирован пользователем {user_id}")
            return False

        except TelegramBadRequest as e:
            logger.error(
                f"Ошибка отправки сообщения пользователю {user_id}: {e}")
            return False

        except Exception as e:
            logger.error(f"Неожиданная ошибка отправки уведомления: {e}")
            return False

    async def process_profile_updates(self, profile_id: int, update_data: Dict):
        """Обработать обновления профиля и отправить уведомления"""
        try:
            # Получаем профиль из БД
            async with db.session_maker() as session:
                stmt = select(TrackedProfile).where(
                    TrackedProfile.id == profile_id)
                result = await session.execute(stmt)
                profile = result.scalar_one_or_none()

                if not profile:
                    logger.warning(f"Профиль {profile_id} не найден")
                    return

                # Уведомление об истории
                if profile.notify_history and update_data.get('new_history'):
                    await self.notify_history_changes(
                        profile.user_id,
                        profile.shikimori_username,
                        update_data['new_history']
                    )

                # Уведомление о статусе онлайн
                if update_data.get('online_changed'):
                    is_online = update_data.get('is_online_now', False)
                    was_online = update_data.get('was_online', False)

                    # Онлайн
                    if is_online and not was_online and profile.notify_online:
                        await self.notify_online_status(
                            profile.user_id,
                            profile.shikimori_username,
                            True,
                            update_data.get('online_status', '')
                        )

                    # Оффлайн
                    elif not is_online and was_online and profile.notify_offline:
                        await self.notify_online_status(
                            profile.user_id,
                            profile.shikimori_username,
                            False,
                            update_data.get('online_status', '')
                        )

        except Exception as e:
            logger.error(
                f"Ошибка обработки обновлений профиля {profile_id}: {e}")
