import sys
import traceback
from PySide6.QtCore import QObject, QRunnable, Signal, Slot


import inspect

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.

    Supported signals are:
    - `finished`: Emitted when the task is done.
    - `error`: Emitted when an exception occurs, passing a tuple (type, value, traceback).
    - `result`: Emitted when the task successfully completes, passing the result object.
    - `progress`: Emitted to update progress, passing two integers (current, total).
    """

    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int, int)


class Worker(QRunnable):
    """
    Worker thread for running a function in the background.

    Inherits from QRunnable to handle worker thread setup, execution, and signals.

    :param fn: The function to run.
    :param args: Positional arguments to pass to the function.
    :param kwargs: Keyword arguments to pass to the function.
    """

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        Execute the worker's function with the provided arguments.
        If the target function accepts a 'progress_callback' keyword argument,
        it will be provided with a callback that emits the progress signal.
        """
        # Check if the target function accepts a 'progress_callback' kwarg.
        try:
            sig = inspect.signature(self.fn)
            if 'progress_callback' in sig.parameters:
                # If it does, inject our progress-emitting callback.
                self.kwargs['progress_callback'] = self.signals.progress.emit
        except (ValueError, TypeError):
            # Some callables (e.g., built-ins) might not support introspection.
            # In these cases, we just proceed without the callback.
            pass

        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            exctype, value = sys.exc_info()[:2]
            tb = traceback.format_exc()
            self.signals.error.emit((exctype, value, tb))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()