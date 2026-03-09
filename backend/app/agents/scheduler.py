"""Agent Scheduler

Central scheduler that runs all background agents on configurable intervals.
Integrates with FastAPI's lifespan to start/stop cleanly.
"""
import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("agents.scheduler")


@dataclass
class ScheduledAgent:
    name: str
    coroutine_fn: object  # async callable
    interval_seconds: int
    task: asyncio.Task | None = field(default=None, repr=False)


class AgentScheduler:
    def __init__(self):
        self._agents: list[ScheduledAgent] = []
        self._running = False

    def register(self, name: str, coroutine_fn, interval_seconds: int):
        self._agents.append(ScheduledAgent(
            name=name,
            coroutine_fn=coroutine_fn,
            interval_seconds=interval_seconds,
        ))

    async def start(self):
        self._running = True
        for agent in self._agents:
            agent.task = asyncio.create_task(self._run_loop(agent))
            logger.info(f"Started agent: {agent.name} (every {agent.interval_seconds}s)")

    async def stop(self):
        self._running = False
        for agent in self._agents:
            if agent.task:
                agent.task.cancel()
                try:
                    await agent.task
                except asyncio.CancelledError:
                    pass
                logger.info(f"Stopped agent: {agent.name}")

    async def _run_loop(self, agent: ScheduledAgent):
        # Initial delay to let the app fully start
        await asyncio.sleep(5)

        while self._running:
            try:
                result = await agent.coroutine_fn()
                logger.debug(f"Agent {agent.name} completed: {result}")
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Agent {agent.name} failed: {e}", exc_info=True)

            try:
                await asyncio.sleep(agent.interval_seconds)
            except asyncio.CancelledError:
                return

    def status(self) -> list[dict]:
        return [
            {
                "name": a.name,
                "interval_seconds": a.interval_seconds,
                "running": a.task is not None and not a.task.done(),
            }
            for a in self._agents
        ]


def create_default_scheduler() -> AgentScheduler:
    """Create the scheduler with all default agents registered."""
    from app.agents import expiration, reprocessing, moderation, analytics

    scheduler = AgentScheduler()

    scheduler.register("query_expiration", expiration.run, interval_seconds=300)       # 5 min
    scheduler.register("match_reprocessing", reprocessing.run, interval_seconds=120)   # 2 min
    scheduler.register("content_moderation", moderation.sweep_unmoderated, interval_seconds=60)  # 1 min
    scheduler.register("analytics_snapshot", analytics.run, interval_seconds=3600)     # 1 hour

    return scheduler
