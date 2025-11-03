"""Главный файл бота"""
import config
import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import db
from handlers import setup_routers
from middlewares import DatabaseMiddleware
from services import tracker
from services.notifier import Notifier


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ShikimoriTrackerBot:
    """Основной класс бота"""

    def __init__(self):
        self.bot = Bot(
            token=config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dp = Dispatcher()
        self.notifier = Notifier(self.bot)
        self.scheduler = AsyncIOScheduler(timezone='Europe/Moscow')

        # Настройка middleware
        self.dp.update.middleware(DatabaseMiddleware())

        # Подключение роутеров
        self.dp.include_router(setup_routers())

    async def check_updates_task(self):
        """Периодическая задача проверки обновлений"""
        try:
            logger.info("Запуск проверки обновлений профилей")

            # Проверяем все профили
            results = await tracker.check_all_profiles()

            # Обрабатываем результаты
            for profile_id, update_data in results.items():
                if update_data.get('success'):
                    # Отправляем уведомления
                    await self.notifier.process_profile_updates(profile_id, update_data)

                    # Логируем изменения
                    if update_data.get('new_history'):
                        logger.info(
                            f"Профиль {profile_id}: {len(update_data['new_history'])} новых записей"
                        )

                    if update_data.get('online_changed'):
                        logger.info(
                            f"Профиль {profile_id}: изменение статуса онлайн"
                        )
                else:
                    logger.error(
                        f"Профиль {profile_id}: ошибка - {update_data.get('error')}")

            logger.info(
                f"Проверка завершена. Обработано профилей: {len(results)}")

        except Exception as e:
            logger.error(
                f"Ошибка в задаче проверки обновлений: {e}", exc_info=True)

    async def on_startup(self):
        """Действия при запуске бота"""
        logger.info("Запуск бота")

        # Инициализация БД
        await db.init_db()
        logger.info("База данных инициализирована")

        # Запуск планировщика задач
        self.scheduler.add_job(
            self.check_updates_task,
            'interval',
            minutes=config.CHECK_INTERVAL,
            id='check_updates',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(
            f"Планировщик запущен. Интервал проверки: {config.CHECK_INTERVAL} мин"
        )

        # Первая проверка сразу после запуска
        await self.check_updates_task()

    async def on_shutdown(self):
        """Действия при остановке бота"""
        logger.info("Остановка бота")

        # Останавливаем планировщик
        self.scheduler.shutdown()
        logger.info("Планировщик остановлен")

        # Закрываем бота
        await self.bot.session.close()

    async def run(self):
        """Запустить бота"""
        try:
            await self.on_startup()

            # Запуск polling
            logger.info("Бот запущен и готов к работе")
            await self.dp.start_polling(
                self.bot,
                allowed_updates=self.dp.resolve_used_update_types()
            )

        except Exception as e:
            logger.error(f"Критическая ошибка: {e}", exc_info=True)

        finally:
            await self.on_shutdown()


async def main():
    """Главная функция"""
    bot = ShikimoriTrackerBot()
    await bot.run()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}", exc_info=True)
