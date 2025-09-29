import multiprocessing
from .logging_config import logger

class DownloadWorker:
    """
    Manages a download operation in a separate process to allow for safe cancellation.
    """
    def __init__(self, target, args):
        """
        Initializes the worker.

        Args:
            target (callable): The function to run in the separate process.
            args (tuple): The arguments to pass to the target function.
        """
        self.target = target
        self.args = args
        self.queue = multiprocessing.Queue()
        self.process = None

    def start(self):
        """
        Starts the download process.
        """
        if self.process is not None and self.process.is_alive():
            logger.warning("Download process is already running.")
            return

        # The queue is added to the arguments for the target function to use
        process_args = (self.queue,) + self.args
        self.process = multiprocessing.Process(target=self.target, args=process_args)
        self.process.start()
        logger.info(f"Started download process with PID: {self.process.pid}")

    def stop(self):
        """
        Stops (terminates) the download process if it's running.
        """
        if self.process and self.process.is_alive():
            logger.info(f"Terminating download process with PID: {self.process.pid}")
            self.process.terminate()
            self.process.join() # Wait for the process to terminate
            logger.info("Download process terminated.")
        else:
            logger.info("No active download process to stop.")

    def is_running(self):
        """
        Checks if the download process is currently running.
        """
        return self.process and self.process.is_alive()