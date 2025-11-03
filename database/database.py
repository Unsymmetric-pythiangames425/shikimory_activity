"""Работа с базой данных"""
import config

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, delete
from typing import Optional, List
from datetime import datetime

from database.models import Base, User, TrackedProfile, HistoryEntry, OnlineStatus


class Database:
    def __init__(self, url: str = config.DATABASE_URL):
        self.engine = create_async_engine(url, echo=False)
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def init_db(self):
        """Инициализация базы данных"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        """Получить сессию"""
        async with self.session_maker() as session:
            return session

    # ===== USER =====
    async def add_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
        """Добавить пользователя"""
        async with self.session_maker() as session:
            # Проверяем существование
            result = await session.execute(select(User).where(User.id == user_id))
            existing = result.scalar_one_or_none()

            if existing:
                # Обновляем данные
                existing.username = username
                existing.first_name = first_name
                existing.is_active = True
            else:
                # Создаем нового
                user = User(
                    id=user_id,
                    username=username,
                    first_name=first_name
                )
                session.add(user)

            await session.commit()

    async def get_user(self, user_id: int) -> Optional[User]:
        """Получить пользователя"""
        async with self.session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    # ===== TRACKED PROFILES =====
    async def add_tracked_profile(self, user_id: int, shikimori_username: str,
                                  shikimori_user_id: Optional[str] = None, settings: dict = None) -> TrackedProfile:
        """Добавить отслеживаемый профиль"""
        async with self.session_maker() as session:
            # Проверяем существование по shikimori_user_id (если есть) или username
            if shikimori_user_id:
                result = await session.execute(
                    select(TrackedProfile).where(
                        TrackedProfile.user_id == user_id,
                        TrackedProfile.shikimori_user_id == shikimori_user_id
                    )
                )
            else:
                result = await session.execute(
                    select(TrackedProfile).where(
                        TrackedProfile.user_id == user_id,
                        TrackedProfile.shikimori_username == shikimori_username
                    )
                )

            existing = result.scalar_one_or_none()

            if existing:
                existing.is_active = True
                # Обновляем username если изменился
                existing.shikimori_username = shikimori_username
                if shikimori_user_id:
                    existing.shikimori_user_id = shikimori_user_id
                if settings:
                    for key, value in settings.items():
                        setattr(existing, key, value)
                await session.commit()
                return existing

            # Создаем новый профиль
            profile = TrackedProfile(
                user_id=user_id,
                shikimori_username=shikimori_username,
                shikimori_user_id=shikimori_user_id,
                **(settings or config.DEFAULT_SETTINGS)
            )
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            return profile

    async def get_user_profiles(self, user_id: int) -> List[TrackedProfile]:
        """Получить все профили пользователя"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(TrackedProfile).where(
                    TrackedProfile.user_id == user_id,
                    TrackedProfile.is_active == True
                )
            )
            return list(result.scalars().all())

    async def get_all_active_profiles(self) -> List[TrackedProfile]:
        """Получить все активные профили"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(TrackedProfile).where(TrackedProfile.is_active == True)
            )
            return list(result.scalars().all())

    async def update_profile_settings(self, profile_id: int, settings: dict):
        """Обновить настройки профиля"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(TrackedProfile).where(TrackedProfile.id == profile_id)
            )
            profile = result.scalar_one_or_none()

            if profile:
                for key, value in settings.items():
                    setattr(profile, key, value)
                profile.updated_at = datetime.now()
                await session.commit()

    async def get_profile_by_shikimori_id(self, shikimori_user_id: str) -> Optional[TrackedProfile]:
        """Получить профиль по ID на Shikimori"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(TrackedProfile).where(
                    TrackedProfile.shikimori_user_id == shikimori_user_id,
                    TrackedProfile.is_active == True
                )
            )
            return result.scalar_one_or_none()

    async def remove_profile(self, profile_id: int):
        """Удалить профиль"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(TrackedProfile).where(TrackedProfile.id == profile_id)
            )
            profile = result.scalar_one_or_none()

            if profile:
                profile.is_active = False
                await session.commit()

    async def update_profile_status(self, profile_id: int, online_status: str, was_online: bool):
        """Обновить статус профиля"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(TrackedProfile).where(TrackedProfile.id == profile_id)
            )
            profile = result.scalar_one_or_none()

            if profile:
                profile.last_online_status = online_status
                profile.was_online = was_online
                profile.updated_at = datetime.now()
                await session.commit()

    # ===== HISTORY =====
    async def add_history_entry(self, profile_id: int, entry_id: str, anime_name: str,
                                anime_url: str, action: str, timestamp: str) -> Optional[HistoryEntry]:
        """Добавить запись в историю"""
        async with self.session_maker() as session:
            # Проверяем существование
            result = await session.execute(
                select(HistoryEntry).where(
                    HistoryEntry.profile_id == profile_id,
                    HistoryEntry.entry_id == entry_id
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                return None  # Уже существует

            entry = HistoryEntry(
                profile_id=profile_id,
                entry_id=entry_id,
                anime_name=anime_name,
                anime_url=anime_url,
                action=action,
                timestamp=timestamp
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return entry

    async def get_unnotified_entries(self, profile_id: int) -> List[HistoryEntry]:
        """Получить неотправленные записи"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(HistoryEntry).where(
                    HistoryEntry.profile_id == profile_id,
                    HistoryEntry.notified == False
                ).order_by(HistoryEntry.created_at.desc())
            )
            return list(result.scalars().all())

    async def mark_as_notified(self, entry_id: int):
        """Отметить запись как отправленную"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(HistoryEntry).where(HistoryEntry.id == entry_id)
            )
            entry = result.scalar_one_or_none()

            if entry:
                entry.notified = True
                await session.commit()

    # ===== ONLINE STATUS =====
    async def add_online_status(self, profile_id: int, is_online: bool, status_text: str):
        """Добавить запись о статусе"""
        async with self.session_maker() as session:
            status = OnlineStatus(
                profile_id=profile_id,
                is_online=is_online,
                status_text=status_text
            )
            session.add(status)
            await session.commit()

    async def get_last_online_status(self, profile_id: int) -> Optional[OnlineStatus]:
        """Получить последний статус"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(OnlineStatus)
                .where(OnlineStatus.profile_id == profile_id)
                .order_by(OnlineStatus.checked_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()


# Глобальный экземпляр
db = Database()
