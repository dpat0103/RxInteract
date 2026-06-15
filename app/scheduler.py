from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.orm_models import Drug
from app.service import get_or_fetch_label, STALE_AFTER_DAYS
from app.logger import get_logger
from datetime import datetime, timezone, timedelta

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()


async def refresh_stale_drugs():
    """
    Runs on a schedule, finds every drug in the DB whose label is older
    than STALE_AFTER_DAYS and re-fetches it from OpenFDA.
    This ensures cached data stays current without requiring a user request
    to trigger the refresh.
    """
    logger.info("[SCHEDULER] Starting stale drug refresh job")

    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_AFTER_DAYS)
        result = await db.execute(select(Drug).where(Drug.last_updated < cutoff))
        stale_drugs = result.scalars().all()

        if not stale_drugs:
            logger.info("[SCHEDULER] No stale drugs found — nothing to refresh")
            return

        logger.info(f"[SCHEDULER] Found {len(stale_drugs)} stale drug(s) to refresh")

        for drug in stale_drugs:
            try:
                await get_or_fetch_label(drug, db)
                logger.info(f"[SCHEDULER] Refreshed label for '{drug.name}'")
            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to refresh '{drug.name}': {e}")

    logger.info("[SCHEDULER] Refresh job complete")


def start_scheduler():
    scheduler.add_job(
        refresh_stale_drugs,
        trigger="interval",
        hours=24,
        id="refresh_stale_drugs",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[SCHEDULER] APScheduler started — refresh job runs every 24 hours")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("[SCHEDULER] APScheduler stopped")
