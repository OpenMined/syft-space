"""Settings repository for database operations."""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from syft_space.components.settings.entities import (
    BENCHMARK_SETTINGS_ID,
    BenchmarkSettings,
    Settings,
)
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class SettingsRepository(AsyncBaseRepository[Settings]):
    """Repository for Settings CRUD operations.

    TODO: Add multi-tenant support.
    """

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, Settings)

    async def get_settings(self) -> Settings:
        """Get the settings."""
        settings = await self.get_all()
        if len(settings) > 0:
            return settings[0]
        # Create a new settings object if no settings exist
        settings = Settings(public_url=None, ngrok_token=None)
        return await self.create(settings)

    async def get_public_url(self) -> str | None:
        """Get the stored public URL."""
        settings = await self.get_settings()
        return settings.public_url

    async def update_public_url(self, url: str | None) -> Settings:
        """Update the public_url setting."""
        settings = await self.get_settings()
        settings.public_url = url
        settings.updated_at = datetime.now(timezone.utc)
        return await self.update(settings)

    async def get_ngrok_token(self) -> str:
        """Get the stored ngrok token."""
        settings = await self.get_settings()
        return settings.ngrok_token

    async def update_ngrok_token(self, token: str | None) -> Settings:
        """Update the ngrok token setting."""
        settings = await self.get_settings()
        settings.ngrok_token = token
        settings.updated_at = datetime.now(timezone.utc)
        return await self.update(settings)

    async def get_ngrok_domain(self) -> str | None:
        """Get the stored ngrok domain for tunnel."""
        settings = await self.get_settings()
        return settings.ngrok_domain

    async def update_ngrok_domain(self, domain: str | None) -> Settings:
        """Update the ngrok domain setting."""
        settings = await self.get_settings()
        settings.ngrok_domain = domain
        settings.updated_at = datetime.now(timezone.utc)
        return await self.update(settings)

    async def get_diagnostics_enabled(self) -> bool:
        """Get the diagnostics enabled setting."""
        settings = await self.get_settings()
        return settings.diagnostics_enabled

    async def update_diagnostics_enabled(self, enabled: bool) -> Settings:
        """Update the diagnostics enabled setting."""
        settings = await self.get_settings()
        settings.diagnostics_enabled = enabled
        settings.updated_at = datetime.now(timezone.utc)
        return await self.update(settings)

    async def get_benchmarks_settings(self) -> BenchmarkSettings:
        """Get the benchmark settings, or the defaults where nothing is stored.

        Reading does not write. A row exists only where somebody decided
        something — the owner flipping the switch, or
        ``enable_benchmarks_if_untouched`` on his first connection — so its
        absence is the answer to "has this ever been decided", and merely
        opening the page that shows the switch does not answer it for him.
        """
        async with self.db.get_session() as session:
            row = await session.get(BenchmarkSettings, BENCHMARK_SETTINGS_ID)
            return row if row is not None else BenchmarkSettings()

    async def get_benchmarks_mode(self) -> str:
        """Get how this Space accepts benchmark results."""
        return (await self.get_benchmarks_settings()).mode

    async def update_benchmarks_mode(self, mode: str) -> BenchmarkSettings:
        """Update how this Space accepts benchmark results."""
        async with self.db.get_session() as session:
            row = await session.get(BenchmarkSettings, BENCHMARK_SETTINGS_ID)
            if row is not None:
                row.mode = mode
                row.updated_at = datetime.now(timezone.utc)
                await session.commit()
                await session.refresh(row)
                return row

            session.add(BenchmarkSettings(mode=mode))
            try:
                await session.commit()
            except IntegrityError:
                # A concurrent call created the row first; update the one
                # that is actually there rather than leaving this call's mode
                # unapplied.
                await session.rollback()
                row = await session.get(BenchmarkSettings, BENCHMARK_SETTINGS_ID)
                assert row is not None
                row.mode = mode
                row.updated_at = datetime.now(timezone.utc)
                await session.commit()
                await session.refresh(row)
                return row

            row = await session.get(BenchmarkSettings, BENCHMARK_SETTINGS_ID)
            assert row is not None
            return row

    async def enable_benchmarks_if_untouched(self) -> None:
        """Turn benchmark reporting on, but only if the switch was never touched.

        Called when the owner makes the *first* benchmark connection this
        Space has ever had. Connecting one is a route only the owner can
        reach, and doing it already says he means for that benchmark to
        report in his name — asking him to also find a separate switch on the
        settings page and flip it would be the same consent asked for twice,
        once loudly and once in fine print.

        A row already existing means the switch was decided before — by an
        earlier call to this same method, or by the owner's own hand — and
        either way its value is left alone: turning it back off must stick,
        including across a later, second connection. Nothing else writes that
        row, reads included, or its absence would stop meaning "never decided".
        """
        async with self.db.get_session() as session:
            if await session.get(BenchmarkSettings, BENCHMARK_SETTINGS_ID) is not None:
                return
            session.add(BenchmarkSettings(mode="local"))
            try:
                await session.commit()
            except IntegrityError:
                # Lost the race to another concurrent first connection; its
                # row already says what this call would have said.
                await session.rollback()
