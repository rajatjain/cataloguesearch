#!/usr/bin/env python3
"""
CLI/Daemon for CatalogueSearch Discovery Module
"""

import argparse
import logging
import os
import signal
import sys
import time
import psutil
from datetime import datetime
from threading import Event

from backend.common.opensearch import get_opensearch_client, get_metadata
from backend.config import Config
from backend.crawler.discovery import Discovery
from backend.crawler.index_state import IndexState
from backend.index.embedding_module import IndexingEmbeddingModule
from backend.crawler.pdf_processor import PDFProcessor
from utils.logger import setup_logging, VERBOSE_LEVEL_NUM

PIDFILE = '/tmp/discovery-daemon.pid'

log_handle = logging.getLogger(__name__)

class DaemonManager:
    """Manages daemon process lifecycle"""

    @staticmethod
    def write_pidfile(pid):
        """Write PID to file"""
        with open(PIDFILE, 'w') as f:
            f.write(f"{pid}\n{datetime.now().isoformat()}\n")

    @staticmethod
    def read_pidfile():
        """Read PID and start time from file"""
        try:
            with open(PIDFILE, 'r') as f:
                lines = f.read().strip().split('\n')
                pid = int(lines[0])
                start_time = datetime.fromisoformat(lines[1])
                return pid, start_time
        except (FileNotFoundError, ValueError, IndexError):
            return None, None

    @staticmethod
    def remove_pidfile():
        """Remove PID file"""
        try:
            os.remove(PIDFILE)
        except FileNotFoundError:
            pass

    @staticmethod
    def is_process_running(pid):
        """Check if process is running"""
        try:
            return psutil.pid_exists(pid)
        except:
            return False

    @staticmethod
    def kill_process(pid):
        """Kill process"""
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            if DaemonManager.is_process_running(pid):
                os.kill(pid, signal.SIGKILL)
            return True
        except:
            return False

    @staticmethod
    def check_existing_daemon():
        """Check for existing daemon and handle according to requirements"""
        pid, start_time = DaemonManager.read_pidfile()

        if pid is None:
            return True  # No existing daemon

        if not DaemonManager.is_process_running(pid):
            # Process not running, clean up stale pidfile
            DaemonManager.remove_pidfile()
            return True

        # Process is running, check how long
        running_hours = (datetime.now() - start_time).total_seconds() / 3600

        if running_hours > 2:
            logging.info(f"Existing daemon (PID {pid}) running for {running_hours:.1f} hours. Killing...")
            if DaemonManager.kill_process(pid):
                DaemonManager.remove_pidfile()
                logging.info("Killed existing daemon")
                return True
            else:
                logging.error("Failed to kill existing daemon")
                return False
        else:
            logging.info(f"Existing daemon (PID {pid}) running for {running_hours:.1f} hours. Exiting.")
            return False


class DiscoveryDaemon:
    """Daemon that runs discovery at regular intervals"""

    def __init__(self, config: Config):
        self.config = config
        self.stop_event = Event()

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Initialize discovery components
        self.index_state = IndexState(config.SQLITE_DB_PATH)
        self.pdf_processor = PDFProcessor(config)
        self.indexing_module = IndexingEmbeddingModule(config)
        self.discovery = Discovery(config, self.indexing_module, self.pdf_processor, self.index_state)

        logging.info("Discovery daemon initialized")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logging.info(f"Received signal {signum}. Shutting down...")
        self.stop_event.set()

    def _run_discovery(self):
        """Run discovery and log results"""
        try:
            logging.info("Starting discovery crawl...")

            # Run discovery
            self.discovery.crawl()

            # Update metadata cache after discovery
            logging.info("Updating metadata cache...")
            metadata = get_metadata(self.config)
            self.index_state.update_metadata_cache(metadata)
            logging.info("Metadata cache updated successfully")

        except Exception as e:
            logging.error(f"Discovery failed: {e}")
            raise

    def start(self):
        """Start the daemon"""
        # Write PID file
        DaemonManager.write_pidfile(os.getpid())

        try:
            logging.info("Starting discovery daemon...")

            # Run initial discovery
            self._run_discovery()

            # Daemon loop - run every 6 hours
            while not self.stop_event.is_set():
                logging.info("Waiting 6 hours until next discovery run...")

                if self.stop_event.wait(timeout=6 * 3600):  # 6 hours
                    break

                self._run_discovery()

        finally:
            DaemonManager.remove_pidfile()
            logging.info("Discovery daemon stopped")


def run_discovery_once(config: Config):
    """Run discovery once"""
    try:
        logging.info("Starting one-time discovery...")

        # Initialize components
        index_state = IndexState(config.SQLITE_DB_PATH)
        pdf_processor = PDFProcessor(config)
        indexing_module = IndexingEmbeddingModule(config, get_opensearch_client(config))
        discovery = Discovery(config, indexing_module, pdf_processor, index_state)

        # Run discovery
        discovery.crawl()

        # Update metadata cache after discovery
        logging.info("Updating metadata cache...")
        metadata = get_metadata(config)
        index_state.update_metadata_cache(metadata)
        logging.info("Metadata cache updated successfully")

    except Exception as e:
        logging.error(f"Discovery failed: {e}")
        sys.exit(1)

def delete_index(config: Config):
    get_opensearch_client(config, force_clean=True)

    # delete index_state as well
    index_state = IndexState(config.SQLITE_DB_PATH)
    index_state.delete_index_state()

def main():
    parser = argparse.ArgumentParser(description="CatalogueSearch Discovery CLI/Daemon")

    parser.add_argument('command', choices=['discover'], help='Command to run')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (every 6 hours)')
    parser.add_argument('--delete-index', action='store_true',
                        help='Delete OpenSearch index before starting discovery')

    args = parser.parse_args()

    # setup logging
    logs_dir = os.getenv("HOME", "") + "/cataloguesearch/logs/discovery"
    setup_logging(logs_dir, console_level=logging.INFO,
                  file_level=VERBOSE_LEVEL_NUM, console_only=False)

    try:
        config = Config("configs/config.yaml")
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        sys.exit(1)

    if args.command == 'discover':
        if args.delete_index:
            delete_index(config)
        if args.daemon:
            # Check existing daemon
            if not DaemonManager.check_existing_daemon():
                sys.exit(1)

            # Start daemon
            daemon = DiscoveryDaemon(config)
            daemon.start()
        else:
            run_discovery_once(config)


if __name__ == '__main__':
    main()