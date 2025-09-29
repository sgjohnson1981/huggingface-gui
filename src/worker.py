import sys
import traceback
from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.

    Supported signals are:
    - `finished`: Emitted when the task is done.
    - `error`: Emitted when an exception occurs, passing a tuple (type, value, traceback).
    - `result`: Emitted when the task successfully completes, passing the result object.
    """

    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)


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
        """
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