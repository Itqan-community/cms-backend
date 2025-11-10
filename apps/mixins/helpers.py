import logging

from celery.result import AsyncResult, EagerResult

from config.settings.base import RUNNING_TESTS

logger = logging.getLogger(__name__)


def run_task(task, *args, **kwargs) -> AsyncResult | EagerResult:
    """
    This helper method will allow us to directly run the tasks locally during unit testing,
    instead of deferring to celery.

    Why not use celery in unit testing:
    1. we will have to run a test celery instance which is not always feasible
    1. celery is async, which adds complexity to the testing


    :param task: The task function.
    :param args: The positional arguments passed on to the task.
    :param kwargs: The keyword arguments passed on to the task.

    :return: The task result object
    """
    if RUNNING_TESTS:
        # we use `.apply` instead of calling the task directly, in order to catch any serialization issues.
        return task.apply(args=args, kwargs=kwargs, throw=True)
    else:
        logger.info(f"running task: {task}, with args: {args}, and kwargs: {kwargs}")
        if countdown := kwargs.pop("countdown", None):
            return task.apply_async(kwargs=kwargs, countdown=countdown)
        return task.delay(*args, **kwargs)


def get_mp3_duration_ms(django_file) -> int:
    """
    Return duration (ms) for an MP3 Django File; returns 0 on error.
    """
    try:
        from mutagen.mp3 import MP3  # type: ignore[import-not-found]

        f = getattr(django_file, "file", django_file)
        try:
            f.seek(0)
        except Exception:
            pass
        audio = MP3(f)
        return int(audio.info.length * 1000)
    except Exception:
        return 0
