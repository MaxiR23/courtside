from typing import Literal

from fastapi import APIRouter, Request

from app.feeds.games import FeedModel
from app.storage.state import FeedBuildState, JobState, StateStore

router = APIRouter()


class Health(FeedModel):
    status: Literal["ok"]
    jobs: list[JobState]
    feeds: list[FeedBuildState]


@router.get("/health")
def read_health(request: Request) -> Health:
    store = StateStore(request.app.state.settings.data_dir)
    return Health(
        status="ok", jobs=store.job_states(), feeds=store.failed_feed_builds()
    )
